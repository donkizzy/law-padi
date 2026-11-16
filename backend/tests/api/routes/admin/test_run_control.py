import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import settings
from app.ingestion.runtime.queue import append_run_event
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
)
from app.legal.models import (
    IngestionEvent,
    IngestionStep,
    IngestionTask,
)
from tests.api.routes.admin.conftest import _source_and_run


def test_ingestion_run_events_replays_only_after_last_event_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _source, run = _source_and_run(db)
    profiling_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.PROFILING,
        )
    ).one()
    first_event = append_run_event(
        db,
        run,
        event_type="stage_started",
        message="Profiling started",
        step=profiling_step,
    )
    second_event = append_run_event(
        db,
        run,
        event_type="stage_succeeded",
        message="Profiling completed",
        stage=IngestionStage.PROFILING,
    )

    with client.stream(
        "GET",
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/events?replay_only=true",
        headers={
            **superuser_token_headers,
            "Last-Event-ID": str(first_event.sequence),
        },
    ) as response:
        assert response.status_code == 200
        response_text = next(response.iter_text())
        assert f"id: {second_event.sequence}" in response_text
        assert "stage_succeeded" in response_text
        assert "Profiling completed" in response_text
        assert f"id: {first_event.sequence}" not in response_text
        assert "Profiling started" not in response_text


def test_run_control_mutations_are_idempotent(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _source, cancel_run = _source_and_run(db)
    cancel_body = {
        "idempotency_key": f"cancel-{uuid.uuid4().hex}",
        "expected_version": cancel_run.lock_version,
        "reason": "Operator cancelled run",
    }
    cancel_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{cancel_run.id}/cancel",
        headers=superuser_token_headers,
        json=cancel_body,
    )
    assert cancel_response.status_code == 200
    repeated_cancel = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{cancel_run.id}/cancel",
        headers=superuser_token_headers,
        json=cancel_body,
    )
    assert repeated_cancel.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionEvent)
            .where(
                IngestionEvent.run_id == cancel_run.id,
                IngestionEvent.event_type == "run_cancelled",
            )
        ).one()
        == 1
    )

    _source, resume_run = _source_and_run(db)
    resume_run.status = IngestionRunStatus.WAITING_FOR_INPUT
    resume_run.current_stage = IngestionStage.AWAITING_PAGE_CONFIRMATION
    db.add(resume_run)
    db.commit()
    db.refresh(resume_run)
    resume_body = {
        "idempotency_key": f"resume-{uuid.uuid4().hex}",
        "expected_version": resume_run.lock_version,
    }
    resume_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{resume_run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )
    assert resume_response.status_code == 200
    db.refresh(resume_run)
    assert resume_run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert resume_run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    repeated_resume = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{resume_run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )
    assert repeated_resume.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionEvent)
            .where(
                IngestionEvent.run_id == resume_run.id,
                IngestionEvent.event_type == "run_resume_not_required",
            )
        ).one()
        == 1
    )

    _source, retry_run = _source_and_run(db)
    retry_run.status = IngestionRunStatus.FAILED
    retry_run.current_stage = IngestionStage.NATIVE_EXTRACTION
    db.add(retry_run)
    db.commit()
    db.refresh(retry_run)
    retry_body = {
        "idempotency_key": f"retry-{uuid.uuid4().hex}",
        "expected_version": retry_run.lock_version,
    }
    retry_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{retry_run.id}/retry",
        headers=superuser_token_headers,
        json=retry_body,
    )
    assert retry_response.status_code == 200
    repeated_retry = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{retry_run.id}/retry",
        headers=superuser_token_headers,
        json=retry_body,
    )
    assert repeated_retry.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == retry_run.id,
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
            )
        ).one()
        == 1
    )


def test_retry_keeps_the_failed_stage_task_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _source, run = _source_and_run(db)
    run.status = IngestionRunStatus.FAILED
    run.current_stage = IngestionStage.EMBEDDING
    release_id = str(uuid.uuid4())
    db.add(run)
    db.add(
        IngestionTask(
            run_id=run.id,
            task_type=IngestionStage.EMBEDDING.value,
            status=IngestionTaskStatus.FAILED,
            idempotency_key=f"{run.id}:embedding:manual",
            payload={"release_id": release_id, "source_document_id": "source"},
            created_at=datetime(2026, 10, 23, 10, 0, tzinfo=UTC),
        )
    )
    # A later retry that held only the flag must not hide the stage's inputs.
    db.add(
        IngestionTask(
            run_id=run.id,
            task_type=IngestionStage.EMBEDDING.value,
            status=IngestionTaskStatus.FAILED,
            idempotency_key=f"{run.id}:embedding:retry:old",
            payload={"retry": True},
            created_at=datetime(2026, 10, 23, 11, 0, tzinfo=UTC),
        )
    )
    db.commit()
    db.refresh(run)

    response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/retry",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"retry-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
        },
    )

    assert response.status_code == 200
    retry_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.status == IngestionTaskStatus.PENDING,
        )
    ).one()
    assert retry_task.payload == {
        "release_id": release_id,
        "source_document_id": "source",
        "retry": True,
    }


def test_resume_cancelled_run_requeues_current_stage_once(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    run.status = IngestionRunStatus.CANCELLED
    run.current_stage = IngestionStage.NATIVE_EXTRACTION
    run.error_details = {"reason": "Operator cancelled run"}
    step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NATIVE_EXTRACTION,
        )
    ).one()
    step.status = IngestionStepStatus.CANCELLED
    step.completed_at = datetime.now(UTC)
    db.add(run)
    db.add(step)
    db.commit()
    db.refresh(run)
    resume_body = {
        "idempotency_key": f"resume-{uuid.uuid4().hex}",
        "expected_version": run.lock_version,
    }

    resume_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )

    assert resume_response.status_code == 200
    db.refresh(run)
    db.refresh(step)
    assert run.status == IngestionRunStatus.QUEUED
    assert run.current_stage == IngestionStage.NATIVE_EXTRACTION
    assert step.status == IngestionStepStatus.PENDING
    assert step.completed_at is None
    tasks = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
        )
    ).all()
    assert len(tasks) == 1
    assert tasks[0].status == IngestionTaskStatus.PENDING
    assert tasks[0].payload == {
        "resume": True,
        "source_document_id": str(source.id),
    }

    repeated_resume = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )

    assert repeated_resume.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
            )
        ).one()
        == 1
    )
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionEvent)
            .where(
                IngestionEvent.run_id == run.id,
                IngestionEvent.event_type == "run_resumed",
            )
        ).one()
        == 1
    )
