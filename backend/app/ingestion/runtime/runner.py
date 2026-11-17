import threading
import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.common import get_datetime_utc
from app.ingestion.registry import handler_for
from app.ingestion.runtime.errors import (
    IngestionLeaseLost,
    IngestionWorkerError,
    IngestionWorkerStopped,
    retryable_error,
)
from app.ingestion.runtime.inputs import retain_pipeline_inputs
from app.ingestion.runtime.leases import TaskLease, fence_stage_writes
from app.ingestion.runtime.queue import (
    append_run_event,
    complete_task,
    enqueue_task,
    fail_task,
    lease_next_task,
    mark_task_running,
    release_task,
    renew_task_lease,
)
from app.ingestion.runtime.source_files import source_files
from app.ingestion.runtime.types import StageOutcome, WorkerResult
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    SourceUploadStatus,
)
from app.legal.models import (
    IngestionRun,
    IngestionStep,
    IngestionTask,
    SourceUpload,
)


def run_once(
    session: Session,
    *,
    worker_id: str,
    task_type: str | None = None,
    lease_seconds: int = 900,
    stage_concurrency_limits: dict[str, int] | None = None,
) -> WorkerResult | None:
    task = lease_next_task(
        session,
        worker_id=worker_id,
        task_type=task_type,
        lease_seconds=lease_seconds,
        stage_concurrency_limits=(
            stage_concurrency_limits
            if stage_concurrency_limits is not None
            else settings.INGESTION_STAGE_CONCURRENCY_LIMITS
        ),
    )
    if not task:
        return None
    return run_leased_task(
        session, task, worker_id=worker_id, lease_seconds=lease_seconds
    )


def run_until_idle(
    session: Session,
    *,
    worker_id: str,
    max_tasks: int = 100,
) -> list[WorkerResult]:
    with source_files(session):
        results: list[WorkerResult] = []
        for _ in range(max_tasks):
            result = run_once(session, worker_id=worker_id)
            if result is None:
                break
            results.append(result)
        return results


def run_leased_task(
    session: Session,
    task: IngestionTask,
    *,
    worker_id: str,
    lease_seconds: int | None = None,
) -> WorkerResult:
    lease = TaskLease.from_task(task)
    if lease.worker_id != worker_id:
        raise IngestionLeaseLost("Task lease belongs to a different worker")
    run_id, stage = task.run_id, stage_for_task(task)
    expire_on_commit = session.expire_on_commit
    session.expire_on_commit = False
    try:
        return _run_leased_task(
            session,
            task,
            worker_id=worker_id,
            lease=lease,
            lease_seconds=lease_seconds or settings.INGESTION_WORKER_LEASE_SECONDS,
        )
    except IngestionLeaseLost:
        session.rollback()
        session.refresh(task)
        run = get_run(session, run_id)
        session.refresh(run)
        return WorkerResult(
            task_id=lease.task_id,
            run_id=run_id,
            stage=stage,
            task_status=task.status,
            run_status=run.status,
        )
    finally:
        session.expire_on_commit = expire_on_commit
        session.info.pop("ingestion_continue", None)


def _run_leased_task(
    session: Session,
    task: IngestionTask,
    *,
    worker_id: str,
    lease: TaskLease,
    lease_seconds: int,
) -> WorkerResult:
    run = get_run(session, task.run_id)
    stage = stage_for_task(task)
    step = get_step(session, run.id, stage, task.step_id)
    started_at = get_datetime_utc()
    task = mark_task_running(session, task, commit=False)
    with fence_stage_writes(session, lease):
        mark_step_running(
            session, step, worker_id=worker_id, started_at=started_at, commit=False
        )
        mark_run_running(session, run, stage=stage, commit=False)
        append_run_event(
            session,
            run,
            event_type="stage_started",
            message=f"{stage.value} started",
            step=step,
            payload={"worker_id": worker_id, "task_id": str(task.id)},
            commit=False,
        )

    session.commit()

    stop_heartbeat = threading.Event()
    lease_lost = threading.Event()

    def heartbeat() -> None:
        interval = max(1.0, lease_seconds / 3)
        failures = 0
        while not stop_heartbeat.wait(interval):
            try:
                from app.core.db import engine

                with Session(engine) as heartbeat_session:
                    if not renew_task_lease(
                        heartbeat_session,
                        task_id=lease.task_id,
                        worker_id=worker_id,
                        lease_seconds=lease_seconds,
                        lease_version=lease.version,
                    ):
                        lease_lost.set()
                        return
                failures = 0
            except Exception:
                failures += 1
                if failures >= 3:
                    lease_lost.set()
                    return

    def should_continue() -> None:
        if lease_lost.is_set():
            raise IngestionLeaseLost("Task lease was lost during stage execution")
        stopping = session.info.get("ingestion_stop_requested")
        if stopping and stopping():
            raise IngestionWorkerStopped("Worker shutdown requested")

    session.info["ingestion_continue"] = should_continue
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    try:
        should_continue()
        with fence_stage_writes(session, lease):
            outcome = handler_for(stage)(session, run, task)
        if lease_lost.is_set():
            raise IngestionLeaseLost("Task lease was lost during stage execution")
    except IngestionLeaseLost:
        raise
    except IngestionWorkerStopped:
        session.rollback()
        release_task(session, task, lease=lease, commit=False)
        step.status = IngestionStepStatus.PENDING
        step.lease_owner = None
        step.leased_until = None
        run.status = IngestionRunStatus.QUEUED
        session.add_all([step, run])
        append_run_event(
            session,
            run,
            event_type="stage_interrupted",
            message="Worker stopped; checkpointed work can resume",
            step=step,
            commit=False,
        )
        session.commit()
        return WorkerResult(
            task_id=task.id,
            run_id=run.id,
            stage=stage,
            task_status=task.status,
            run_status=run.status,
        )
    except Exception as exc:
        # A failed flush leaves SQLAlchemy unable to record task failure until
        # its transaction is rolled back. Discard partial stage writes first.
        session.rollback()
        return handle_stage_failure(
            session,
            run=run,
            step=step,
            task=task,
            stage=stage,
            exc=exc,
            lease=lease,
        )
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)

    completed_task = complete_task(session, task, commit=False, lease=lease)
    mark_step_succeeded(session, step, metrics=outcome.metrics, commit=False)
    append_run_event(
        session,
        run,
        event_type="stage_succeeded",
        message=f"{stage.value} completed",
        step=step,
        payload=outcome.metrics,
        commit=False,
    )
    advance_run_after_success(session, run, outcome=outcome, commit=False)
    session.commit()
    session.refresh(run)
    return WorkerResult(
        task_id=completed_task.id,
        run_id=run.id,
        stage=stage,
        task_status=completed_task.status,
        run_status=run.status,
    )


def advance_run_after_success(
    session: Session,
    run: IngestionRun,
    *,
    outcome: StageOutcome,
    commit: bool = True,
) -> None:
    now = get_datetime_utc()
    if outcome.next_task_payload:
        retain_pipeline_inputs(session, run, outcome.next_task_payload)
        run.pipeline_config = {
            **(run.pipeline_config or {}),
            "stage_inputs": {
                **(run.pipeline_config or {}).get("stage_inputs", {}),
                str(outcome.next_stage): outcome.next_task_payload,
            },
        }
    run.status = outcome.next_status
    if outcome.next_stage:
        run.current_stage = outcome.next_stage
    run.completed_units += 1
    run.lock_version += 1
    run.updated_at = now
    session.add(run)
    for skipped_stage in outcome.skipped_stages:
        skipped_step = get_step(session, run.id, skipped_stage, None)
        skipped_step.status = IngestionStepStatus.SKIPPED
        skipped_step.completed_at = now
        skipped_step.updated_at = now
        skipped_step.lock_version += 1
        session.add(skipped_step)
    if outcome.next_stage and outcome.block_next_stage:
        next_step = get_step(session, run.id, outcome.next_stage, None)
        next_step.status = IngestionStepStatus.BLOCKED
        next_step.metrics = outcome.metrics
        next_step.updated_at = now
        session.add(next_step)
        append_run_event(
            session,
            run,
            event_type="stage_blocked",
            message=f"{outcome.next_stage.value} requires admin input",
            step=next_step,
            payload=outcome.metrics,
            commit=False,
        )
    elif outcome.next_stage:
        next_step = get_step(session, run.id, outcome.next_stage, None)
        enqueue_task(
            session,
            run=run,
            step=next_step,
            task_type=outcome.next_stage.value,
            idempotency_key=f"{run.id}:{outcome.next_stage.value}:{run.lock_version}",
            payload=outcome.next_task_payload or {},
            priority=priority_for_stage(outcome.next_stage),
            commit=False,
        )
    if commit:
        session.commit()
    else:
        session.flush()


def handle_stage_failure(
    session: Session,
    *,
    run: IngestionRun,
    step: IngestionStep,
    task: IngestionTask,
    stage: IngestionStage,
    exc: Exception,
    lease: TaskLease | None = None,
) -> WorkerResult:
    error_details = {
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }
    failed_or_retryable_task = fail_task(
        session,
        task,
        error_details,
        lease=lease,
        commit=False,
        retryable=retryable_error(exc),
    )
    now = get_datetime_utc()
    step.error_details = error_details
    step.heartbeat_at = now
    step.updated_at = now
    if failed_or_retryable_task.status == IngestionTaskStatus.FAILED:
        step.status = IngestionStepStatus.FAILED
        step.completed_at = now
        run.status = IngestionRunStatus.FAILED
        if stage == IngestionStage.VERIFYING_UPLOAD:
            upload_id = task.payload.get("source_upload_id") or run.source_upload_id
            if upload_id:
                upload = session.get(SourceUpload, uuid.UUID(str(upload_id)))
                if upload:
                    upload.status = SourceUploadStatus.FAILED
                    upload.error_message = str(exc)[:2000]
                    upload.updated_at = now
                    upload.lock_version += 1
                    session.add(upload)
        run.failed_units += 1
        run.error_details = error_details
        run.updated_at = now
        session.add(run)
    else:
        step.status = IngestionStepStatus.PENDING
    session.add(step)
    append_run_event(
        session,
        run,
        event_type="stage_failed",
        message=str(exc),
        step=step,
        payload=error_details,
        commit=False,
    )
    session.commit()
    session.refresh(run)
    return WorkerResult(
        task_id=failed_or_retryable_task.id,
        run_id=run.id,
        stage=stage,
        task_status=failed_or_retryable_task.status,
        run_status=run.status,
    )


def mark_step_running(
    session: Session,
    step: IngestionStep,
    *,
    worker_id: str,
    started_at: datetime,
    commit: bool = True,
) -> None:
    now = get_datetime_utc()
    step.status = IngestionStepStatus.RUNNING
    step.lease_owner = worker_id
    step.heartbeat_at = now
    step.started_at = step.started_at or started_at
    step.attempt_count += 1
    step.lock_version += 1
    step.updated_at = now
    session.add(step)
    if commit:
        session.commit()


def mark_step_succeeded(
    session: Session,
    step: IngestionStep,
    *,
    metrics: dict[str, Any],
    commit: bool = True,
) -> None:
    now = get_datetime_utc()
    step.status = IngestionStepStatus.SUCCEEDED
    step.lease_owner = None
    step.leased_until = None
    step.heartbeat_at = now
    step.metrics = metrics
    step.completed_units = step.total_units or 1
    step.completed_at = now
    step.lock_version += 1
    step.updated_at = now
    session.add(step)
    if commit:
        session.commit()
    else:
        session.flush()


def mark_run_running(
    session: Session, run: IngestionRun, *, stage: IngestionStage, commit: bool = True
) -> None:
    run.status = IngestionRunStatus.RUNNING
    run.current_stage = stage
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add(run)
    if commit:
        session.commit()


def get_run(session: Session, run_id: uuid.UUID) -> IngestionRun:
    run = session.get(IngestionRun, run_id)
    if not run:
        raise IngestionWorkerError("Ingestion run was not found")
    return run


def get_step(
    session: Session,
    run_id: uuid.UUID,
    stage: IngestionStage,
    task_step_id: uuid.UUID | None,
) -> IngestionStep:
    if task_step_id:
        step = session.get(IngestionStep, task_step_id)
        if step:
            return step
    step = session.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run_id,
            IngestionStep.stage == stage,
        )
    ).first()
    if not step:
        raise IngestionWorkerError(f"Ingestion step {stage.value} was not found")
    return step


def stage_for_task(task: IngestionTask) -> IngestionStage:
    try:
        return IngestionStage(task.task_type)
    except ValueError:
        raise IngestionWorkerError(f"Unknown ingestion task type: {task.task_type}")


def priority_for_stage(stage: IngestionStage) -> int:
    return {
        IngestionStage.VERIFYING_UPLOAD: 10,
        IngestionStage.MALWARE_SCAN: 15,
        IngestionStage.PROFILING: 20,
        IngestionStage.RENDERING: 30,
        IngestionStage.NATIVE_EXTRACTION: 40,
        IngestionStage.LOCAL_OCR: 45,
        IngestionStage.MANAGED_OCR: 50,
        IngestionStage.NORMALIZING: 60,
        IngestionStage.PARSING_STRUCTURE: 70,
        IngestionStage.VALIDATING_DOCUMENT: 80,
    }.get(stage, 100)
