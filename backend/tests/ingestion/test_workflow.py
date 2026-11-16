from collections.abc import Generator

import pytest
from sqlmodel import Session, delete, select

from app.ingestion.runtime.queue import (
    PIPELINE_STAGES,
    append_run_event,
    complete_task,
    create_run_steps,
    enqueue_task,
    fail_task,
    lease_next_task,
    mark_run_cancelled,
    mark_task_running,
)
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


@pytest.fixture(autouse=True)
def isolate_workflow_tables(db: Session) -> Generator[None]:
    db.rollback()
    for model in (
        TransactionalOutbox,
        IngestionTask,
        IngestionEvent,
        IngestionStep,
        IngestionRun,
    ):
        db.exec(delete(model))
    db.commit()
    yield
    db.rollback()
    for model in (
        TransactionalOutbox,
        IngestionTask,
        IngestionEvent,
        IngestionStep,
        IngestionRun,
    ):
        db.exec(delete(model))
    db.commit()


def test_create_run_steps_tracks_the_full_plan_stage_order(db: Session) -> None:
    run = _create_run(db)

    steps = create_run_steps(db, run)

    assert [step.stage for step in steps] == list(PIPELINE_STAGES)
    assert steps[0].dependency_step_id is None
    assert steps[1].dependency_step_id == steps[0].id
    assert steps[-1].stage == IngestionStage.PUBLISHING
    assert all(step.status == IngestionStepStatus.PENDING for step in steps)

    same_steps = create_run_steps(db, run)
    assert [step.id for step in same_steps] == [step.id for step in steps]


def test_append_run_event_assigns_monotonic_sequences_for_sse_replay(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.PROFILING,))

    first = append_run_event(
        db,
        run,
        event_type="stage_started",
        message="Profiling started",
        step=steps[0],
        payload={"worker": "worker-1"},
    )
    second = append_run_event(
        db,
        run,
        event_type="stage_succeeded",
        message="Profiling complete",
        stage=IngestionStage.PROFILING,
    )

    events = db.exec(
        select(IngestionEvent)
        .where(IngestionEvent.run_id == run.id)
        .order_by(IngestionEvent.sequence)
    ).all()
    assert [event.sequence for event in events] == [1, 2]
    assert first.stage == IngestionStage.PROFILING
    assert second.stage == IngestionStage.PROFILING
    outbox_events = db.exec(
        select(TransactionalOutbox)
        .where(TransactionalOutbox.aggregate_id == run.id)
        .order_by(TransactionalOutbox.created_at)
    ).all()
    assert [event.event_type for event in outbox_events] == [
        "ingestion_event.stage_started",
        "ingestion_event.stage_succeeded",
    ]
    assert [event.payload["sequence"] for event in outbox_events] == [1, 2]


def test_enqueue_and_lease_task_is_idempotent_and_ordered_by_priority(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.PROFILING,))
    task = enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.PROFILING.value,
        idempotency_key=f"{run.id}:profile",
        payload={"page_range": [1, 10]},
        priority=10,
    )
    duplicate = enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.PROFILING.value,
        idempotency_key=f"{run.id}:profile",
        priority=1,
    )

    assert duplicate.id == task.id
    assert duplicate.payload == {"page_range": [1, 10]}
    task_outbox_events = db.exec(
        select(TransactionalOutbox).where(
            TransactionalOutbox.event_type == "ingestion_task.enqueued",
            TransactionalOutbox.aggregate_id == task.id,
        )
    ).all()
    assert len(task_outbox_events) == 1
    assert task_outbox_events[0].payload["payload"] == {"page_range": [1, 10]}

    leased = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.PROFILING.value,
        lease_seconds=60,
    )

    assert leased is not None
    assert leased.id == task.id
    assert leased.status == IngestionTaskStatus.LEASED
    assert leased.lease_owner == "worker-1"
    assert leased.attempt_count == 1
    assert leased.lock_version == 2


def test_task_lifecycle_supports_running_completion_and_retryable_failure(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.NATIVE_EXTRACTION,))
    enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:extract",
    )

    leased = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
    )
    assert leased is not None

    running = mark_task_running(db, leased)
    assert running.status == IngestionTaskStatus.RUNNING
    assert running.lock_version == 3

    retryable = fail_task(db, running, {"code": "temporary_error"})
    assert retryable.status == IngestionTaskStatus.PENDING
    assert retryable.error_details == {"code": "temporary_error"}
    assert retryable.lock_version == 4

    leased_again = lease_next_task(
        db,
        worker_id="worker-2",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
    )
    assert leased_again is not None
    assert leased_again.lock_version == 5
    completed = complete_task(db, leased_again)
    assert completed.status == IngestionTaskStatus.SUCCEEDED
    assert completed.lease_owner is None
    assert completed.lock_version == 6


def test_expired_leased_task_can_be_reclaimed_by_another_worker(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.NATIVE_EXTRACTION,))
    enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:expired-lease",
    )
    first_lease = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        lease_seconds=-1,
    )
    assert first_lease is not None
    assert first_lease.status == IngestionTaskStatus.LEASED

    reclaimed = lease_next_task(
        db,
        worker_id="worker-2",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
    )

    assert reclaimed is not None
    assert reclaimed.id == first_lease.id
    assert reclaimed.status == IngestionTaskStatus.LEASED
    assert reclaimed.lease_owner == "worker-2"
    assert reclaimed.attempt_count == 2


def test_expired_running_task_can_be_reclaimed_after_worker_crash(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.NATIVE_EXTRACTION,))
    enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:expired-running",
    )
    first_lease = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        lease_seconds=-1,
    )
    assert first_lease is not None
    running = mark_task_running(db, first_lease)
    assert running.status == IngestionTaskStatus.RUNNING

    reclaimed = lease_next_task(
        db,
        worker_id="worker-2",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
    )

    assert reclaimed is not None
    assert reclaimed.id == running.id
    assert reclaimed.status == IngestionTaskStatus.LEASED
    assert reclaimed.lease_owner == "worker-2"
    assert reclaimed.attempt_count == 2


def test_active_running_task_is_not_reclaimed(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.NATIVE_EXTRACTION,))
    enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:active-running",
    )
    leased = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        lease_seconds=60,
    )
    assert leased is not None
    mark_task_running(db, leased)

    assert (
        lease_next_task(
            db,
            worker_id="worker-2",
            task_type=IngestionStage.NATIVE_EXTRACTION.value,
        )
        is None
    )


def test_stage_concurrency_limit_blocks_additional_active_tasks(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.NATIVE_EXTRACTION,))
    first_task = enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:extract-1",
    )
    enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:extract-2",
    )
    leased = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        lease_seconds=60,
        stage_concurrency_limits={IngestionStage.NATIVE_EXTRACTION.value: 1},
    )
    assert leased is not None
    assert leased.id == first_task.id

    assert (
        lease_next_task(
            db,
            worker_id="worker-2",
            task_type=IngestionStage.NATIVE_EXTRACTION.value,
            stage_concurrency_limits={IngestionStage.NATIVE_EXTRACTION.value: 1},
        )
        is None
    )


def test_stage_concurrency_limit_skips_capped_stage_and_leases_next_type(
    db: Session,
) -> None:
    run = _create_run(db)
    steps = create_run_steps(
        db, run, (IngestionStage.PROFILING, IngestionStage.NATIVE_EXTRACTION)
    )
    profiling_step = steps[0]
    extraction_step = steps[1]
    enqueue_task(
        db,
        run=run,
        step=profiling_step,
        task_type=IngestionStage.PROFILING.value,
        idempotency_key=f"{run.id}:profile-active",
        priority=1,
    )
    pending_profile = enqueue_task(
        db,
        run=run,
        step=profiling_step,
        task_type=IngestionStage.PROFILING.value,
        idempotency_key=f"{run.id}:profile-pending",
        priority=2,
    )
    pending_extract = enqueue_task(
        db,
        run=run,
        step=extraction_step,
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:extract-pending",
        priority=3,
    )
    active_profile = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.PROFILING.value,
        lease_seconds=60,
    )
    assert active_profile is not None

    leased = lease_next_task(
        db,
        worker_id="worker-2",
        stage_concurrency_limits={IngestionStage.PROFILING.value: 1},
    )

    assert leased is not None
    assert leased.id == pending_extract.id
    db.refresh(pending_profile)
    assert pending_profile.status == IngestionTaskStatus.PENDING


def test_terminal_run_tasks_are_not_leased(db: Session) -> None:
    run = _create_run(db)
    steps = create_run_steps(db, run, (IngestionStage.NATIVE_EXTRACTION,))
    enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:terminal-run-task",
    )
    run.status = IngestionRunStatus.FAILED
    db.add(run)
    db.commit()

    assert (
        lease_next_task(
            db,
            worker_id="worker-1",
            task_type=IngestionStage.NATIVE_EXTRACTION.value,
        )
        is None
    )


def test_cancel_run_marks_terminal_status_and_appends_event(db: Session) -> None:
    run = _create_run(db)
    steps = create_run_steps(
        db, run, (IngestionStage.PROFILING, IngestionStage.NATIVE_EXTRACTION)
    )
    running_task = enqueue_task(
        db,
        run=run,
        step=steps[0],
        task_type=IngestionStage.PROFILING.value,
        idempotency_key=f"{run.id}:profile",
        priority=10,
    )
    pending_task = enqueue_task(
        db,
        run=run,
        step=steps[1],
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:extract",
        priority=20,
    )
    leased = lease_next_task(
        db,
        worker_id="worker-1",
        task_type=IngestionStage.PROFILING.value,
    )
    assert leased is not None
    assert leased.id == running_task.id
    mark_task_running(db, leased)
    steps[0].status = IngestionStepStatus.RUNNING
    steps[1].status = IngestionStepStatus.BLOCKED
    db.add(steps[0])
    db.add(steps[1])
    db.commit()

    cancelled = mark_run_cancelled(db, run, "Admin cancelled stale run")

    assert cancelled.status == IngestionRunStatus.CANCELLED
    assert cancelled.error_details == {"reason": "Admin cancelled stale run"}
    event = db.exec(select(IngestionEvent).where(IngestionEvent.run_id == run.id)).one()
    assert event.event_type == "run_cancelled"
    tasks = db.exec(
        select(IngestionTask)
        .where(IngestionTask.run_id == run.id)
        .order_by(IngestionTask.priority)
    ).all()
    assert [task.id for task in tasks] == [running_task.id, pending_task.id]
    assert [task.status for task in tasks] == [
        IngestionTaskStatus.CANCELLED,
        IngestionTaskStatus.CANCELLED,
    ]
    assert all(task.lease_owner is None for task in tasks)
    assert all(task.leased_until is None for task in tasks)
    assert [step.status for step in steps] == [
        IngestionStepStatus.CANCELLED,
        IngestionStepStatus.CANCELLED,
    ]
    assert (
        lease_next_task(
            db,
            worker_id="worker-2",
            task_type=IngestionStage.NATIVE_EXTRACTION.value,
        )
        is None
    )


def _create_run(db: Session) -> IngestionRun:
    run = IngestionRun(
        status=IngestionRunStatus.QUEUED,
        current_stage=IngestionStage.UPLOADING,
        pipeline_config={"max_pages": 1000},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_outbox_drain_marks_pending_events_published(db: Session) -> None:
    from app.ingestion.runtime.queue import append_run_event, drain_outbox_batch
    from app.legal.models import IngestionRun, TransactionalOutbox

    run = IngestionRun(source_document_id=None)
    db.add(run)
    db.commit()
    db.refresh(run)
    append_run_event(db, run=run, event_type="run_queued", message="queued")
    db.commit()

    pending = drain_outbox_batch(db)
    assert len(pending) >= 1
    db.rollback()

    published = drain_outbox_batch(db, publisher=lambda _event: None)
    assert len(published) >= 1
    db.commit()
    stored = db.get(TransactionalOutbox, pending[0].id)
    assert stored
    assert stored.published_at is not None
