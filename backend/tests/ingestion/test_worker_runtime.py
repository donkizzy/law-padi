import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_ROOT = REPO_ROOT / "services" / "ingestion-worker"
sys.path.insert(0, str(WORKER_ROOT))

from ingestion_worker.cli import (  # noqa: E402
    WorkerSettings,
    run_worker,
)

from app.legal.enums import (  # noqa: E402
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
)


@dataclass(frozen=True)
class FakeWorkerResult:
    task_id: uuid.UUID
    run_id: uuid.UUID
    stage: IngestionStage | str
    task_status: IngestionTaskStatus | str
    run_status: IngestionRunStatus | str


def test_worker_package_is_independent_python_312_runtime() -> None:
    pyproject = (WORKER_ROOT / "pyproject.toml").read_text()
    dockerfile = (WORKER_ROOT / "Dockerfile").read_text()

    assert 'requires-python = ">=3.12,<3.13"' in pyproject
    assert "[tool.uv.workspace]" not in pyproject
    assert "FROM python:3.12-slim" in dockerfile
    assert "poppler-utils" in dockerfile
    assert "tesseract-ocr" in dockerfile
    assert "PYTHONPATH=/app/backend:/app/services/ingestion-worker" in dockerfile
    assert 'CMD ["python", "-m", "ingestion_worker.cli"]' in dockerfile


def test_compose_runs_worker_as_separate_service_with_shared_storage() -> None:
    compose = (REPO_ROOT / "compose.yml").read_text()

    assert "\n  ingestion-worker:\n" in compose
    assert "dockerfile: services/ingestion-worker/Dockerfile" in compose
    assert "INGESTION_WORKER_POLL_INTERVAL_SECONDS" in compose
    assert "INGESTION_WORKER_LEASE_SECONDS" in compose
    assert "INGESTION_WORKER_MAX_TASKS_PER_POLL" in compose
    assert "INGESTION_STAGE_CONCURRENCY_LIMITS" in compose
    assert "MALWARE_SCANNER_BACKEND" in compose
    assert "CLAMAV_HOST" in compose
    assert "CLAMAV_PORT" in compose
    assert "QDRANT_URL: ${QDRANT_URL:-}" in compose
    assert "OPENAI_API_KEY: ${OPENAI_API_KEY:-}" in compose
    assert (
        "- app-ingestion-source-documents:/app/backend/storage/source-documents"
        in compose
    )


def test_worker_settings_read_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("INGESTION_WORKER_ID", "worker-a")
    monkeypatch.setenv("INGESTION_WORKER_POLL_INTERVAL_SECONDS", "0.25")
    monkeypatch.setenv("INGESTION_WORKER_LEASE_SECONDS", "120")
    monkeypatch.setenv("INGESTION_WORKER_MAX_TASKS_PER_POLL", "3")
    monkeypatch.setenv("INGESTION_WORKER_TASK_TYPE", "profiling")
    monkeypatch.setenv(
        "INGESTION_STAGE_CONCURRENCY_LIMITS",
        '{"embedding": 1, "indexing": 2}',
    )

    settings = WorkerSettings.from_env()

    assert settings == WorkerSettings(
        worker_id="worker-a",
        poll_interval_seconds=0.25,
        lease_seconds=120,
        max_tasks_per_poll=3,
        task_type="profiling",
        stage_concurrency_limits={"embedding": 1, "indexing": 2},
    )


def test_worker_loop_processes_batches_then_sleeps_when_idle() -> None:
    sessions: list[object] = []
    sleeps: list[float] = []
    calls: list[dict[str, Any]] = []
    task_results: list[FakeWorkerResult | None] = [
        _fake_result(),
        _fake_result(stage=IngestionStage.PROFILING),
        None,
        None,
    ]

    @contextmanager
    def session_factory() -> Iterator[object]:
        session = object()
        sessions.append(session)
        yield session

    def fake_run_once(
        session: object,
        *,
        worker_id: str,
        task_type: str | None,
        lease_seconds: int,
        stage_concurrency_limits: dict[str, int],
    ) -> FakeWorkerResult | None:
        calls.append(
            {
                "session": session,
                "worker_id": worker_id,
                "task_type": task_type,
                "lease_seconds": lease_seconds,
                "stage_concurrency_limits": stage_concurrency_limits,
            }
        )
        return task_results.pop(0)

    stats = run_worker(
        settings=WorkerSettings(
            worker_id="worker-a",
            poll_interval_seconds=1.5,
            lease_seconds=60,
            max_tasks_per_poll=3,
            task_type=IngestionStage.PROFILING.value,
            stage_concurrency_limits={IngestionStage.PROFILING.value: 1},
        ),
        session_factory=session_factory,
        sleep=sleeps.append,
        max_iterations=2,
        run_once_fn=fake_run_once,
    )

    assert stats.iterations == 2
    assert stats.tasks_processed == 2
    assert stats.idle_polls == 1
    assert sleeps == [1.5]
    assert len(sessions) == 4
    assert all(call["worker_id"] == "worker-a" for call in calls)
    assert all(call["task_type"] == "profiling" for call in calls)
    assert all(call["lease_seconds"] == 60 for call in calls)
    assert all(call["stage_concurrency_limits"] == {"profiling": 1} for call in calls)


def test_worker_loop_logs_string_status_results() -> None:
    task_results: list[FakeWorkerResult | None] = [
        _fake_result(
            task_status=IngestionTaskStatus.SUCCEEDED.value,
            run_status=IngestionRunStatus.RUNNING.value,
        ),
        None,
    ]

    @contextmanager
    def session_factory() -> Iterator[object]:
        yield object()

    def fake_run_once(
        _session: object,
        *,
        worker_id: str,
        task_type: str | None,
        lease_seconds: int,
        stage_concurrency_limits: dict[str, int],
    ) -> FakeWorkerResult | None:
        del worker_id, task_type, lease_seconds, stage_concurrency_limits
        return task_results.pop(0)

    stats = run_worker(
        settings=WorkerSettings(
            worker_id="worker-a",
            poll_interval_seconds=0,
            lease_seconds=60,
            max_tasks_per_poll=2,
        ),
        session_factory=session_factory,
        sleep=lambda _seconds: None,
        max_iterations=1,
        run_once_fn=fake_run_once,
    )

    assert stats.tasks_processed == 1


def test_worker_loop_rejects_invalid_poll_settings() -> None:
    invalid_settings = WorkerSettings(
        worker_id="worker-a",
        poll_interval_seconds=-1,
        lease_seconds=60,
        max_tasks_per_poll=1,
    )

    try:
        run_worker(settings=invalid_settings, sleep=lambda _seconds: None)
    except ValueError as exc:
        assert "POLL_INTERVAL" in str(exc)
    else:
        raise AssertionError("negative poll interval should fail fast")


def test_worker_loop_rejects_invalid_stage_concurrency_limits() -> None:
    invalid_settings = WorkerSettings(
        worker_id="worker-a",
        poll_interval_seconds=1,
        lease_seconds=60,
        max_tasks_per_poll=1,
        stage_concurrency_limits={"embedding": 0},
    )

    try:
        run_worker(settings=invalid_settings, sleep=lambda _seconds: None)
    except ValueError as exc:
        assert "INGESTION_STAGE_CONCURRENCY_LIMITS" in str(exc)
    else:
        raise AssertionError("invalid stage concurrency limit should fail fast")


def _fake_result(
    *,
    stage: IngestionStage = IngestionStage.VERIFYING_UPLOAD,
    task_status: IngestionTaskStatus | str = IngestionTaskStatus.SUCCEEDED,
    run_status: IngestionRunStatus | str = IngestionRunStatus.RUNNING,
) -> FakeWorkerResult:
    return FakeWorkerResult(
        task_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        stage=stage,
        task_status=task_status,
        run_status=run_status,
    )
