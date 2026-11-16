import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.composition import (
    composition_gates,
)
from app.legal.enums import (
    ExtractionCandidateStatus,
    ReviewIssueStatus,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    ExtractionCandidate,
    RetrievalIndexBuild,
    ReviewIssue,
    SourceDocument,
)


def release_source_and_review_gates(
    session: Session,
    entries: Sequence[CorpusReleaseEntry],
    *,
    release: CorpusRelease | None = None,
) -> list[str]:
    """Recheck mutable source/review state immediately before approval/publication."""
    gates: list[str] = composition_gates(session, release, entries) if release else []
    source_ids = {
        entry.source_document_id for entry in entries if entry.source_document_id
    }
    sources = (
        session.exec(
            select(SourceDocument).where(col(SourceDocument.id).in_(source_ids))
        ).all()
        if source_ids
        else []
    )
    if len(sources) != len(source_ids):
        gates.append("release_source_missing")
    if any(
        source.verification_status != VerificationStatus.VERIFIED for source in sources
    ):
        gates.append("release_source_not_verified")

    run_ids = {entry.ingestion_run_id for entry in entries if entry.ingestion_run_id}
    if not run_ids:
        return gates
    # Rejected candidates are a final review decision and are never released,
    # as in the review and materialization gates.
    candidates = session.exec(
        select(ExtractionCandidate).where(
            col(ExtractionCandidate.run_id).in_(run_ids),
            ExtractionCandidate.status != ExtractionCandidateStatus.REJECTED,
        )
    ).all()
    if any(
        candidate.status
        not in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.AUTO_APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }
        for candidate in candidates
    ):
        gates.append("release_candidate_not_approved")
    candidate_ids = [candidate.id for candidate in candidates]
    if candidate_ids:
        blocking_issue = session.exec(
            select(ReviewIssue).where(
                col(ReviewIssue.candidate_id).in_(candidate_ids),
                ReviewIssue.blocking == True,  # noqa: E712
                ReviewIssue.status == ReviewIssueStatus.OPEN,
            )
        ).first()
        if blocking_issue:
            gates.append("release_blocking_review_issue_open")
    return gates


def ready_retrieval_index_build(
    session: Session, release_id: uuid.UUID
) -> RetrievalIndexBuild | None:
    builds = session.exec(
        select(RetrievalIndexBuild)
        .where(
            RetrievalIndexBuild.release_id == release_id,
            RetrievalIndexBuild.status == VectorIndexStatus.READY,
        )
        .order_by(col(RetrievalIndexBuild.updated_at).desc())
    ).all()
    for build in builds:
        if not retrieval_index_build_validation_gates(build):
            return build
    return None


def retrieval_index_build_validation_gates(
    build: RetrievalIndexBuild,
) -> list[str]:
    gates: list[str] = []
    report = build.validation_report or {}
    if build.backend != "pgvector":
        gates.append("retrieval_index_backend_mismatch")
    if build.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        gates.append("retrieval_index_vector_dimensions_mismatch")
    if build.expected_segment_count <= 0:
        gates.append("retrieval_index_has_no_expected_segments")
    if build.stored_segment_count != build.expected_segment_count:
        gates.append("retrieval_index_segment_count_mismatch")
    if build.stored_embedding_count != build.expected_segment_count:
        gates.append("retrieval_index_embedding_count_mismatch")
    if not build.profile_hash:
        gates.append("retrieval_index_profile_hash_missing")
    if not build.checksum:
        gates.append("retrieval_index_checksum_missing")
    if report.get("is_valid") is not True:
        gates.append("retrieval_index_local_validation_missing")
    if report.get("vector_dimensions") != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        gates.append("retrieval_index_report_dimensions_mismatch")
    if report.get("lexical_smoke_query_supported") is not True:
        gates.append("retrieval_index_lexical_validation_missing")
    return gates
