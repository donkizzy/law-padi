from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import update
from sqlmodel import Session, select

from app.ingestion.common import get_datetime_utc
from app.ingestion.runtime import queue, runner
from app.legal.enums import IngestionRunStatus, IngestionStage, IngestionTaskStatus
from app.legal.models import IngestionEvent, IngestionRun, IngestionTask


@pytest.mark.parametrize("operation", ["complete", "fail", "renew", "start"])
@pytest.mark.parametrize("replacement_owner", ["worker-b", "worker-a"])
def test_stale_lease_cannot_write_task(
    db: Session, operation: str, replacement_owner: str
) -> None:
    run = IngestionRun(status=IngestionRunStatus.QUEUED)
    db.add(run)
    db.commit()
    task = queue.enqueue_task(
        db, run=run, step=None, task_type="profiling", idempotency_key=str(run.id)
    )
    task_id = task.id
    stale = queue.lease_next_task(db, worker_id="worker-a", task_type="profiling")
    assert stale is not None
    lease_version = stale.attempt_count
    with Session(db.get_bind()) as other:
        other.execute(
            update(IngestionTask)
            .where(IngestionTask.id == task_id)
            .values(leased_until=get_datetime_utc() - timedelta(seconds=1))
        )
        other.commit()
        replacement = queue.lease_next_task(
            other, worker_id=replacement_owner, task_type="profiling"
        )
        assert replacement is not None and replacement.id == task_id
    if operation == "renew":
        assert not queue.renew_task_lease(
            db,
            task_id=task_id,
            worker_id="worker-a",
            lease_version=lease_version,
            lease_seconds=60,
        )
    else:
        with pytest.raises(RuntimeError, match="lease"):
            if operation == "complete":
                queue.complete_task(db, stale)
            elif operation == "fail":
                queue.fail_task(db, stale, {"message": "stale failure"})
            else:
                queue.mark_task_running(db, stale)
    db.rollback()
    db.refresh(task)
    assert task.status == IngestionTaskStatus.LEASED
    assert task.lease_owner == replacement_owner
    assert task.attempt_count == 2
    assert task.error_details is None
    queue.mark_run_cancelled(db, run, "test cleanup")


@pytest.mark.parametrize("fail_handler", [False, True])
def test_stale_handler_cannot_commit_or_fail_new_owner(
    db: Session, monkeypatch: pytest.MonkeyPatch, fail_handler: bool
) -> None:
    run = IngestionRun(status=IngestionRunStatus.QUEUED)
    db.add(run)
    db.commit()
    steps = queue.create_run_steps(db, run, (IngestionStage.PROFILING,))
    task = queue.enqueue_task(
        db, run=run, step=steps[0], task_type="profiling", idempotency_key=str(run.id)
    )
    task.max_attempts = 1
    db.commit()
    task_id, run_id = task.id, run.id

    def handler(session: Session, run: IngestionRun, _task: IngestionTask) -> Any:
        session.commit()
        with Session(db.get_bind()) as other:
            other.execute(
                update(IngestionTask)
                .where(IngestionTask.id == task_id)
                .values(leased_until=get_datetime_utc() - timedelta(seconds=1))
            )
            other.commit()
            replacement = queue.lease_next_task(
                other, worker_id="worker-b", task_type="profiling"
            )
            assert replacement is not None and replacement.id == task_id
        if fail_handler:
            raise RuntimeError("old worker failed")
        run.failed_units = 99
        session.add(run)
        session.commit()
        return runner.StageOutcome(metrics={})

    monkeypatch.setattr(runner, "handler_for", lambda _stage: handler)
    result = runner.run_once(db, worker_id="worker-a", task_type="profiling")
    assert result is not None
    db.refresh(task)
    db.refresh(run)
    db.refresh(steps[0])
    assert task.lease_owner == "worker-b"
    assert task.status == IngestionTaskStatus.LEASED
    assert run.status == IngestionRunStatus.RUNNING
    assert run.failed_units == 0
    assert steps[0].status != "failed"
    events = db.exec(
        select(IngestionEvent).where(IngestionEvent.run_id == run_id)
    ).all()
    assert [event.event_type for event in events] == ["stage_started"]
    queue.mark_run_cancelled(db, run, "test cleanup")


@pytest.mark.parametrize("failures", [1, 3])
def test_heartbeat_retries_database_blips(
    db: Session, monkeypatch: pytest.MonkeyPatch, failures: int
) -> None:
    from types import SimpleNamespace

    run = IngestionRun(status=IngestionRunStatus.QUEUED)
    db.add(run)
    db.commit()
    step = queue.create_run_steps(db, run, (IngestionStage.PROFILING,))[0]
    queue.enqueue_task(
        db, run=run, step=step, task_type="profiling", idempotency_key=str(run.id)
    )
    calls: list[dict[str, Any]] = []

    class Event:
        def __init__(self) -> None:
            self.set_value = False
            self.waits = 0

        def set(self) -> None:
            self.set_value = True

        def is_set(self) -> bool:
            return self.set_value

        def wait(self, _interval: float) -> bool:
            self.waits += 1
            return self.set_value or self.waits > 4

    class Thread:
        def __init__(self, *, target: Any, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

        def join(self, *, timeout: int) -> None:
            pass

    def renew(_session: Session, **kwargs: Any) -> bool:
        calls.append(kwargs)
        if len(calls) <= failures:
            raise ConnectionError("temporary database outage")
        return True

    monkeypatch.setattr(
        runner, "threading", SimpleNamespace(Event=Event, Thread=Thread)
    )
    monkeypatch.setattr(runner, "renew_task_lease", renew)
    monkeypatch.setattr(
        runner,
        "handler_for",
        lambda _stage: lambda *_args: runner.StageOutcome(metrics={}),
    )
    result = runner.run_once(
        db, worker_id="worker-a", task_type="profiling", lease_seconds=12
    )
    assert result is not None
    assert all(call["lease_seconds"] == 12 for call in calls)
    assert all(call["lease_version"] == 1 for call in calls)
    if failures == 1:
        assert result.task_status == IngestionTaskStatus.SUCCEEDED
        assert len(calls) == 4
    else:
        assert result.task_status == IngestionTaskStatus.RUNNING
        assert len(calls) == 3
    queue.mark_run_cancelled(db, run, "test cleanup")


def test_worker_starts_task_step_run_and_event_in_one_commit(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import event

    run = IngestionRun(status=IngestionRunStatus.QUEUED)
    db.add(run)
    db.commit()
    step = queue.create_run_steps(db, run, (IngestionStage.PROFILING,))[0]
    queue.enqueue_task(
        db, run=run, step=step, task_type="profiling", idempotency_key=str(run.id)
    )
    task = queue.lease_next_task(db, worker_id="worker-a", task_type="profiling")
    assert task is not None
    commits: list[None] = []

    def count_commits(_session: Session) -> None:
        commits.append(None)

    def handler(*_args: Any) -> runner.StageOutcome:
        assert len(commits) == 1
        return runner.StageOutcome(metrics={})

    monkeypatch.setattr(runner, "handler_for", lambda _stage: handler)
    event.listen(db, "after_commit", count_commits)
    try:
        result = runner.run_leased_task(db, task, worker_id="worker-a")
    finally:
        event.remove(db, "after_commit", count_commits)
    assert result.task_status == IngestionTaskStatus.SUCCEEDED
    assert len(commits) == 2


def test_shutdown_keeps_checkpoint_and_releases_task_immediately(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ingestion.runtime.control import check_stage_continue

    run = IngestionRun(status=IngestionRunStatus.QUEUED)
    db.add(run)
    db.commit()
    step = queue.create_run_steps(db, run, (IngestionStage.PROFILING,))[0]
    task = queue.enqueue_task(
        db, run=run, step=step, task_type="profiling", idempotency_key=str(run.id)
    )
    stopping = [False]
    db.info["ingestion_stop_requested"] = lambda: stopping[0]

    def handler(
        session: Session, current_run: IngestionRun, _task: IngestionTask
    ) -> Any:
        for number in range(1, 4):
            check_stage_continue(session)
            current_run.completed_units = number
            session.add(current_run)
            session.commit()
            stopping[0] = True
        return runner.StageOutcome(metrics={})

    monkeypatch.setattr(runner, "handler_for", lambda _: handler)
    try:
        result = runner.run_once(db, worker_id="stopping-worker", task_type="profiling")
        assert result is not None and result.task_status == IngestionTaskStatus.PENDING
        db.refresh(run)
        db.refresh(task)
        assert run.completed_units == 1
        assert run.status == IngestionRunStatus.QUEUED
        assert task.lease_owner is None
        assert task.max_attempts == 4
        next_task = queue.lease_next_task(
            db, worker_id="next-worker", task_type="profiling"
        )
        assert next_task is not None and next_task.id == task.id
        assert next_task.attempt_count == 2
    finally:
        db.info.pop("ingestion_stop_requested", None)
        queue.mark_run_cancelled(db, run, "test cleanup")


def test_stage_logs_carry_the_task_and_run(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import logging

    from tests.utils.logs import captured_logs

    run = IngestionRun(status=IngestionRunStatus.QUEUED)
    db.add(run)
    db.commit()
    step = queue.create_run_steps(db, run, (IngestionStage.PROFILING,))[0]
    queue.enqueue_task(
        db, run=run, step=step, task_type="profiling", idempotency_key=str(run.id)
    )
    task = queue.lease_next_task(db, worker_id="worker-a", task_type="profiling")
    assert task is not None

    def handler(*_args: Any) -> runner.StageOutcome:
        logging.getLogger("app.ingestion.stages.test").info("stage_progress")
        return runner.StageOutcome(metrics={})

    monkeypatch.setattr(runner, "handler_for", lambda _stage: handler)
    with captured_logs("app.ingestion") as records:
        runner.run_leased_task(db, task, worker_id="worker-a")
    (record,) = [r for r in records if r.getMessage() == "stage_progress"]
    assert record.__dict__["task_id"] == str(task.id)
    assert record.__dict__["run_id"] == str(run.id)
