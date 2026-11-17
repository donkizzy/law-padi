import uuid

from sqlmodel import Session, col, select

from app.core.errors import DomainError, ErrorCode
from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_record_for_request,
    idempotency_request_hash,
    idempotency_result_payload,
    idempotency_scope,
)
from app.ingestion.admin.queries import check_expected_version, get_run_step
from app.ingestion.admin.review_validation import (
    open_blocking_issue_count,
    revalidate_review_page_coverage,
)
from app.ingestion.common import get_datetime_utc
from app.ingestion.runtime.queue import (
    append_run_event,
    enqueue_task,
)
from app.legal.enums import (
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    PageInclusionStatus,
    ReviewIssueStatus,
)
from app.legal.models import (
    ExtractionCandidate,
    IdempotencyRecord,
    IngestionRun,
    ReviewIssue,
    SourcePage,
)
from app.legal.schemas import (
    PageSelectionUpdate,
)
from app.models import User


def update_page_selection(
    session: Session,
    run_id: uuid.UUID,
    body: PageSelectionUpdate,
    current_user: User,
) -> list[SourcePage]:
    scope = idempotency_scope("ingestion_run.page_selection", run_id)
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return pages_for_idempotency_record(session, record)
    run = session.exec(
        select(IngestionRun).where(IngestionRun.id == run_id).with_for_update()
    ).one_or_none()
    if run is None:
        raise DomainError(ErrorCode.NOT_FOUND, "Ingestion run not found")
    check_expected_version(run.lock_version, body.expected_run_version)
    imported_review = (
        run.status == IngestionRunStatus.WAITING_FOR_REVIEW
        and run.current_stage == IngestionStage.REVIEW
        and bool((run.pipeline_config or {}).get("review_import_complete"))
    )
    if not imported_review and (
        run.status != IngestionRunStatus.WAITING_FOR_INPUT
        or run.current_stage != IngestionStage.AWAITING_PAGE_CONFIRMATION
    ):
        raise DomainError(
            ErrorCode.CONFLICT, "Page selection is not currently awaiting confirmation"
        )
    all_pages = session.exec(
        select(SourcePage).where(SourcePage.run_id == run.id).with_for_update()
    ).all()
    requested_numbers = [item.page_number for item in body.pages]
    if len(requested_numbers) != len(set(requested_numbers)):
        raise DomainError(
            ErrorCode.VALIDATION_ERROR,
            "Each profiled page must be included exactly once",
        )
    profiled_numbers = {page.page_number for page in all_pages}
    if set(requested_numbers) != profiled_numbers:
        raise DomainError(
            ErrorCode.VALIDATION_ERROR,
            "Page selection must include every profiled page exactly once",
        )
    pages_by_number = {page.page_number: page for page in all_pages}
    if imported_review and any(
        page.inclusion_status
        not in {PageInclusionStatus.INCLUDED, PageInclusionStatus.EXCLUDED}
        or not (page.inclusion_reason or "").strip()
        for page in body.pages
    ):
        raise DomainError(
            ErrorCode.VALIDATION_ERROR,
            "Imported review pages require explicit inclusion decisions and reasons",
        )
    pages: list[SourcePage] = []
    for requested_page in body.pages:
        page = pages_by_number.get(requested_page.page_number)
        if not page:
            raise DomainError(ErrorCode.NOT_FOUND, "Source page not found")
        check_expected_version(page.lock_version, requested_page.expected_version)
        page.inclusion_status = requested_page.inclusion_status
        page.inclusion_reason = requested_page.inclusion_reason
        page.lock_version += 1
        session.add(page)
        pages.append(page)
    if imported_review:
        candidates = session.exec(
            select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
        ).all()
        included = {
            page.page_number
            for page in pages
            if page.inclusion_status == PageInclusionStatus.INCLUDED
        }
        for candidate in candidates:
            if (
                candidate.status == ExtractionCandidateStatus.MATERIALIZED
                or candidate.materialized_version_id
            ):
                raise DomainError(
                    ErrorCode.CONFLICT,
                    "Materialized runs cannot change page boundaries",
                )
            revalidate_review_page_coverage(session, candidate, included, current_user)
            if candidate.status in {
                ExtractionCandidateStatus.APPROVED,
                ExtractionCandidateStatus.AUTO_APPROVED,
            }:
                candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
            candidate.lock_version += 1
            session.add(candidate)
            for issue in session.exec(
                select(ReviewIssue).where(
                    ReviewIssue.candidate_id == candidate.id,
                    ReviewIssue.issue_type == "provisional_page_boundaries",
                    ReviewIssue.status == ReviewIssueStatus.OPEN,
                )
            ).all():
                issue.status = ReviewIssueStatus.RESOLVED
                issue.resolved_by = current_user.id
                issue.resolved_at = get_datetime_utc()
                issue.resolution_reason = "All imported source pages received explicit reviewed boundary decisions."
                issue.resolution_evidence = {
                    "page_numbers": sorted(included),
                    "idempotency_key": body.idempotency_key,
                }
                session.add(issue)
            session.flush()
            candidate.blocking_issue_count = open_blocking_issue_count(
                session, candidate.id
            )
        run.pipeline_config = {
            **run.pipeline_config,
            "provisional_page_boundaries": False,
        }
        run.lock_version += 1
        run.updated_at = get_datetime_utc()
        session.add(run)
        append_run_event(
            session,
            run,
            event_type="review_page_boundaries_confirmed",
            message="Imported page boundaries confirmed; candidate review remains required",
            stage=IngestionStage.REVIEW,
            payload={
                "actor_user_id": str(current_user.id),
                "pages": [item.model_dump(mode="json") for item in body.pages],
            },
            commit=False,
        )
        add_idempotency_record(
            session,
            scope=scope,
            idempotency_key=body.idempotency_key,
            request_hash=request_hash,
            result_type="page_selection",
            result_id=run.id,
            created_by=current_user.id,
            result_payload={
                "run_id": str(run.id),
                "page_numbers": [page.page_number for page in pages],
            },
        )
        session.commit()
        for page in pages:
            session.refresh(page)
        return pages
    awaiting_step = get_run_step(
        session, run.id, IngestionStage.AWAITING_PAGE_CONFIRMATION
    )
    awaiting_step.status = IngestionStepStatus.SUCCEEDED
    awaiting_step.completed_units = len(pages)
    awaiting_step.completed_at = get_datetime_utc()
    awaiting_step.updated_at = awaiting_step.completed_at
    session.add(awaiting_step)
    native_extraction_step = get_run_step(
        session, run.id, IngestionStage.NATIVE_EXTRACTION
    )
    run.status = IngestionRunStatus.RUNNING
    run.current_stage = IngestionStage.NATIVE_EXTRACTION
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add(run)
    enqueue_task(
        session,
        run=run,
        step=native_extraction_step,
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:{IngestionStage.NATIVE_EXTRACTION.value}",
        payload={"source_document_id": str(run.source_document_id)},
        priority=30,
        commit=False,
    )
    append_run_event(
        session,
        run,
        event_type="page_selection_confirmed",
        message="Page inclusion ranges confirmed",
        stage=IngestionStage.AWAITING_PAGE_CONFIRMATION,
        payload={"page_count": len(pages)},
        commit=False,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="page_selection",
        result_id=run.id,
        created_by=current_user.id,
        result_payload={
            "run_id": str(run.id),
            "page_numbers": [page.page_number for page in pages],
        },
    )
    session.commit()
    for page in pages:
        session.refresh(page)
    return pages


def pages_for_idempotency_record(
    session: Session, record: IdempotencyRecord
) -> list[SourcePage]:
    payload = idempotency_result_payload(record)
    run_id = payload.get("run_id")
    page_numbers = payload.get("page_numbers")
    if not isinstance(run_id, str) or not isinstance(page_numbers, list):
        raise DomainError(
            ErrorCode.CONFLICT,
            "Idempotent page-selection result is no longer available",
        )
    numbers = [number for number in page_numbers if isinstance(number, int)]
    if not numbers:
        return []
    pages = session.exec(
        select(SourcePage)
        .where(
            SourcePage.run_id == uuid.UUID(run_id),
            col(SourcePage.page_number).in_(numbers),
        )
        .order_by(col(SourcePage.page_number))
    ).all()
    if len(pages) != len(numbers):
        raise DomainError(
            ErrorCode.CONFLICT,
            "Idempotent page-selection result is no longer available",
        )
    return list(pages)
