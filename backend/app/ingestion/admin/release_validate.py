import uuid

from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_payload_hash,
    idempotency_record_for_request,
    idempotency_scope,
)
from app.ingestion.admin.queries import check_expected_version, get_release
from app.ingestion.admin.release_gates import (
    release_source_and_review_gates,
    retrieval_index_build_validation_gates,
)
from app.ingestion.evaluation import (
    active_evaluation_item_count,
    benchmark_dataset_versions,
)
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
    VectorIndexStatus,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingRun,
    RetrievalIndexBuild,
)
from app.models import User

MIN_PUBLICATION_RECALL_AT_10 = 0.95


def validate_corpus_release(
    session: Session,
    release_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> CorpusRelease:
    scope = idempotency_scope("corpus_release.validate", release_id)
    request_hash = idempotency_payload_hash(
        {"expected_version": expected_version, "release_id": str(release_id)}
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_release(session, release_id)
    release = get_release(session, release_id)
    check_expected_version(release.lock_version, expected_version)
    entries = session.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    embedding_run = session.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.selected_for_release == True,  # noqa: E712
            EmbeddingRun.status == EmbeddingRunStatus.SUCCEEDED,
        )
    ).first()
    retrieval_index_build = None
    if embedding_run:
        retrieval_index_build = session.exec(
            select(RetrievalIndexBuild)
            .where(
                RetrievalIndexBuild.release_id == release.id,
                RetrievalIndexBuild.embedding_run_id == embedding_run.id,
                RetrievalIndexBuild.status == VectorIndexStatus.READY,
            )
            .order_by(col(RetrievalIndexBuild.updated_at).desc())
        ).first()
    unresolved_gates: list[str] = []
    benchmark_item_count: int | None = None
    if not entries:
        unresolved_gates.append("release_has_no_entries")
    unresolved_gates.extend(
        release_source_and_review_gates(session, entries, release=release)
    )
    if not embedding_run:
        unresolved_gates.append("selected_embedding_run_missing")
    elif (
        embedding_run.recall_at_10 is None
        or embedding_run.recall_at_10 < MIN_PUBLICATION_RECALL_AT_10
    ):
        unresolved_gates.append("selected_embedding_run_below_recall_threshold")
    if embedding_run and not embedding_run.benchmark_dataset_version:
        unresolved_gates.append("benchmark_dataset_version_missing")
    elif embedding_run and embedding_run.benchmark_dataset_version:
        dataset_counts = [
            active_evaluation_item_count(
                session,
                dataset_version,
                dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
                item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            )
            for dataset_version in benchmark_dataset_versions(
                embedding_run.benchmark_dataset_version
            )
        ]
        benchmark_item_count = sum(dataset_counts)
        if not dataset_counts or any(count <= 0 for count in dataset_counts):
            unresolved_gates.append("benchmark_dataset_missing_or_empty")
    if not retrieval_index_build:
        unresolved_gates.append("ready_retrieval_index_build_missing")
    else:
        unresolved_gates.extend(
            retrieval_index_build_validation_gates(retrieval_index_build)
        )

    release.validation_report = {
        **(release.validation_report or {}),
        "entry_count": len(entries),
        "selected_embedding_run_id": str(embedding_run.id) if embedding_run else None,
        "benchmark_dataset_version": (
            embedding_run.benchmark_dataset_version if embedding_run else None
        ),
        "benchmark_query_count": benchmark_item_count,
        "ready_retrieval_index_build_id": (
            str(retrieval_index_build.id) if retrieval_index_build else None
        ),
        "retrieval_backend": settings.RETRIEVAL_INDEX_BACKEND,
        "minimum_recall_at_10": MIN_PUBLICATION_RECALL_AT_10,
        "unresolved_gates": unresolved_gates,
    }
    release.status = (
        CorpusReleaseStatus.APPROVED
        if not unresolved_gates
        else CorpusReleaseStatus.VALIDATING
    )
    release.lock_version += 1
    session.add(release)
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="corpus_release",
        result_id=release.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(release)
    return release
