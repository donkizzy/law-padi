from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_
from sqlmodel import Session, col, func, select

from app.ingestion.common import enum_value, get_datetime_utc
from app.ingestion.runtime.errors import IngestionLeaseLost
from app.ingestion.runtime.leases import TaskLease, update_owned_task
from app.ingestion.runtime.retry import retry_delay
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
)
from app.legal.models import (
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    TransactionalOutbox,
)

PIPELINE_STAGES: tuple[IngestionStage, ...] = (
    IngestionStage.UPLOADING,
    IngestionStage.VERIFYING_UPLOAD,
    IngestionStage.MALWARE_SCAN,
    IngestionStage.PROFILING,
    IngestionStage.AWAITING_PAGE_CONFIRMATION,
    IngestionStage.RENDERING,
    IngestionStage.NATIVE_EXTRACTION,
    IngestionStage.LOCAL_OCR,
    IngestionStage.MANAGED_OCR,
    IngestionStage.NORMALIZING,
    IngestionStage.PARSING_STRUCTURE,
    IngestionStage.VALIDATING_DOCUMENT,
    IngestionStage.REVIEW,
    IngestionStage.MATERIALIZING,
    IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
    IngestionStage.EMBEDDING,
    IngestionStage.INDEXING,
    IngestionStage.VALIDATING_INDEX,
    IngestionStage.PUBLISHING,
)
ACTIVE_STEP_STATUSES: tuple[IngestionStepStatus, ...] = (
    IngestionStepStatus.PENDING,
    IngestionStepStatus.LEASED,
    IngestionStepStatus.RUNNING,
    IngestionStepStatus.BLOCKED,
)
ACTIVE_TASK_STATUSES: tuple[IngestionTaskStatus, ...] = (
    IngestionTaskStatus.PENDING,
    IngestionTaskStatus.LEASED,
    IngestionTaskStatus.RUNNING,
)
TERMINAL_RUN_STATUSES: tuple[IngestionRunStatus, ...] = (
    IngestionRunStatus.FAILED,
    IngestionRunStatus.CANCELLED,
    IngestionRunStatus.PUBLISHED,
)


def create_run_steps(
    session: Session,
    run: IngestionRun,
    stages: tuple[IngestionStage, ...] = PIPELINE_STAGES,
    *,
    commit: bool = True,
) -> list[IngestionStep]:
    existing_steps = session.exec(
        select(IngestionStep).where(IngestionStep.run_id == run.id)
    ).all()
    if existing_steps:
        stage_order = {stage.value: index for index, stage in enumerate(stages)}
        return sorted(
            existing_steps,
            key=lambda step: stage_order.get(enum_value(step.stage), len(stages)),
        )

    steps: list[IngestionStep] = []
    dependency_step_id: UUID | None = None
    for stage in stages:
        step = IngestionStep(
            run_id=run.id,
            dependency_step_id=dependency_step_id,
            stage=stage,
            status=IngestionStepStatus.PENDING,
            idempotency_key=f"{run.id}:{stage.value}",
        )
        session.add(step)
        session.flush()
        dependency_step_id = step.id
        steps.append(step)
    if commit:
        session.commit()
    else:
        session.flush()
    return steps


def append_run_event(
    session: Session,
    run: IngestionRun,
    *,
    event_type: str,
    message: str,
    step: IngestionStep | None = None,
    stage: IngestionStage | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> IngestionEvent:
    session.exec(
        select(IngestionRun).where(IngestionRun.id == run.id).with_for_update()
    ).one()
    latest_sequence = session.exec(
        select(func.max(IngestionEvent.sequence)).where(IngestionEvent.run_id == run.id)
    ).one()
    sequence = int(latest_sequence or 0) + 1
    event_stage = stage
    if event_stage is None and step is not None:
        event_stage = step.stage
    event = IngestionEvent(
        run_id=run.id,
        step_id=step.id if step else None,
        sequence=sequence,
        event_type=event_type,
        stage=event_stage,
        message=message,
        payload=payload,
    )
    session.add(event)
    session.flush()
    _append_outbox_event(
        session,
        aggregate_type="ingestion_run",
        aggregate_id=run.id,
        event_type=f"ingestion_event.{event_type}",
        idempotency_key=f"ingestion-event:{run.id}:{sequence}",
        payload={
            "event_id": str(event.id),
            "run_id": str(run.id),
            "step_id": str(event.step_id) if event.step_id else None,
            "sequence": sequence,
            "stage": enum_value(event_stage) if event_stage else None,
            "message": message,
            "payload": payload or {},
        },
    )
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(event)
    return event


def enqueue_task(
    session: Session,
    *,
    run: IngestionRun,
    step: IngestionStep | None,
    task_type: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    priority: int = 100,
    commit: bool = True,
) -> IngestionTask:
    existing_task = session.exec(
        select(IngestionTask).where(IngestionTask.idempotency_key == idempotency_key)
    ).first()
    if existing_task:
        return existing_task

    task = IngestionTask(
        run_id=run.id,
        step_id=step.id if step else None,
        task_type=task_type,
        status=IngestionTaskStatus.PENDING,
        priority=priority,
        idempotency_key=idempotency_key,
        payload=payload or {},
    )
    session.add(task)
    session.flush()
    _append_outbox_event(
        session,
        aggregate_type="ingestion_task",
        aggregate_id=task.id,
        event_type="ingestion_task.enqueued",
        idempotency_key=f"ingestion-task:{idempotency_key}:enqueued",
        payload={
            "task_id": str(task.id),
            "run_id": str(run.id),
            "step_id": str(step.id) if step else None,
            "task_type": task_type,
            "priority": priority,
            "payload": payload or {},
        },
    )
    if commit:
        session.commit()
        session.refresh(task)
    else:
        session.flush()
    return task


def lease_next_task(
    session: Session,
    *,
    worker_id: str,
    task_type: str | None = None,
    run_id: UUID | None = None,
    lease_seconds: int = 900,
    stage_concurrency_limits: dict[str, int] | None = None,
) -> IngestionTask | None:
    now = get_datetime_utc()
    limits = stage_concurrency_limits or {}
    statement = (
        select(IngestionTask)
        .join(IngestionRun, col(IngestionRun.id) == col(IngestionTask.run_id))
        .where(
            or_(
                col(IngestionTask.status) == IngestionTaskStatus.PENDING,
                and_(
                    col(IngestionTask.status).in_(
                        (
                            IngestionTaskStatus.LEASED,
                            IngestionTaskStatus.RUNNING,
                        )
                    ),
                    col(IngestionTask.leased_until).is_not(None),
                    col(IngestionTask.leased_until) < now,
                ),
            ),
            col(IngestionTask.available_at) <= now,
            ~col(IngestionRun.status).in_(TERMINAL_RUN_STATUSES),
        )
        .order_by(col(IngestionTask.priority), col(IngestionTask.created_at))
        .with_for_update(skip_locked=True)
    )
    if run_id is not None:
        statement = statement.where(IngestionTask.run_id == run_id)
    if task_type:
        statement = statement.where(col(IngestionTask.task_type) == task_type)
    candidates = session.exec(statement.limit(100)).all()
    for task in candidates:
        if _task_type_at_concurrency_limit(
            session,
            task_type=task.task_type,
            limits=limits,
            now=now,
        ):
            continue

        lease_until = now + timedelta(seconds=lease_seconds)
        task.status = IngestionTaskStatus.LEASED
        task.lease_owner = worker_id
        task.leased_until = lease_until
        task.heartbeat_at = now
        task.attempt_count += 1
        task.lock_version += 1
        task.updated_at = now
        session.add(task)
        session.commit()
        session.refresh(task)
        return task
    return None


def mark_task_running(
    session: Session, task: IngestionTask, *, commit: bool = True
) -> IngestionTask:
    now = get_datetime_utc()
    update_owned_task(
        session,
        TaskLease.from_task(task),
        {
            "status": IngestionTaskStatus.RUNNING,
            "heartbeat_at": now,
            "updated_at": now,
            "lock_version": col(IngestionTask.lock_version) + 1,
        },
    )
    if commit:
        session.commit()
    session.refresh(task)
    return task


def renew_task_lease(
    session: Session,
    *,
    task_id: UUID,
    worker_id: str,
    lease_version: int,
    lease_seconds: int,
) -> bool:
    now = get_datetime_utc()
    try:
        update_owned_task(
            session,
            TaskLease(task_id, worker_id, lease_version),
            {
                "leased_until": now + timedelta(seconds=max(1, lease_seconds)),
                "heartbeat_at": now,
                "updated_at": now,
                "lock_version": col(IngestionTask.lock_version) + 1,
            },
        )
    except IngestionLeaseLost:
        session.rollback()
        return False
    session.commit()
    return True


def complete_task(
    session: Session,
    task: IngestionTask,
    *,
    commit: bool = True,
    lease: TaskLease | None = None,
) -> IngestionTask:
    now = get_datetime_utc()
    update_owned_task(
        session,
        lease or TaskLease.from_task(task),
        {
            "status": IngestionTaskStatus.SUCCEEDED,
            "lease_owner": None,
            "leased_until": None,
            "heartbeat_at": now,
            "updated_at": now,
            "lock_version": col(IngestionTask.lock_version) + 1,
        },
    )
    if commit:
        session.commit()
    session.refresh(task)
    return task


def fail_task(
    session: Session,
    task: IngestionTask,
    error_details: dict[str, Any],
    *,
    lease: TaskLease | None = None,
    commit: bool = True,
    retryable: bool = True,
) -> IngestionTask:
    now = get_datetime_utc()
    terminal = not retryable or task.attempt_count >= task.max_attempts
    update_owned_task(
        session,
        lease or TaskLease.from_task(task),
        {
            "error_details": error_details,
            "available_at": (
                task.available_at
                if terminal
                else now
                + timedelta(seconds=retry_delay(task.attempt_count, base=30, cap=1800))
            ),
            "lease_owner": None,
            "leased_until": None,
            "heartbeat_at": now,
            "updated_at": now,
            "lock_version": col(IngestionTask.lock_version) + 1,
            "status": (
                IngestionTaskStatus.FAILED if terminal else IngestionTaskStatus.PENDING
            ),
        },
    )
    if commit:
        session.commit()
    session.refresh(task)
    return task


def release_task(
    session: Session,
    task: IngestionTask,
    *,
    lease: TaskLease,
    commit: bool = True,
) -> IngestionTask:
    now = get_datetime_utc()
    update_owned_task(
        session,
        lease,
        {
            "status": IngestionTaskStatus.PENDING,
            "lease_owner": None,
            "leased_until": None,
            "available_at": now,
            "updated_at": now,
            "lock_version": col(IngestionTask.lock_version) + 1,
            # A cooperative yield does not spend an error retry. Keep the fencing
            # version monotonic while extending the failure-attempt allowance.
            "max_attempts": col(IngestionTask.max_attempts) + 1,
        },
    )
    if commit:
        session.commit()
    session.refresh(task)
    return task


def mark_run_cancelled(
    session: Session, run: IngestionRun, reason: str, *, commit: bool = True
) -> IngestionRun:
    now = get_datetime_utc()
    tasks = session.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            col(IngestionTask.status).in_(ACTIVE_TASK_STATUSES),
        )
    ).all()
    for task in tasks:
        task.status = IngestionTaskStatus.CANCELLED
        task.lease_owner = None
        task.leased_until = None
        task.heartbeat_at = now
        task.updated_at = now
        task.lock_version += 1
        session.add(task)
    steps = session.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            col(IngestionStep.status).in_(ACTIVE_STEP_STATUSES),
        )
    ).all()
    for step in steps:
        step.status = IngestionStepStatus.CANCELLED
        step.completed_at = now
        step.updated_at = now
        step.lock_version += 1
        session.add(step)
    run.status = IngestionRunStatus.CANCELLED
    run.error_details = {"reason": reason}
    run.completed_at = now
    run.updated_at = now
    session.add(run)
    append_run_event(
        session,
        run,
        event_type="run_cancelled",
        message=reason,
        stage=run.current_stage,
        commit=False,
    )
    if commit:
        session.commit()
    return run


def _append_outbox_event(
    session: Session,
    *,
    aggregate_type: str,
    aggregate_id: UUID,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> TransactionalOutbox:
    existing = session.exec(
        select(TransactionalOutbox).where(
            TransactionalOutbox.idempotency_key == idempotency_key
        )
    ).first()
    if existing:
        return existing
    outbox = TransactionalOutbox(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    session.add(outbox)
    return outbox


def drain_outbox_batch(
    session: Session,
    *,
    limit: int = 100,
    publisher: Callable[[TransactionalOutbox], None] | None = None,
) -> list[TransactionalOutbox]:
    """Claim outbox rows and mark them only after the publisher succeeds."""
    pending = list(
        session.exec(
            select(TransactionalOutbox)
            .where(
                col(TransactionalOutbox.published_at).is_(None),
                col(TransactionalOutbox.event_type).startswith("ingestion_"),
            )
            .order_by(col(TransactionalOutbox.created_at))
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
    )
    if publisher is None:
        return pending
    now = datetime.now(UTC)
    for event in pending:
        try:
            event.attempt_count += 1
            publisher(event)
            event.published_at = now
            event.error_message = None
            session.add(event)
        except Exception as exc:
            event.error_message = str(exc)[:2000]
            session.add(event)
    session.commit()
    return pending


def _task_type_at_concurrency_limit(
    session: Session,
    *,
    task_type: str,
    limits: dict[str, int],
    now: datetime,
) -> bool:
    limit = limits.get(task_type)
    if limit is None:
        return False
    if limit <= 0:
        return True
    active_count = session.exec(
        select(func.count())
        .select_from(IngestionTask)
        .join(IngestionRun, col(IngestionRun.id) == col(IngestionTask.run_id))
        .where(
            IngestionTask.task_type == task_type,
            col(IngestionTask.status).in_(
                (IngestionTaskStatus.LEASED, IngestionTaskStatus.RUNNING)
            ),
            col(IngestionTask.leased_until).is_not(None),
            col(IngestionTask.leased_until) >= now,
            ~col(IngestionRun.status).in_(TERMINAL_RUN_STATUSES),
        )
    ).one()
    return int(active_count or 0) >= limit
