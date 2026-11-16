from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.ingestion.admin.queries import get_run_step
from app.ingestion.admin.review_validation import (
    live_review_candidates,
    review_candidates_ready_for_materialization,
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
    VerificationStatus,
)
from app.legal.models import (
    ExtractionCandidate,
    IngestionEvent,
    IngestionRun,
    SourceDocument,
)


def maybe_complete_review_and_queue_materialization(
    session: Session,
    *,
    candidate: ExtractionCandidate,
) -> None:
    run = session.get(IngestionRun, candidate.run_id)
    if not run or not (
        run.current_stage == IngestionStage.REVIEW
        or run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    ):
        return
    # Approval is often performed in batches. Avoid loading every candidate's
    # text and spans after each decision while any review remains unfinished.
    unfinished = session.exec(
        select(ExtractionCandidate.id).where(
            ExtractionCandidate.run_id == run.id,
            col(ExtractionCandidate.status).not_in(
                [
                    ExtractionCandidateStatus.APPROVED,
                    ExtractionCandidateStatus.AUTO_APPROVED,
                    ExtractionCandidateStatus.MATERIALIZED,
                    ExtractionCandidateStatus.REJECTED,
                ]
            ),
        )
    ).first()
    if unfinished:
        return
    candidates = live_review_candidates(session, run.id)
    if not review_candidates_ready_for_materialization(session, candidates):
        return

    source = session.get(SourceDocument, candidate.source_document_id)
    if not source or source.verification_status != VerificationStatus.VERIFIED:
        mark_review_waiting_for_source_verification(
            session, run=run, source=source, candidates=candidates
        )
        return

    complete_review_and_queue_materialization(
        session, run=run, source=source, candidates=candidates
    )


def queue_materialization_for_verified_source(
    session: Session,
    *,
    source: SourceDocument,
) -> None:
    runs = session.exec(
        select(IngestionRun).where(
            IngestionRun.source_document_id == source.id,
            IngestionRun.status == IngestionRunStatus.WAITING_FOR_REVIEW,
            IngestionRun.current_stage == IngestionStage.REVIEW,
        )
    ).all()
    for run in runs:
        candidates = live_review_candidates(session, run.id)
        if review_candidates_ready_for_materialization(session, candidates):
            complete_review_and_queue_materialization(
                session, run=run, source=source, candidates=candidates
            )


def mark_review_waiting_for_source_verification(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument | None,
    candidates: Sequence[ExtractionCandidate],
) -> None:
    now = get_datetime_utc()
    review_step = get_run_step(session, run.id, IngestionStage.REVIEW)
    review_step.status = IngestionStepStatus.BLOCKED
    review_step.metrics = {
        "candidate_count": len(candidates),
        "source_verification_required": True,
    }
    review_step.updated_at = now
    review_step.lock_version += 1
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    run.updated_at = now
    session.add(review_step)
    session.add(run)
    existing_event = session.exec(
        select(IngestionEvent).where(
            IngestionEvent.run_id == run.id,
            IngestionEvent.event_type == "source_verification_required",
        )
    ).first()
    if existing_event:
        session.commit()
        return
    append_run_event(
        session,
        run,
        event_type="source_verification_required",
        message="Document-level source verification is required before materialization",
        stage=IngestionStage.REVIEW,
        payload={
            "candidate_count": len(candidates),
            "source_document_id": str(source.id) if source else None,
        },
    )


def complete_review_and_queue_materialization(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    candidates: Sequence[ExtractionCandidate],
) -> None:
    now = get_datetime_utc()
    review_step = get_run_step(session, run.id, IngestionStage.REVIEW)
    review_step.status = IngestionStepStatus.SUCCEEDED
    review_step.completed_units = len(candidates)
    review_step.completed_at = now
    review_step.updated_at = now
    review_step.lock_version += 1
    session.add(review_step)

    materializing_step = get_run_step(session, run.id, IngestionStage.MATERIALIZING)
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = IngestionStage.MATERIALIZING
    run.lock_version += 1
    run.updated_at = now
    session.add(run)
    session.commit()
    enqueue_task(
        session,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:{IngestionStage.MATERIALIZING.value}",
        payload={"source_document_id": str(source.id)},
        priority=50,
    )
    append_run_event(
        session,
        run,
        event_type="review_completed",
        message="Review approved; materialization queued",
        step=review_step,
        payload={"candidate_count": len(candidates)},
    )
