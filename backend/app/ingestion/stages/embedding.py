import hashlib
import json
from typing import Any

from sqlmodel import Session, col, select

from app.ingestion.common import get_datetime_utc
from app.ingestion.embedding import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DenseEmbeddingProvider,
    EmbeddingBatch,
    EmbeddingBenchmarkQuery,
    evaluate_embedding_benchmark,
    select_best_embedding_run,
)
from app.ingestion.embedding_reuse import member_document_vectors, profile_fingerprint
from app.ingestion.retrieval import build_retrieval_documents
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.inputs import retain_pipeline_inputs
from app.ingestion.runtime.types import StageOutcome
from app.ingestion.stages.artifacts import ensure_artifact, payload_list
from app.ingestion.stages.documents import retrieval_documents_payload
from app.ingestion.stages.embedding_checkpoints import embed_with_checkpoints
from app.ingestion.stages.embedding_profiles import (
    active_embedding_profiles,
    auto_start_embedding,
    benchmark_dataset_for_embedding_profiles,
    embedding_provider_for_profile,
    embedding_run_for_profile,
    profile_float,
    profile_int,
    sum_optional_costs,
)
from app.ingestion.stages.releases import (
    ensure_composite_member_gates,
    get_release_for_task,
    provisions_by_versions,
    release_entries,
    versions_by_release_entry,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    EmbeddingRunStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
)
from app.legal.models import (
    CorpusRelease,
    EmbeddingProfile,
    EmbeddingRun,
    IngestionRun,
    IngestionTask,
    LegalInstrument,
)


def handle_building_retrieval_documents(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    release = get_release_for_task(session, task)
    ensure_composite_member_gates(session, release)
    entries = release_entries(session, release.id)
    if not entries:
        raise IngestionWorkerError("Release does not have entries to index")
    versions_by_id = versions_by_release_entry(entries, session)
    provisions_by_id = provisions_by_versions(versions_by_id, session)
    retrieval_documents = build_retrieval_documents(
        release_version=release.version,
        entries=entries,
        versions_by_id=versions_by_id,
        provisions_by_id=provisions_by_id,
        instruments_by_id={
            instrument.id: instrument
            for instrument in session.exec(
                select(LegalInstrument).where(
                    col(LegalInstrument.id).in_(
                        {p.instrument_id for p in provisions_by_id.values()}
                    )
                )
            ).all()
        },
    )
    if not retrieval_documents:
        raise IngestionWorkerError("Release did not produce retrieval documents")
    payload = {
        "release_id": str(release.id),
        "release_version": release.version,
        "document_count": len(retrieval_documents),
        "documents": [document.to_json() for document in retrieval_documents],
    }
    content = json.dumps(payload, sort_keys=True).encode()
    # Artifacts are immutable: rebuilt documents (for example after a
    # retrieval-text change) are stored beside earlier ones, and readers take
    # the newest artifact for the release.
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS.value,
        filename=f"retrieval-documents-{release.version}-{content_hash}.json",
        content=content,
        content_type="application/json",
        metadata={"release_id": str(release.id)},
    )
    ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={
            "release_id": str(release.id),
            "document_count": len(retrieval_documents),
        },
    )
    release.validation_report = {
        **(release.validation_report or {}),
        "retrieval_document_count": len(retrieval_documents),
        "unresolved_gates": [
            "selected_embedding_run_missing",
            "ready_retrieval_index_build_missing",
        ],
    }
    release.lock_version += 1
    session.add(release)
    retain_pipeline_inputs(session, run, {"release_id": str(release.id)})
    session.commit()
    metrics = {
        "release_id": str(release.id),
        "release_version": release.version,
        "retrieval_document_count": len(retrieval_documents),
    }
    if auto_start_embedding(run) and active_embedding_profiles(session):
        return StageOutcome(
            metrics=metrics,
            next_stage=IngestionStage.EMBEDDING,
            next_task_payload={
                "source_document_id": str(run.source_document_id),
                "release_id": str(release.id),
            },
        )
    return StageOutcome(
        metrics=metrics,
        next_stage=IngestionStage.EMBEDDING,
        next_status=IngestionRunStatus.READY_TO_EMBED,
        block_next_stage=True,
    )


def handle_embedding(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    release = get_release_for_task(session, task)
    ensure_composite_member_gates(session, release)
    documents_payload = retrieval_documents_payload(session, run, release.id)
    documents = payload_list(documents_payload, "documents")
    texts = [str(document["retrieval_text"]) for document in documents]
    if not texts:
        raise IngestionWorkerError("Release does not have retrieval text to embed")
    profiles = active_embedding_profiles(session)
    if not profiles:
        raise IngestionWorkerError("No active embedding profiles are configured")
    benchmark_dataset_version, benchmark_queries = (
        benchmark_dataset_for_embedding_profiles(session, profiles, release)
    )

    embedding_runs: list[EmbeddingRun] = []
    for profile in profiles:
        if profile.is_active and not profile.model_revision:
            raise IngestionWorkerError(
                f"Embedding profile {profile.name} is active but has no pinned model_revision"
            )
        embedding_run = embedding_run_for_profile(session, release, profile)
        embedding_run.status = EmbeddingRunStatus.RUNNING
        embedding_run.started_at = embedding_run.started_at or get_datetime_utc()
        embedding_run.error_details = None
        session.add(embedding_run)
        session.commit()
        try:
            provider = embedding_provider_for_profile(profile)
            batch_size = profile_int(
                profile, "batch_size", default=DEFAULT_EMBEDDING_BATCH_SIZE
            )
            batch = embed_release_documents(
                session,
                release=release,
                documents=documents,
                run=run,
                profile=profile,
                embedding_run=embedding_run,
                provider=provider,
                batch_size=batch_size,
            )
            if batch.dimensions != profile.vector_dimensions:
                raise IngestionWorkerError(
                    "Embedding vector dimensions do not match the profile"
                )
            query_batch = embed_with_checkpoints(
                session,
                run=run,
                profile=profile,
                embedding_run=embedding_run,
                provider=provider,
                texts=[query.query_text for query in benchmark_queries],
                batch_size=batch_size,
                kind="queries",
            )
            if query_batch.dimensions != profile.vector_dimensions:
                raise IngestionWorkerError(
                    "Benchmark query vector dimensions do not match the profile"
                )
            benchmark = evaluate_embedding_benchmark(
                documents=documents,
                document_vectors=batch.vectors,
                queries=[
                    EmbeddingBenchmarkQuery(
                        item_key=query.item_key,
                        query_text=query.query_text,
                        expected_canonical_paths=query.expected_canonical_paths,
                    )
                    for query in benchmark_queries
                ],
                query_vectors=query_batch.vectors,
            )
            artifact_payload: dict[str, Any] = {
                "release_id": str(release.id),
                "release_version": release.version,
                "embedding_run_id": str(embedding_run.id),
                "profile_id": str(profile.id),
                "provider": profile.provider,
                "model_name": profile.model_name,
                "model_revision": profile.model_revision,
                "benchmark": benchmark.to_metrics(),
                "documents": documents,
                "dense_vectors": batch.vectors,
            }
            content = json.dumps(artifact_payload, sort_keys=True).encode()
            # Artifacts are immutable, so a re-scored run (same vectors, new
            # benchmark result) is stored beside the earlier one, not over it.
            # Readers take the newest artifact for the embedding run.
            content_hash = hashlib.sha256(content).hexdigest()[:16]
            blob = get_blob_store().put_artifact(
                run_id=str(run.id),
                artifact_type=IngestionArtifactType.EMBEDDINGS.value,
                filename=f"embeddings-{profile.name}-{content_hash}.json",
                content=content,
                content_type="application/json",
                metadata={
                    "release_id": str(release.id),
                    "embedding_run_id": str(embedding_run.id),
                    "profile_id": str(profile.id),
                },
            )
            ensure_artifact(
                session,
                run_id=run.id,
                artifact_type=IngestionArtifactType.EMBEDDINGS,
                storage_key=blob.key,
                sha256=blob.sha256,
                mime_type=blob.content_type,
                metadata={
                    "release_id": str(release.id),
                    "embedding_run_id": str(embedding_run.id),
                    "profile_id": str(profile.id),
                    "document_count": len(documents),
                    "vector_dimensions": batch.dimensions,
                },
            )
            embedding_run.status = EmbeddingRunStatus.SUCCEEDED
            embedding_run.completed_at = get_datetime_utc()
            embedding_run.benchmark_dataset_version = benchmark_dataset_version
            embedding_run.recall_at_10 = benchmark.recall_at_10
            embedding_run.ndcg_at_10 = benchmark.ndcg_at_10
            reported_cost = sum_optional_costs(batch.cost_usd, query_batch.cost_usd)
            embedding_run.cost_usd = (
                reported_cost
                if reported_cost is not None
                else profile_float(profile, "estimated_cost_usd")
            )
            embedding_run.p95_latency_ms = profile_float(profile, "p95_latency_ms")
            embedding_run.metrics = {
                "profile_fingerprint": profile_fingerprint(profile),
                "document_embedding_metrics": batch.metrics or {},
                "query_embedding_metrics": query_batch.metrics or {},
                "benchmark_dataset_version": benchmark_dataset_version,
                **benchmark.to_metrics(),
                "document_count": len(documents),
                "vector_dimensions": batch.dimensions,
                "sparse_vector_count": 0,
            }
        except Exception as exc:
            embedding_run.status = EmbeddingRunStatus.FAILED
            embedding_run.completed_at = get_datetime_utc()
            embedding_run.error_details = {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
        session.add(embedding_run)
        session.commit()
        session.refresh(embedding_run)
        embedding_runs.append(embedding_run)

    selected_run = select_best_embedding_run(embedding_runs)
    if not selected_run:
        failures = [item.error_details for item in embedding_runs if item.error_details]
        if failures:
            raise IngestionWorkerError(
                f"Embedding provider failures: {json.dumps(failures)}"
            )
        raise IngestionWorkerError(
            "No embedding run reached the Recall@10 publication threshold"
        )
    selected_run.selected_for_release = True
    selected_profile = session.get(EmbeddingProfile, selected_run.profile_id)
    if not selected_profile:
        raise IngestionWorkerError("Selected embedding profile was not found")
    release.embedding_model = selected_profile.model_name
    release.embedding_model_version = selected_profile.model_revision
    release.validation_report = {
        **(release.validation_report or {}),
        "selected_embedding_run_id": str(selected_run.id),
        "embedding_profile_id": str(selected_profile.id),
        "unresolved_gates": [
            *[
                gate
                for gate in (release.validation_report or {}).get(
                    "unresolved_gates", []
                )
                if gate
                not in {
                    "selected_embedding_run_missing",
                    "retrieval_documents_pending",
                    "ready_retrieval_index_build_missing",
                    "ready_vector_index_missing",
                }
            ],
            "ready_retrieval_index_build_missing",
        ],
    }
    release.lock_version += 1
    session.add(selected_run)
    session.add(release)
    retain_pipeline_inputs(
        session,
        run,
        {"release_id": str(release.id), "embedding_run_id": str(selected_run.id)},
    )
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "embedding_run_count": len(embedding_runs),
            "selected_embedding_run_id": str(selected_run.id),
            "selected_model": selected_profile.model_name,
        },
        next_stage=IngestionStage.INDEXING,
        next_status=IngestionRunStatus.INDEXING,
        next_task_payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release.id),
            "embedding_run_id": str(selected_run.id),
        },
    )


def embed_release_documents(
    session: Session,
    *,
    release: CorpusRelease,
    documents: list[dict[str, Any]],
    run: IngestionRun,
    profile: EmbeddingProfile,
    embedding_run: EmbeddingRun,
    provider: DenseEmbeddingProvider,
    batch_size: int,
) -> EmbeddingBatch:
    if not (release.validation_report or {}).get("composition"):
        return embed_with_checkpoints(
            session,
            run=run,
            profile=profile,
            embedding_run=embedding_run,
            provider=provider,
            texts=[str(document["retrieval_text"]) for document in documents],
            batch_size=batch_size,
            kind="documents",
        )
    reusable = member_document_vectors(session, release, profile, documents)
    positions = [index for index in range(len(documents)) if index not in reusable]
    batch = (
        embed_with_checkpoints(
            session,
            run=run,
            profile=profile,
            embedding_run=embedding_run,
            provider=provider,
            texts=[str(documents[index]["retrieval_text"]) for index in positions],
            batch_size=batch_size,
            kind="documents",
        )
        if positions
        else EmbeddingBatch(
            provider=str(profile.provider),
            model_name=profile.model_name,
            model_revision=profile.model_revision,
            vectors=[],
            cost_usd=0,
        )
    )
    if len(batch.vectors) != len(positions):
        raise IngestionWorkerError(
            "Embedding vector count differs from missing documents"
        )
    values = {**reusable, **dict(zip(positions, batch.vectors, strict=True))}
    return EmbeddingBatch(
        provider=batch.provider,
        model_name=batch.model_name,
        model_revision=batch.model_revision,
        vectors=[values[index] for index in range(len(documents))],
        cost_usd=batch.cost_usd,
        metrics={
            **(batch.metrics or {}),
            "reused_document_count": len(reusable),
            "new_document_count": len(positions),
        },
    )
