import difflib
import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from app.ingestion.common import get_datetime_utc
from app.ingestion.text_alignment import compact_text
from app.ingestion.validation import has_unbalanced_punctuation
from app.legal.enums import (
    ExtractionCandidateStatus,
    PageInclusionStatus,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.models import (
    CandidateRevision,
    ExtractionCandidate,
    IngestionRun,
    ReviewIssue,
    SourcePage,
)
from app.models import User


def latest_candidate_revision(
    session: Session, candidate_id: uuid.UUID
) -> CandidateRevision | None:
    return session.exec(
        select(CandidateRevision)
        .where(CandidateRevision.candidate_id == candidate_id)
        .order_by(col(CandidateRevision.revision_number).desc())
    ).first()


def line_diff(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
        )
    )


def candidate_snapshot(
    candidate: ExtractionCandidate, revised_text: str | None
) -> dict[str, object]:
    return {
        "heading": candidate.heading,
        "kind": str(candidate.kind),
        "number": candidate.number,
        "parent_candidate_id": (
            str(candidate.parent_candidate_id)
            if candidate.parent_candidate_id
            else None
        ),
        "canonical_path": candidate.canonical_path,
        "sort_key": candidate.sort_key,
        "source_page_start": candidate.source_page_start,
        "source_page_end": candidate.source_page_end,
        "source_spans": candidate.source_spans,
        "revised_text": revised_text,
    }


def has_open_blocking_issue(session: Session, candidate_id: uuid.UUID) -> bool:
    issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate_id,
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    return issue is not None


def revalidate_candidate_revision_text(
    session: Session,
    *,
    candidate: ExtractionCandidate,
    revised_text: str,
    current_user: User,
) -> None:
    run = session.get(IngestionRun, candidate.run_id)
    if (
        run
        and (run.pipeline_config or {}).get("review_import_complete")
        and not (run.pipeline_config or {}).get("provisional_page_boundaries", True)
    ):
        included = set(
            session.exec(
                select(SourcePage.page_number).where(
                    SourcePage.run_id == candidate.run_id,
                    SourcePage.inclusion_status == PageInclusionStatus.INCLUDED,
                )
            ).all()
        )
        revalidate_review_page_coverage(session, candidate, included, current_user)
    open_revision_issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "revision_unbalanced_punctuation",
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    open_extraction_issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "unbalanced_punctuation",
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    if has_unbalanced_punctuation(revised_text):
        if open_extraction_issue and open_revision_issue:
            open_revision_issue.status = ReviewIssueStatus.RESOLVED
            open_revision_issue.resolved_by = current_user.id
            open_revision_issue.resolved_at = get_datetime_utc()
            open_revision_issue.resolution_reason = "Duplicate punctuation finding; the extraction-time blocker remains open."
            open_revision_issue.resolution_evidence = {
                "duplicate_of": str(open_extraction_issue.id),
                "revision_number": candidate.revision_number,
            }
            session.add(open_revision_issue)
        elif not open_revision_issue and not open_extraction_issue:
            session.add(
                ReviewIssue(
                    candidate_id=candidate.id,
                    issue_type="revision_unbalanced_punctuation",
                    severity=ReviewIssueSeverity.BLOCKING,
                    status=ReviewIssueStatus.OPEN,
                    blocking=True,
                    message="Revised candidate text has unbalanced punctuation.",
                    evidence={"canonical_path": candidate.canonical_path},
                )
            )
    # Revalidate the current revision, including extraction-time findings.
    # Exact source-character agreement can clear an obsolete coverage finding
    # without waiving the provenance gate or changing the immutable raw text.
    compact_revision, _ = compact_text(revised_text)
    source_text = "\n".join(
        str(span.get("text") or "") for span in candidate.source_spans or []
    )
    spans_have_coordinates = bool(candidate.source_spans) and all(
        all(key in (span.get("bbox") or {}) for key in ("x0", "y0", "x1", "y1"))
        for span in candidate.source_spans or []
    )
    exact_source_match = (
        bool(compact_revision)
        and spans_have_coordinates
        and (compact_revision == compact_text(source_text)[0])
    )
    for issue in session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).all():
        repaired_punctuation = issue.issue_type in {
            "unbalanced_punctuation",
            "revision_unbalanced_punctuation",
        } and not has_unbalanced_punctuation(revised_text)
        repaired_coverage = (
            issue.issue_type in {"missing_source_spans", "source_span_coverage"}
            and exact_source_match
        )
        if repaired_punctuation or repaired_coverage:
            issue.status = ReviewIssueStatus.RESOLVED
            issue.resolved_by = current_user.id
            issue.resolved_at = get_datetime_utc()
            issue.resolution_reason = (
                "Finding cleared by candidate revision revalidation."
            )
            issue.resolution_evidence = {
                "revision_number": candidate.revision_number,
                "exact_source_character_match": exact_source_match,
                "punctuation_balanced": not has_unbalanced_punctuation(revised_text),
            }
            session.add(issue)
    session.flush()
    candidate.blocking_issue_count = open_blocking_issue_count(session, candidate.id)
    session.add(candidate)


def open_blocking_issue_count(session: Session, candidate_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(ReviewIssue)
        .where(
            ReviewIssue.candidate_id == candidate_id,
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).one()


def revalidate_review_page_coverage(
    session: Session,
    candidate: ExtractionCandidate,
    included: set[int],
    current_user: User,
) -> None:
    pages: set[int | None] = set(
        range(
            candidate.source_page_start or 1,
            (candidate.source_page_end or candidate.source_page_start or 1) + 1,
        )
    )
    for span in candidate.source_spans or []:
        page = span.get("page_number", span.get("page"))
        pages.add(
            page if isinstance(page, int) and not isinstance(page, bool) else None
        )
    invalid = pages - included
    issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "excluded_source_page",
        )
    ).first()
    if invalid:
        if issue is None:
            issue = ReviewIssue(
                candidate_id=candidate.id,
                issue_type="excluded_source_page",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate source mapping includes excluded or unknown pages.",
            )
        issue.status = ReviewIssueStatus.OPEN
        issue.evidence = {
            "excluded_or_unknown_pages": sorted(str(page) for page in invalid)
        }
        issue.resolved_by = None
        issue.resolved_at = None
        session.add(issue)
    elif issue and issue.status == ReviewIssueStatus.OPEN:
        issue.status = ReviewIssueStatus.RESOLVED
        issue.resolved_by = current_user.id
        issue.resolved_at = get_datetime_utc()
        issue.resolution_reason = (
            "Current candidate mapping uses only confirmed included source pages."
        )
        issue.resolution_evidence = {"revision_number": candidate.revision_number}
        session.add(issue)


def live_review_candidates(
    session: Session, run_id: uuid.UUID
) -> list[ExtractionCandidate]:
    # Rejected candidates (duplicate scans, junk fragments) are a final review
    # decision: they are never materialized and their findings do not block.
    return list(
        session.exec(
            select(ExtractionCandidate).where(
                ExtractionCandidate.run_id == run_id,
                ExtractionCandidate.status != ExtractionCandidateStatus.REJECTED,
            )
        ).all()
    )


def review_candidates_ready_for_materialization(
    session: Session, candidates: Sequence[ExtractionCandidate]
) -> bool:
    if not candidates:
        return False
    if any(
        item.status
        not in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.AUTO_APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }
        for item in candidates
    ):
        return False
    candidate_ids = [item.id for item in candidates]
    unresolved_blocking_issue = session.exec(
        select(ReviewIssue).where(
            col(ReviewIssue.candidate_id).in_(candidate_ids),
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    return unresolved_blocking_issue is None
