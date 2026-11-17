import uuid

from sqlmodel import Session, select

from app.core.errors import DomainError, ErrorCode
from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_record_for_request,
    idempotency_request_hash,
    idempotency_scope,
)
from app.ingestion.admin.queries import check_expected_version, get_candidate
from app.ingestion.admin.review_completion import (
    maybe_complete_review_and_queue_materialization,
)
from app.ingestion.admin.review_validation import (
    candidate_snapshot,
    has_open_blocking_issue,
    latest_candidate_revision,
    line_diff,
    open_blocking_issue_count,
    revalidate_candidate_revision_text,
)
from app.ingestion.common import get_datetime_utc
from app.legal.enums import (
    AuditSeverity,
    ExtractionCandidateStatus,
    IngestionRunStatus,
    ReviewDecisionType,
    ReviewIssueStatus,
)
from app.legal.models import (
    AuditEvent,
    CandidateRevision,
    ExtractionCandidate,
    IngestionRun,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
)
from app.legal.schemas import (
    ReviewDecisionCreate,
    ReviewIssueUpdate,
    ReviewItemDerive,
    ReviewItemUpdate,
)
from app.models import User


def update_review_candidate(
    session: Session,
    candidate_id: uuid.UUID,
    body: ReviewItemUpdate,
    current_user: User,
) -> CandidateRevision:
    scope = idempotency_scope("review_item.update", candidate_id)
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        revision = (
            session.get(CandidateRevision, record.result_id)
            if record.result_id
            else None
        )
        if not revision:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Idempotent review revision result is no longer available",
            )
        return revision
    candidate = get_candidate(session, candidate_id)
    check_expected_version(candidate.lock_version, body.expected_version)
    validate_review_patch(session, candidate, body)
    latest_revision = latest_candidate_revision(session, candidate.id)
    previous_text = (
        latest_revision.revised_text if latest_revision else candidate.raw_text
    )
    next_text = body.revised_text if body.revised_text is not None else previous_text
    before_snapshot = candidate_snapshot(candidate, previous_text)
    changed_fields: dict[str, object] = {}
    json_patch = body.model_dump(mode="json", exclude_unset=True)
    for field_name in (
        "heading",
        "kind",
        "number",
        "parent_candidate_id",
        "canonical_path",
        "sort_key",
        "source_page_start",
        "source_page_end",
        "source_spans",
    ):
        value = getattr(body, field_name)
        if field_name in body.model_fields_set:
            setattr(candidate, field_name, value)
            changed_fields[field_name] = json_patch[field_name]
    after_snapshot = candidate_snapshot(candidate, next_text)
    for field_name, after_value in after_snapshot.items():
        before_value = before_snapshot.get(field_name)
        if before_value != after_value:
            changed_fields.setdefault(
                field_name, {"before": before_value, "after": after_value}
            )
    revision_number = (latest_revision.revision_number if latest_revision else 1) + 1
    revision = CandidateRevision(
        candidate_id=candidate.id,
        revision_number=revision_number,
        previous_text=previous_text,
        revised_text=next_text,
        diff=line_diff(previous_text or "", next_text or ""),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        changed_fields=changed_fields,
        reason=body.reason,
        revised_by=current_user.id,
    )
    candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
    candidate.revision_number = revision_number
    candidate.lock_version += 1
    candidate.updated_at = get_datetime_utc()
    session.add(revision)
    session.add(candidate)
    session.flush()
    revalidate_candidate_revision_text(
        session,
        candidate=candidate,
        revised_text=next_text or "",
        current_user=current_user,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="candidate_revision",
        result_id=revision.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(revision)
    return revision


def derive_review_candidate(
    session: Session,
    candidate_id: uuid.UUID,
    body: ReviewItemDerive,
    current_user: User,
) -> ExtractionCandidate:
    scope = idempotency_scope("review_item.derive", candidate_id)
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record and record.result_id:
        return get_candidate(session, record.result_id)
    original = get_candidate(session, candidate_id)
    check_expected_version(original.lock_version, body.expected_version)
    if (
        original.materialized_version_id
        or original.status == ExtractionCandidateStatus.MATERIALIZED
    ):
        raise DomainError(
            ErrorCode.CONFLICT, "Derive from an unmaterialized review candidate"
        )
    candidate = ExtractionCandidate(
        run_id=original.run_id,
        source_document_id=original.source_document_id,
        kind=body.kind,
        number=body.number,
        heading=body.heading,
        parent_candidate_id=body.parent_candidate_id,
        canonical_path=body.canonical_path,
        sort_key=body.sort_key,
        # A recovered structural heading must not inherit its origin's body.
        # The original extraction is retained in the revision's before snapshot.
        raw_text=original.raw_text if body.revised_text is not None else None,
        source_page_start=body.source_page_start,
        source_page_end=body.source_page_end,
        source_spans=body.source_spans,
        parser_version="reviewer-derived-v1",
        extractor_version=original.extractor_version,
        revision_number=2,
    )
    validate_review_patch(session, candidate, body)
    session.add(candidate)
    session.flush()
    revision = CandidateRevision(
        candidate_id=candidate.id,
        revision_number=2,
        previous_text=original.raw_text,
        revised_text=body.revised_text,
        diff=line_diff(original.raw_text or "", body.revised_text or ""),
        before_snapshot=candidate_snapshot(original, original.raw_text),
        after_snapshot=candidate_snapshot(candidate, body.revised_text),
        changed_fields={"derived_from_candidate_id": str(original.id)},
        reason=body.reason,
        revised_by=current_user.id,
    )
    session.add(revision)
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="review_item.derived",
            entity_type="extraction_candidate",
            entity_id=candidate.id,
            reason=body.reason,
            payload={
                "source_candidate_id": str(original.id),
                "source_document_id": str(original.source_document_id),
            },
        )
    )
    revalidate_candidate_revision_text(
        session,
        candidate=candidate,
        revised_text=body.revised_text or "",
        current_user=current_user,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="extraction_candidate",
        result_id=candidate.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(candidate)
    return candidate


def validate_review_patch(
    session: Session, candidate: ExtractionCandidate, body: ReviewItemUpdate
) -> None:
    """Reject unsafe structure edits before changing the audited candidate."""
    if (
        candidate.status == ExtractionCandidateStatus.MATERIALIZED
        or candidate.materialized_version_id
        or candidate.materialized_provision_id
    ):
        raise DomainError(
            ErrorCode.CONFLICT, "Materialized candidates cannot be revised"
        )
    run = session.get(IngestionRun, candidate.run_id)
    if not run or run.status == IngestionRunStatus.CANCELLED:
        raise DomainError(ErrorCode.CONFLICT, "Cancelled runs cannot be revised")
    # Serialize graph edits within a run, including path uniqueness checks.
    session.exec(
        select(IngestionRun).where(IngestionRun.id == run.id).with_for_update()
    ).one()
    path = body.canonical_path or candidate.canonical_path
    duplicate = session.exec(
        select(ExtractionCandidate.id).where(
            ExtractionCandidate.run_id == candidate.run_id,
            ExtractionCandidate.canonical_path == path,
            ExtractionCandidate.id != candidate.id,
        )
    ).first()
    if duplicate:
        raise DomainError(
            ErrorCode.CONFLICT, "Canonical path already exists in this run"
        )
    parent_id = (
        body.parent_candidate_id
        if "parent_candidate_id" in body.model_fields_set
        else candidate.parent_candidate_id
    )
    visited = {candidate.id}
    while parent_id:
        if parent_id in visited:
            raise DomainError(
                ErrorCode.VALIDATION_ERROR, "Candidate parent would create a cycle"
            )
        visited.add(parent_id)
        parent = session.get(ExtractionCandidate, parent_id)
        if (
            not parent
            or parent.run_id != candidate.run_id
            or parent.source_document_id != candidate.source_document_id
        ):
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                "Parent must belong to the same source and run",
            )
        parent_id = parent.parent_candidate_id
    start = (
        body.source_page_start
        if "source_page_start" in body.model_fields_set
        else candidate.source_page_start
    )
    end = (
        body.source_page_end
        if "source_page_end" in body.model_fields_set
        else candidate.source_page_end
    )
    source = session.get(SourceDocument, candidate.source_document_id)
    if start is not None and end is not None and end < start:
        raise DomainError(
            ErrorCode.VALIDATION_ERROR, "Source end page precedes start page"
        )
    if (
        source
        and source.page_count
        and any(page and page > source.page_count for page in (start, end))
    ):
        raise DomainError(
            ErrorCode.VALIDATION_ERROR, "Source page exceeds the document page count"
        )
    if body.model_fields_set & {"source_spans", "source_page_start", "source_page_end"}:
        spans = (
            body.source_spans
            if "source_spans" in body.model_fields_set
            else candidate.source_spans
        )
        for span in spans or []:
            page = span.get("page_number", span.get("page"))
            if (
                not isinstance(page, int)
                or isinstance(page, bool)
                or page < 1
                or (start is not None and page < start)
                or (end is not None and page > end)
            ):
                raise DomainError(
                    ErrorCode.VALIDATION_ERROR,
                    "Each source span must name a page within the candidate range",
                )


def decide_review_candidate(
    session: Session,
    candidate_id: uuid.UUID,
    body: ReviewDecisionCreate,
    current_user: User,
) -> ExtractionCandidate:
    scope = idempotency_scope("review_item.decision", candidate_id)
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_candidate(session, candidate_id)
    candidate = get_candidate(session, candidate_id)
    check_expected_version(candidate.lock_version, body.expected_version)
    if body.decision == ReviewDecisionType.APPROVE and has_open_blocking_issue(
        session, candidate.id
    ):
        raise DomainError(
            ErrorCode.CONFLICT,
            "Blocking review issues must be resolved before approval",
        )
    decision = ReviewDecisionRecord(
        candidate_id=candidate.id,
        decision=body.decision,
        decided_by=current_user.id,
        reason=body.reason,
    )
    candidate.status = candidate_status_for_decision(body.decision)
    candidate.lock_version += 1
    candidate.updated_at = get_datetime_utc()
    session.add(decision)
    session.add(candidate)
    session.flush()
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="review_decision",
        result_id=decision.id,
        created_by=current_user.id,
    )
    if body.decision == ReviewDecisionType.APPROVE:
        maybe_complete_review_and_queue_materialization(session, candidate=candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


def update_review_issue(
    session: Session,
    issue_id: uuid.UUID,
    body: ReviewIssueUpdate,
    current_user: User,
) -> ReviewIssue:
    scope = idempotency_scope("review_issue.update", issue_id)
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        issue = session.get(ReviewIssue, issue_id)
        if issue is None:
            raise DomainError(ErrorCode.NOT_FOUND, "Review issue not found")
        return issue
    issue = session.exec(
        select(ReviewIssue).where(ReviewIssue.id == issue_id).with_for_update()
    ).one_or_none()
    if issue is None:
        raise DomainError(ErrorCode.NOT_FOUND, "Review issue not found")
    if issue.status == ReviewIssueStatus.RESOLVED:
        raise DomainError(ErrorCode.CONFLICT, "Review issue is already resolved")
    if issue.blocking and not current_user.is_superuser:
        raise DomainError(
            ErrorCode.CONFLICT,
            "Blocking issues must be resolved by candidate revalidation",
        )
    if issue.blocking and not body.superuser_override_reason:
        raise DomainError(
            ErrorCode.CONFLICT, "A blocking issue override requires a reason"
        )
    now = get_datetime_utc()
    issue.status = ReviewIssueStatus.RESOLVED
    issue.resolved_by = current_user.id
    issue.resolved_at = now
    issue.resolution_reason = body.reason
    issue.resolution_evidence = body.evidence
    session.add(issue)
    candidate = session.get(ExtractionCandidate, issue.candidate_id)
    if candidate:
        candidate.blocking_issue_count = open_blocking_issue_count(
            session, candidate.id
        )
        candidate.updated_at = now
        session.add(candidate)
    if body.superuser_override_reason:
        session.add(
            AuditEvent(
                actor_user_id=current_user.id,
                action="review_issue.blocking_override",
                entity_type="review_issue",
                entity_id=issue.id,
                severity=AuditSeverity.HIGH,
                reason=body.superuser_override_reason,
                payload={"issue_type": issue.issue_type},
            )
        )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="review_issue",
        result_id=issue.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(issue)
    return issue


def latest_revision_text(
    session: Session, candidate: ExtractionCandidate
) -> str | None:
    revision = latest_candidate_revision(session, candidate.id)
    return revision.revised_text if revision else None


def candidate_status_for_decision(
    decision: ReviewDecisionType,
) -> ExtractionCandidateStatus:
    if decision == ReviewDecisionType.APPROVE:
        return ExtractionCandidateStatus.APPROVED
    if decision == ReviewDecisionType.REJECT:
        return ExtractionCandidateStatus.REJECTED
    return ExtractionCandidateStatus.NEEDS_CORRECTION
