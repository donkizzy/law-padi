import uuid
from typing import Any, cast

from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.common import get_datetime_utc
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
    validate_index_build,
    write_embeddings,
    write_segments,
)
from app.ingestion.retrieval import RetrievalDocument
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.inputs import retain_pipeline_inputs, task_input
from app.ingestion.runtime.types import StageOutcome
from app.ingestion.stages.artifacts import (
    float_vector,
    json_object,
    latest_artifact_with_metadata,
    payload_list,
    sha256_json,
)
from app.ingestion.stages.releases import (
    ensure_composite_member_gates,
    get_release_for_task,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    EmbeddingRunStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    VectorIndexStatus,
)
from app.legal.models import (
    CorpusRelease,
    EmbeddingProfile,
    EmbeddingRun,
    IngestionRun,
    IngestionTask,
    RetrievalIndexBuild,
)


def handle_indexing(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    release = get_release_for_task(session, task)
    ensure_composite_member_gates(session, release)
    embedding_run = get_embedding_run_for_task(session, task)
    profile = session.get(EmbeddingProfile, embedding_run.profile_id)
    if not profile:
        raise IngestionWorkerError("Embedding run is missing its profile")
    return handle_pgvector_indexing(
        session,
        run=run,
        release=release,
        embedding_run=embedding_run,
        profile=profile,
    )


def handle_pgvector_indexing(
    session: Session,
    *,
    run: IngestionRun,
    release: CorpusRelease,
    embedding_run: EmbeddingRun,
    profile: EmbeddingProfile,
) -> StageOutcome:
    if embedding_run.status != EmbeddingRunStatus.SUCCEEDED:
        raise IngestionWorkerError(
            "Only a succeeded embedding run may be loaded into pgvector"
        )
    if profile.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        raise IngestionWorkerError(
            "The active embedding profile dimensions do not match the retrieval schema"
        )
    payload = embedding_payload(session, run, embedding_run.id)
    documents_payload = payload_list(payload, "documents")
    vectors = payload.get("dense_vectors")
    if not isinstance(vectors, list):
        raise IngestionWorkerError("Embedding artifact did not contain dense vectors")
    documents: list[RetrievalDocument] = []
    for item in documents_payload:
        raw_payload = item.get("payload")
        if not isinstance(raw_payload, dict):
            raise IngestionWorkerError("Retrieval document payload was invalid")
        documents.append(
            RetrievalDocument(
                document_id=str(item.get("id", "")),
                segment_id=str(item.get("segment_id", "")),
                release_version=str(item.get("release_version", release.version)),
                citation=str(item.get("citation", "")),
                ancestor_headings=[
                    str(value) for value in item.get("ancestor_headings", [])
                ],
                heading=(
                    str(item["heading"]) if item.get("heading") is not None else None
                ),
                authoritative_text=str(item.get("authoritative_text", "")),
                retrieval_text=str(item.get("retrieval_text", "")),
                payload=cast(dict[str, object], raw_payload),
            )
        )
    index_kind = index_kind_for_documents(documents)
    try:
        segments = write_segments(
            session,
            release_id=release.id,
            documents=documents,
            index_kind=index_kind,
        )
        vector_values = [
            float_vector(value) if isinstance(value, list) else [] for value in vectors
        ]
        embeddings = write_embeddings(
            session,
            release_id=release.id,
            embedding_run=embedding_run,
            profile=profile,
            segments=segments,
            vectors=vector_values,
        )
    except PgVectorRetrievalError as exc:
        raise IngestionWorkerError(str(exc)) from exc
    profile_hash = sha256_json(
        {
            "name": profile.name,
            "model_name": profile.model_name,
            "model_revision": profile.model_revision,
            "configuration": profile.configuration,
        }
    )
    build = session.exec(
        select(RetrievalIndexBuild).where(
            RetrievalIndexBuild.release_id == release.id,
            RetrievalIndexBuild.embedding_run_id == embedding_run.id,
            RetrievalIndexBuild.index_kind == index_kind,
        )
    ).first()
    if build is None:
        build = RetrievalIndexBuild(
            release_id=release.id,
            embedding_run_id=embedding_run.id,
            profile_id=profile.id,
            backend="pgvector",
            index_kind=index_kind,
            expected_segment_count=len(documents),
            vector_dimensions=profile.vector_dimensions,
            profile_hash=profile_hash,
        )
    elif build.status in {VectorIndexStatus.READY, VectorIndexStatus.PROMOTED}:
        raise IngestionWorkerError("A ready pgvector build is immutable")
    build.expected_segment_count = len(documents)
    build.stored_segment_count = len(segments)
    build.stored_embedding_count = len(embeddings)
    build.profile_hash = profile_hash
    build.vector_dimensions = profile.vector_dimensions
    build.status = VectorIndexStatus.VALIDATING
    build.updated_at = get_datetime_utc()
    build.validation_report = {
        "backend": "pgvector",
        "index_kind": index_kind,
        "exact_search": True,
        "candidate_limits": {
            "dense": settings.RETRIEVAL_DENSE_CANDIDATE_LIMIT,
            "lexical": settings.RETRIEVAL_LEXICAL_CANDIDATE_LIMIT,
        },
    }
    session.add(build)
    session.flush()
    retain_pipeline_inputs(
        session,
        run,
        {
            "release_id": str(release.id),
            "embedding_run_id": str(embedding_run.id),
            "retrieval_index_build_id": str(build.id),
        },
    )
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "retrieval_index_build_id": str(build.id),
            "backend": "pgvector",
            "index_kind": index_kind,
            "segment_count": len(segments),
            "embedding_count": len(embeddings),
        },
        next_stage=IngestionStage.VALIDATING_INDEX,
        next_status=IngestionRunStatus.INDEXING,
        next_task_payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release.id),
            "retrieval_index_build_id": str(build.id),
        },
    )


def handle_validating_index(
    session: Session, _run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    retrieval_index_build_id = task_input(session, task, "retrieval_index_build_id")
    if not retrieval_index_build_id:
        raise IngestionWorkerError("Task does not identify a retrieval index build")
    build = session.get(RetrievalIndexBuild, uuid.UUID(str(retrieval_index_build_id)))
    if not build:
        raise IngestionWorkerError("Retrieval index build was not found")
    report = validate_index_build(
        session,
        build=build,
        expected_segment_count=build.expected_segment_count,
    )
    build.validation_report = report
    build.stored_segment_count = int(report["stored_segment_count"])
    build.stored_embedding_count = int(report["stored_embedding_count"])
    build.checksum = sha256_json(
        {
            "segment_checksum": report["segment_checksum"],
            "embedding_checksum": report["embedding_checksum"],
        }
    )
    if not report["is_valid"]:
        build.status = VectorIndexStatus.FAILED
        session.add(build)
        session.commit()
        raise IngestionWorkerError("pgvector validation did not pass")
    build.status = VectorIndexStatus.READY
    build.updated_at = get_datetime_utc()
    session.add(build)
    release = session.get(CorpusRelease, build.release_id)
    if release:
        release.validation_report = {
            **(release.validation_report or {}),
            "ready_retrieval_index_build_id": str(build.id),
            "unresolved_gates": [
                gate
                for gate in (release.validation_report or {}).get(
                    "unresolved_gates", []
                )
                if gate != "ready_retrieval_index_build_missing"
            ],
        }
        release.lock_version += 1
        session.add(release)
    session.commit()
    return StageOutcome(
        metrics={
            "retrieval_index_build_id": str(build.id),
            "segment_count": build.stored_segment_count,
            "embedding_count": build.stored_embedding_count,
            "checksum": build.checksum,
        },
        next_stage=IngestionStage.PUBLISHING,
        next_status=IngestionRunStatus.READY_TO_PUBLISH,
        block_next_stage=True,
    )


def embedding_payload(
    session: Session, run: IngestionRun, embedding_run_id: uuid.UUID
) -> dict[str, Any]:
    artifact = latest_artifact_with_metadata(
        session,
        run=run,
        artifact_type=IngestionArtifactType.EMBEDDINGS,
        key="embedding_run_id",
        value=str(embedding_run_id),
    )
    if not artifact:
        raise IngestionWorkerError("Run does not have embedding artifacts")
    return json_object(get_blob_store().read_bytes(artifact.storage_key))


def get_embedding_run_for_task(session: Session, task: IngestionTask) -> EmbeddingRun:
    embedding_run_id = task_input(session, task, "embedding_run_id")
    if not embedding_run_id:
        raise IngestionWorkerError("Task does not identify an embedding run")
    embedding_run = session.get(EmbeddingRun, uuid.UUID(str(embedding_run_id)))
    if not embedding_run:
        raise IngestionWorkerError("Embedding run was not found")
    return embedding_run


def index_kind_for_documents(documents: list[RetrievalDocument]) -> str:
    kinds = {
        str(document.payload.get("legal_status", "")).lower() for document in documents
    }
    if kinds and kinds <= {"proposed"}:
        return "proposals"
    return "enacted"
