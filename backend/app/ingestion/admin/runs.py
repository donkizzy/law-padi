import uuid

from fastapi import HTTPException, status
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_payload_hash,
    idempotency_record_for_request,
    idempotency_scope,
)
from app.ingestion.admin.queries import (
    check_expected_version,
    get_release,
    get_run,
    get_run_step,
    release_id_for_run,
)
from app.ingestion.admin.release_gates import release_source_and_review_gates
from app.ingestion.common import enum_value, get_datetime_utc
from app.ingestion.composition import (
    release_entries,
)
from app.ingestion.runtime.queue import (
    append_run_event,
    enqueue_task,
    mark_run_cancelled,
)
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
)
from app.legal.models import (
    EmbeddingProfile,
    IngestionRun,
    IngestionTask,
)
from app.models import User


def cancel_ingestion_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
    reason: str,
) -> IngestionRun:
    scope = idempotency_scope("ingestion_run.cancel", run_id)
    request_hash = idempotency_payload_hash(
        {"expected_version": expected_version, "reason": reason, "run_id": str(run_id)}
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_run(session, run_id)
    run = get_run(session, run_id)
    check_expected_version(run.lock_version, expected_version)
    if run.status in {IngestionRunStatus.PUBLISHED, IngestionRunStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminal ingestion runs cannot be cancelled",
        )
    cancelled = mark_run_cancelled(session, run, reason, commit=False)
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=cancelled.id,
        created_by=current_user.id,
    )
    session.commit()
    return cancelled


def resume_ingestion_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> IngestionRun:
    scope = idempotency_scope("ingestion_run.resume", run_id)
    request_hash = idempotency_payload_hash(
        {"expected_version": expected_version, "run_id": str(run_id)}
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_run(session, run_id)
    run = get_run(session, run_id)
    check_expected_version(run.lock_version, expected_version)
    if run.status not in {
        IngestionRunStatus.WAITING_FOR_INPUT,
        IngestionRunStatus.WAITING_FOR_REVIEW,
        IngestionRunStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only waiting or cancelled ingestion runs can be resumed",
        )
    was_cancelled = run.status == IngestionRunStatus.CANCELLED
    resume_stage = IngestionStage(enum_value(run.current_stage))
    is_page_confirmation = resume_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    if not was_cancelled:
        append_run_event(
            session,
            run,
            event_type="run_resume_not_required",
            message="Ingestion run is already awaiting operator input",
            stage=resume_stage,
            commit=False,
        )
        add_idempotency_record(
            session,
            scope=scope,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            result_type="ingestion_run",
            result_id=run.id,
            created_by=current_user.id,
        )
        session.commit()
        session.refresh(run)
        return run

    run.status = (
        IngestionRunStatus.WAITING_FOR_INPUT
        if is_page_confirmation
        else IngestionRunStatus.QUEUED
    )
    run.completed_at = None
    run.error_details = None
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add(run)
    resume_step = get_run_step(session, run.id, resume_stage)
    resume_step.status = (
        IngestionStepStatus.BLOCKED
        if is_page_confirmation
        else IngestionStepStatus.PENDING
    )
    resume_step.lease_owner = None
    resume_step.leased_until = None
    resume_step.heartbeat_at = None
    resume_step.started_at = None
    resume_step.completed_at = None
    resume_step.error_details = None
    resume_step.lock_version += 1
    resume_step.updated_at = run.updated_at
    session.add(resume_step)
    if not is_page_confirmation:
        payload: dict[str, object] = {"resume": True}
        if run.source_document_id:
            payload["source_document_id"] = str(run.source_document_id)
        enqueue_task(
            session,
            run=run,
            step=resume_step,
            task_type=resume_stage.value,
            idempotency_key=(
                f"{run.id}:{resume_stage.value}:resume:{run.lock_version}"
            ),
            payload=payload,
            priority=5,
            commit=False,
        )
    append_run_event(
        session,
        run,
        event_type="run_resumed",
        message="Ingestion run resumed",
        stage=resume_stage,
        commit=False,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=run.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(run)
    return run


def start_embedding(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> IngestionRun:
    """Atomically move a release from the human pause into embedding."""
    scope = idempotency_scope("ingestion_run.start_embedding", run_id)
    request_hash = idempotency_payload_hash(
        {"expected_version": expected_version, "run_id": str(run_id)}
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_run(session, run_id)
    run = get_run(session, run_id)
    check_expected_version(run.lock_version, expected_version)
    if run.status != IngestionRunStatus.READY_TO_EMBED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only runs ready to embed can start embedding",
        )
    profiles = session.exec(
        select(EmbeddingProfile).where(col(EmbeddingProfile.is_active).is_(True))
    ).all()
    if not profiles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least one active embedding profile is required",
        )
    if any(
        profile.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS
        or not profile.model_revision
        for profile in profiles
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active embedding profiles must use 1,024 dimensions and pinned revisions",
        )
    release_id = release_id_for_run(session, run)
    release = get_release(session, release_id)
    if (release.validation_report or {}).get("composition") is not None:
        gates = release_source_and_review_gates(
            session, release_entries(session, release.id), release=release
        )
        if gates:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Composite member gates must pass before embedding",
                    "gates": gates,
                },
            )
    step = get_run_step(session, run.id, IngestionStage.EMBEDDING)
    step.status = IngestionStepStatus.PENDING
    step.lock_version += 1
    step.updated_at = get_datetime_utc()
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = IngestionStage.EMBEDDING
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add_all([run, step])
    enqueue_task(
        session,
        run=run,
        step=step,
        task_type=IngestionStage.EMBEDDING.value,
        # A run can be embedded again after its documents are rebuilt; a fixed
        # key would return the earlier task and queue nothing. The request
        # itself stays idempotent through its idempotency record.
        idempotency_key=(
            f"{run.id}:{IngestionStage.EMBEDDING.value}:manual:{run.lock_version}"
        ),
        payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release_id),
        },
        priority=40,
        commit=False,
    )
    append_run_event(
        session,
        run,
        event_type="embedding_started",
        message="Embedding benchmark and indexing queued",
        stage=IngestionStage.EMBEDDING,
        commit=False,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=run.id,
        created_by=current_user.id,
    )
    session.commit()
    return run


def retry_ingestion_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> IngestionRun:
    scope = idempotency_scope("ingestion_run.retry", run_id)
    request_hash = idempotency_payload_hash(
        {"expected_version": expected_version, "run_id": str(run_id)}
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_run(session, run_id)
    run = get_run(session, run_id)
    check_expected_version(run.lock_version, expected_version)
    if run.status != IngestionRunStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed ingestion runs can be retried",
        )
    run.status = IngestionRunStatus.QUEUED
    run.lock_version += 1
    run.error_details = None
    run.updated_at = get_datetime_utc()
    session.add(run)
    stage_value = enum_value(run.current_stage)
    # Stages such as embedding read their release from the task payload, so the
    # retry carries over the stage's latest payload that holds those inputs
    # (an earlier retry queued before this fix may hold only the retry flag).
    previous_payload = next(
        (
            payload
            for payload in session.exec(
                select(IngestionTask.payload)
                .where(
                    IngestionTask.run_id == run.id,
                    IngestionTask.task_type == stage_value,
                )
                .order_by(col(IngestionTask.created_at).desc())
            ).all()
            if set(payload or {}) - {"retry"}
        ),
        {},
    )
    enqueue_task(
        session,
        run=run,
        step=get_run_step(session, run.id, run.current_stage),
        task_type=stage_value,
        idempotency_key=f"{run.id}:{stage_value}:retry:{run.lock_version}",
        payload={**previous_payload, "retry": True},
        priority=5,
        commit=False,
    )
    append_run_event(
        session,
        run,
        event_type="run_retried",
        message="Failed ingestion run queued for retry",
        stage=run.current_stage,
        commit=False,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=run.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(run)
    return run
