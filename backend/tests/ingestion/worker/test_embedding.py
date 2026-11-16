import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.service import (
    start_embedding,
)
from app.ingestion.worker import (
    IngestionWorkerError,
    _benchmark_dataset_for_embedding_profiles,
    _embed_with_checkpoints,
    handle_embedding,
    run_once,
    run_until_idle,
)
from app.ingestion.workflow import enqueue_task
from app.legal.enums import (
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    EvaluationItemKind,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    IngestionArtifact,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
)
from app.legal.parser import legal_text_sha256, normalize_legal_text
from tests.ingestion.worker.conftest import (
    _create_retrieval_benchmark_dataset,
    _release_with_retrieval_documents,
)
from tests.utils.user import create_random_user


def test_active_embedding_profiles_must_share_one_persisted_benchmark_dataset(
    db: Session,
) -> None:
    for existing_profile in db.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active == True)  # noqa: E712
    ).all():
        existing_profile.is_active = False
        db.add(existing_profile)
    dataset_version = f"golden-{uuid.uuid4().hex}"
    _create_retrieval_benchmark_dataset(
        db,
        version=dataset_version,
        canonical_path="constitution.1999.chapter4.section37",
    )
    openai_profile = EmbeddingProfile(
        name=f"openai-large-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="text-embedding-3-large",
        model_revision="pinned-openai",
        vector_dimensions=1024,
        configuration={"benchmark_dataset_version": dataset_version},
    )
    bge_profile = EmbeddingProfile(
        name=f"bge-m3-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
        model_name="BAAI/bge-m3",
        model_revision="pinned-bge",
        vector_dimensions=1024,
        configuration={"benchmark_dataset_version": dataset_version},
    )
    db.add_all([openai_profile, bge_profile])
    db.commit()

    release = CorpusRelease(version=f"draft-{uuid.uuid4().hex}")
    recorded, queries = _benchmark_dataset_for_embedding_profiles(
        db, [openai_profile, bge_profile], release
    )
    assert recorded == dataset_version
    assert [query.item_key for query in queries] == ["privacy-exact-reference"]

    bge_profile.configuration = {
        "benchmark_dataset_version": f"other-{uuid.uuid4().hex}"
    }
    db.add(bge_profile)
    db.commit()
    with pytest.raises(IngestionWorkerError, match="same benchmark dataset"):
        _benchmark_dataset_for_embedding_profiles(
            db, [openai_profile, bge_profile], release
        )


def test_embedding_benchmark_grades_each_release_instrument_with_its_own_dataset(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, _run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path, create_benchmark_dataset=False
    )
    constitution = db.get(LegalInstrument, source.legal_instrument_id)
    assert constitution
    pinned_version = str(profile.configuration["benchmark_dataset_version"])
    _create_retrieval_benchmark_dataset(
        db,
        version=pinned_version,
        canonical_path=f"{constitution.slug}.section37",
        instrument_slug=constitution.slug,
    )
    act = LegalInstrument(
        slug=f"act-{uuid.uuid4().hex[:12]}",
        title="Test Act",
        instrument_type=InstrumentType.ACT,
    )
    db.add(act)
    db.commit()
    act_provision = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SECTION,
        number="1",
        canonical_path=f"{act.slug}.section1",
        sort_key="001",
    )
    db.add(act_provision)
    db.commit()
    act_text = "This Act applies to criminal trials."
    act_version = ProvisionVersion(
        provision_id=act_provision.id,
        text=act_text,
        normalized_text=normalize_legal_text(act_text),
        valid_from=date(2015, 5, 13),
        legal_status=LegalStatus.HISTORICAL,
        source_document_id=source.id,
        text_sha256=legal_text_sha256(act_text),
    )
    db.add(act_version)
    db.commit()
    db.add(
        CorpusReleaseEntry(
            release_id=release.id,
            provision_version_id=act_version.id,
            source_document_id=source.id,
        )
    )
    db.commit()

    # An Act in the release without its own benchmark cannot be graded.
    with pytest.raises(IngestionWorkerError, match=f"{act.slug} needs exactly one"):
        _benchmark_dataset_for_embedding_profiles(db, [profile], release)

    act_version_name = f"act-golden-{uuid.uuid4().hex[:8]}"
    _create_retrieval_benchmark_dataset(
        db,
        version=act_version_name,
        canonical_path=act_provision.canonical_path,
        instrument_slug=act.slug,
    )

    recorded, queries = _benchmark_dataset_for_embedding_profiles(
        db, [profile], release
    )

    by_slug = {act.slug: act_version_name, constitution.slug: pinned_version}
    expected = [by_slug[slug] for slug in sorted(by_slug)]
    assert recorded == "+".join(expected)
    assert sorted(query.item_key for query in queries) == sorted(
        f"{version}/privacy-exact-reference" for version in expected
    )
    assert {path for query in queries for path in query.expected_canonical_paths} == {
        f"{constitution.slug}.section37",
        act_provision.canonical_path,
    }


def test_embedding_run_records_every_benchmark_of_a_composite_release(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, _run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path, create_benchmark_dataset=False
    )
    constitution = db.get(LegalInstrument, source.legal_instrument_id)
    assert constitution
    suffix = uuid.uuid4().hex[:8]
    versions = [
        f"{name}-{suffix}"
        for name in (
            "acja-2015-retrieval-v1",
            "constitution-source-edition-retrieval-2026-10-05-v1",
            "copyright-act-2022-retrieval-v1",
            "employees-compensation-act-2010-retrieval-v1",
            "nigeria-tax-act-2025-retrieval-v1",
            "police-act-2020-retrieval-v1",
        )
    ]
    for version in versions:
        _create_retrieval_benchmark_dataset(
            db, version=version, canonical_path=f"{constitution.slug}.section37"
        )
    pinned_version = str(profile.configuration["benchmark_dataset_version"])
    _create_retrieval_benchmark_dataset(
        db,
        version=pinned_version,
        canonical_path=f"{constitution.slug}.section37",
        instrument_slug=constitution.slug,
    )
    monkeypatch.setattr(
        "app.ingestion.worker._benchmark_versions_for_release",
        lambda *_args: versions,
    )

    recorded, queries = _benchmark_dataset_for_embedding_profiles(
        db, [profile], release
    )

    assert recorded == "+".join(versions)
    assert len(recorded) > 128
    assert len(queries) == len(versions)
    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        benchmark_dataset_version=recorded,
    )
    db.add(embedding_run)
    db.commit()
    db.refresh(embedding_run)
    assert embedding_run.benchmark_dataset_version == recorded

    monkeypatch.setattr(
        "app.ingestion.worker.RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH", len(recorded) - 1
    )
    with pytest.raises(IngestionWorkerError, match="too long to record"):
        _benchmark_dataset_for_embedding_profiles(db, [profile], release)


def test_worker_requires_persisted_embedding_benchmark_dataset(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, _profile = _release_with_retrieval_documents(
        db,
        tmp_path=tmp_path,
        create_benchmark_dataset=False,
    )

    class UnexpectedEmbeddingProvider:
        def embed(self, _texts: list[str]) -> EmbeddingBatch:
            raise AssertionError("Embedding provider should not run without a dataset")

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: UnexpectedEmbeddingProvider(),
    )
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    db.add(run)
    db.commit()
    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    task = enqueue_task(
        db,
        run=run,
        step=embedding_step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:embedding-missing-benchmark-dataset",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )
    task.max_attempts = 1
    db.add(task)
    db.commit()

    result = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.EMBEDDING.value,
    )

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "benchmark dataset" in run.error_details["message"]
    embedding_artifacts = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).all()
    assert embedding_artifacts == []


def test_embedding_rejects_active_profile_without_pinned_revision(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    profile.model_revision = None
    db.add(profile)
    db.commit()

    def _unexpected_provider(_profile: EmbeddingProfile) -> EmbeddingBatch:
        raise AssertionError("Provider must not run without a pinned revision")

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        _unexpected_provider,
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
        idempotency_key=f"{run.id}:embedding-unpinned",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )

    # Three attempts are exhausted (default max_attempts=3) before the
    # task and run reach FAILED.
    results = run_until_idle(db, worker_id="worker-test", max_tasks=4)

    assert results[-1].task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "pinned model_revision" in run.error_details["message"]


def test_embedding_honors_configured_batch_size(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    dataset_version = profile.configuration["benchmark_dataset_version"]
    dataset = db.exec(
        select(EvaluationDataset).where(EvaluationDataset.version == dataset_version)
    ).one()
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="citizenship-query",
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            query_text="Which section protects movement?",
            expected_canonical_paths=[f"{dataset_version}"],
        )
    )
    # Point the second query at the same provision so recall stays perfect.
    provision = db.exec(
        select(Provision).where(Provision.instrument_id == source.legal_instrument_id)
    ).one()
    second_query = db.exec(
        select(EvaluationItem).where(EvaluationItem.item_key == "citizenship-query")
    ).one()
    second_query.expected_canonical_paths = [provision.canonical_path]
    profile.configuration = {
        **profile.configuration,
        "batch_size": 1,
    }
    db.add_all([profile, second_query])
    db.commit()

    calls: list[list[str]] = []

    class RecordingEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            calls.append(list(texts))
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: RecordingEmbeddingProvider(),
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
        idempotency_key=f"{run.id}:embedding-batched",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=1)

    assert results[0].task_status == IngestionTaskStatus.SUCCEEDED
    # One document call plus one call per benchmark query.
    assert calls[0] == ["Section 37\nRight to private and family life"]
    assert sorted(calls[1:]) == [
        ["Which section protects movement?"],
        ["Which section protects privacy?"],
    ]
    embedding_run = db.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.profile_id == profile.id,
        )
    ).one()
    assert embedding_run.status == EmbeddingRunStatus.SUCCEEDED
    assert embedding_run.recall_at_10 == 1


def test_embedding_can_be_started_again_after_documents_are_rebuilt(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, _profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)
    actor = create_random_user(db)
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    db.add(run)
    db.commit()
    db.refresh(run)
    start_embedding(
        db,
        run.id,
        expected_version=run.lock_version,
        idempotency_key=f"start-{uuid.uuid4().hex}",
        current_user=actor,
    )
    first = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.EMBEDDING.value,
        )
    ).one()
    first.status = IngestionTaskStatus.FAILED
    # The run fails, its documents are rebuilt and it is ready to embed again.
    db.refresh(run)
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.lock_version += 1
    db.add_all([first, run])
    db.commit()
    db.refresh(run)

    start_embedding(
        db,
        run.id,
        expected_version=run.lock_version,
        idempotency_key=f"start-{uuid.uuid4().hex}",
        current_user=actor,
    )

    pending = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.EMBEDDING.value,
            IngestionTask.status == IngestionTaskStatus.PENDING,
        )
    ).one()
    assert pending.id != first.id
    assert pending.payload["release_id"] == str(release.id)


def test_embedding_can_be_rescored_after_its_benchmark_result_changes(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)

    class FakeEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: FakeEmbeddingProvider(),
    )
    item = db.exec(
        select(EvaluationItem)
        .join(EvaluationDataset)
        .where(
            EvaluationDataset.version
            == profile.configuration["benchmark_dataset_version"]
        )
    ).one()
    expected_paths = item.expected_canonical_paths
    item.expected_canonical_paths = [f"{expected_paths[0]}-elsewhere"]
    db.add(item)
    db.commit()
    task = IngestionTask(
        run_id=run.id,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:embedding:rescore",
        payload={"release_id": str(release.id)},
    )

    with pytest.raises(IngestionWorkerError, match="Recall@10"):
        handle_embedding(db, run, task)

    # The same vectors now score differently; the new artifact sits beside
    # the first instead of colliding with it in the immutable store.
    item.expected_canonical_paths = expected_paths
    db.add(item)
    db.commit()
    handle_embedding(db, run, task)

    embedding_run = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    assert embedding_run.status == EmbeddingRunStatus.SUCCEEDED
    assert embedding_run.recall_at_10 == 1.0
    assert embedding_run.selected_for_release is True
    artifacts = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).all()
    assert len({artifact.storage_key for artifact in artifacts}) == 2


def test_embedding_retry_reuses_completed_batches_and_invalidates_changed_inputs(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)
    embedding_run = EmbeddingRun(release_id=release.id, profile_id=profile.id)
    db.add(embedding_run)
    db.commit()
    calls: list[list[str]] = []

    class InterruptedProvider:
        failed = False

        def embed(self, texts: list[str]) -> EmbeddingBatch:
            calls.append(texts)
            if texts == ["second"] and not self.failed:
                self.failed = True
                raise RuntimeError("provider timeout")
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    provider = InterruptedProvider()
    arguments = {
        "run": run,
        "profile": profile,
        "embedding_run": embedding_run,
        "provider": provider,
        "batch_size": 1,
        "kind": "documents",
    }
    with pytest.raises(RuntimeError, match="provider timeout"):
        _embed_with_checkpoints(db, texts=["first", "second", "third"], **arguments)
    batch = _embed_with_checkpoints(db, texts=["first", "second", "third"], **arguments)
    assert calls == [["first"], ["second"], ["second"], ["third"]]
    assert len(batch.vectors) == 3
    _embed_with_checkpoints(db, texts=["changed", "second", "third"], **arguments)
    assert calls[-1] == ["changed"]
    assert len(calls) == 5
    assert embedding_run.metrics["documents_progress"]["completed"] == 3
