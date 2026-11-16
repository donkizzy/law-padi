import json
from pathlib import Path

import pytest
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.pgvector_repository import dense_search, hybrid_search
from app.ingestion.worker import (
    handle_building_retrieval_documents,
    run_until_idle,
)
from app.ingestion.workflow import enqueue_task
from app.legal.enums import (
    EmbeddingRunStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    VectorIndexStatus,
)
from app.legal.models import (
    EmbeddingRun,
    IngestionArtifact,
    IngestionStep,
    IngestionTask,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
)
from tests.ingestion.worker.conftest import _release_with_retrieval_documents


def test_worker_embeds_indexes_and_validates_pgvector_dataset(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RETRIEVAL_INDEX_BACKEND", "pgvector")
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    release.validation_report = {
        "unresolved_gates": [
            "ready_retrieval_index_build_missing",
            "unrelated_review_gate",
        ]
    }
    db.add(release)
    db.commit()

    class FakeEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            if texts == ["Section 37\nRight to private and family life"]:
                return EmbeddingBatch(
                    provider="fake",
                    model_name=profile.model_name,
                    model_revision=profile.model_revision,
                    vectors=[[1.0] + [0.0] * 1023],
                    cost_usd=0.01,
                    metrics={"batch": "documents"},
                )
            assert texts == ["Which section protects privacy?"]
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023],
                cost_usd=0.02,
                metrics={"batch": "queries"},
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: FakeEmbeddingProvider(),
    )
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    run.pipeline_config = {"auto_start_embedding": True}
    db.add(run)
    db.commit()
    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=embedding_step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:pgvector-embedding",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.EMBEDDING,
        IngestionStage.INDEXING,
        IngestionStage.VALIDATING_INDEX,
    ]
    db.refresh(run)
    db.refresh(release)
    assert run.status == IngestionRunStatus.READY_TO_PUBLISH
    assert run.current_stage == IngestionStage.PUBLISHING
    assert release.embedding_model == "fake-large"
    assert release.embedding_model_version == "pinned-test"
    assert release.validation_report

    embedding_run = db.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.profile_id == profile.id,
        )
    ).one()
    assert embedding_run.status == EmbeddingRunStatus.SUCCEEDED
    assert embedding_run.selected_for_release
    assert embedding_run.recall_at_10 == 1
    assert embedding_run.ndcg_at_10 == 1
    assert embedding_run.cost_usd == 0.03
    assert (
        embedding_run.benchmark_dataset_version
        == profile.configuration["benchmark_dataset_version"]
    )
    assert embedding_run.metrics
    assert embedding_run.metrics["benchmark_query_count"] == 1
    assert embedding_run.metrics["document_embedding_metrics"] == {"batch": "documents"}
    assert embedding_run.metrics["query_embedding_metrics"] == {"batch": "queries"}
    embedding_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).one()
    assert embedding_artifact.artifact_metadata
    assert embedding_artifact.artifact_metadata["embedding_run_id"] == str(
        embedding_run.id
    )
    artifact_payload = json.loads(
        LocalBlobStore(tmp_path).read_bytes(embedding_artifact.storage_key)
    )
    assert artifact_payload["benchmark"]["recall_at_10"] == 1
    assert artifact_payload["benchmark"]["benchmark_query_count"] == 1

    build = db.exec(
        select(RetrievalIndexBuild).where(RetrievalIndexBuild.release_id == release.id)
    ).one()
    assert build.status == VectorIndexStatus.READY
    assert build.stored_segment_count == 1
    assert build.stored_embedding_count == 1
    db.refresh(release)
    assert release.validation_report["unresolved_gates"] == ["unrelated_review_gate"]
    segment = db.exec(
        select(RetrievalSegment).where(RetrievalSegment.release_id == release.id)
    ).one()
    embedding = db.exec(
        select(RetrievalEmbedding).where(
            RetrievalEmbedding.embedding_run_id == build.embedding_run_id
        )
    ).one()
    assert embedding.vector_dimensions == 1024
    assert (
        dense_search(
            db,
            release_id=release.id,
            embedding_run_id=build.embedding_run_id,
            query_vector=[1.0] + [0.0] * 1023,
        )[0][0].id
        == segment.id
    )
    assert (
        hybrid_search(
            db,
            release_id=release.id,
            embedding_run_id=build.embedding_run_id,
            query_vector=[1.0] + [0.0] * 1023,
            query="privacy",
            top_k=1,
        )[0].segment.id
        == segment.id
    )


def test_retrieval_documents_can_be_rebuilt_after_retrieval_text_changes(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, _profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)
    task = IngestionTask(
        run_id=run.id,
        task_type=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS.value,
        idempotency_key=f"{run.id}:building:rebuild",
        payload={"release_id": str(release.id)},
    )
    handle_building_retrieval_documents(db, run, task)
    monkeypatch.setattr(
        "app.ingestion.retrieval.retrieval_phrasing",
        lambda _path: "In plain words: privacy at home.",
    )

    # Changed search text produces a new artifact beside the first instead of
    # colliding with it in the immutable store.
    handle_building_retrieval_documents(db, run, task)

    artifacts = db.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type
            == IngestionArtifactType.RETRIEVAL_DOCUMENTS,
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).all()
    newest = json.loads(LocalBlobStore(tmp_path).read_bytes(artifacts[0].storage_key))
    assert (
        "In plain words: privacy at home." in (newest["documents"][0]["retrieval_text"])
    )
    assert len({artifact.storage_key for artifact in artifacts}) >= 2
