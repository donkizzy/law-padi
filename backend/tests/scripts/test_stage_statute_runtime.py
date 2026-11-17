import pytest
from sqlmodel import Session, select

from app.ingestion.runtime import runner
from app.ingestion.runtime.queue import create_run_steps, enqueue_task
from app.ingestion.runtime.types import StageOutcome
from app.legal.enums import IngestionRunStatus, IngestionStage, IngestionTaskStatus
from app.legal.models import IngestionRun, IngestionTask
from scripts.stage_statute_review import run_to_review


def test_review_import_uses_fenced_runtime_for_only_its_own_tasks(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stages = (
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    )
    queued = []
    for priority in (1, 10):
        run = IngestionRun(status=IngestionRunStatus.QUEUED, current_stage=stages[0])
        db.add(run)
        db.flush()
        steps = create_run_steps(db, run, (*stages, IngestionStage.REVIEW))
        task = enqueue_task(
            db,
            run=run,
            step=steps[0],
            task_type=str(stages[0]),
            idempotency_key=f"{run.id}:first",
            priority=priority,
        )
        queued.append((run, task))
    other_run, other_task = queued[0]
    selected, _ = queued[1]
    executed = []

    def handle(
        _session: Session, run: IngestionRun, task: IngestionTask
    ) -> StageOutcome:
        assert run.id == selected.id
        assert task.lease_owner == "statute-review-import"
        assert task.attempt_count == 1
        assert task.heartbeat_at is not None
        executed.append(task.task_type)
        stage = IngestionStage(task.task_type)
        index = stages.index(stage)
        return StageOutcome(
            metrics={"review_import": True},
            next_stage=stages[index + 1] if index < 2 else IngestionStage.REVIEW,
            block_next_stage=index == 2,
            next_status=IngestionRunStatus.WAITING_FOR_REVIEW
            if index == 2
            else IngestionRunStatus.RUNNING,
        )

    monkeypatch.setattr(runner, "handler_for", lambda _: handle)
    try:
        run_to_review(db, selected)
        assert executed == list(stages)
        db.refresh(selected)
        db.refresh(other_task)
        assert selected.status == IngestionRunStatus.WAITING_FOR_REVIEW
        assert other_task.status == IngestionTaskStatus.PENDING
        assert other_task.attempt_count == 0
        tasks = db.exec(
            select(IngestionTask).where(IngestionTask.run_id == selected.id)
        ).all()
        assert len(tasks) == 3
        assert all(task.status == IngestionTaskStatus.SUCCEEDED for task in tasks)
        assert all(task.lease_owner is None for task in tasks)
    finally:
        db.rollback()
        db.delete(selected)
        db.delete(other_run)
        db.commit()
