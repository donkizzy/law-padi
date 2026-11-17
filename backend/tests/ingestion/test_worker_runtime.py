import os
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

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


def test_worker_passes_shutdown_signal_into_running_session(
    db: Any, tmp_path: Path
) -> None:
    @contextmanager
    def session_factory() -> Iterator[Any]:
        yield db

    def stop_requested() -> bool:
        return False

    def fake_run_once(session: Any, **_kwargs: Any) -> None:
        assert session.info["ingestion_stop_requested"] is stop_requested

    run_worker(
        settings=WorkerSettings(
            worker_id="test",
            poll_interval_seconds=0,
            lease_seconds=60,
            max_tasks_per_poll=1,
            outbox_sink_path=str(tmp_path / "outbox.jsonl"),
        ),
        session_factory=session_factory,
        stop_requested=stop_requested,
        run_once_fn=fake_run_once,
        max_iterations=1,
    )
    db.info.pop("ingestion_stop_requested", None)


def test_worker_loop_beats_on_idle_and_busy_polls(tmp_path: Path) -> None:
    heartbeat = tmp_path / "ingestion-worker.heartbeat"
    fresh_at_poll: list[bool] = []
    task_results: list[FakeWorkerResult | None] = [_fake_result(), None, None]

    @contextmanager
    def session_factory() -> Iterator[object]:
        yield object()

    def fake_run_once(_session: object, **_kwargs: Any) -> FakeWorkerResult | None:
        # Record whether a beat happened since the last poll, then age the file.
        fresh_at_poll.append(heartbeat.stat().st_mtime > 0)
        os.utime(heartbeat, (0, 0))
        return task_results.pop(0)

    stats = run_worker(
        settings=WorkerSettings(
            worker_id="worker-a",
            poll_interval_seconds=5,
            lease_seconds=60,
            max_tasks_per_poll=2,
            heartbeat_file=str(heartbeat),
        ),
        session_factory=session_factory,
        sleep=lambda _seconds: None,
        max_iterations=2,
        run_once_fn=fake_run_once,
    )

    # Busy poll: a beat at the start and after the task; idle poll: at the start.
    assert (stats.iterations, stats.idle_polls) == (2, 1)
    assert fresh_at_poll == [True, True, True]


def test_worker_settings_read_the_heartbeat_file(monkeypatch: Any) -> None:
    monkeypatch.setenv("INGESTION_WORKER_HEARTBEAT_FILE", "/tmp/worker.heartbeat")
    assert WorkerSettings.from_env().heartbeat_file == "/tmp/worker.heartbeat"
    monkeypatch.setenv("INGESTION_WORKER_HEARTBEAT_FILE", "")
    assert WorkerSettings.from_env().heartbeat_file is None


def test_stage_checkpoints_beat_before_checking_for_shutdown() -> None:
    from sqlmodel import Session

    from app.ingestion.runtime.control import check_stage_continue

    calls: list[str] = []
    session = Session()
    session.info["ingestion_heartbeat"] = lambda: calls.append("beat")
    session.info["ingestion_continue"] = lambda: calls.append("continue")
    check_stage_continue(session)
    assert calls == ["beat", "continue"]


def test_worker_shutdown_closes_embedding_clients() -> None:
    from app.ingestion.stages.embedding_profiles import embedding_provider_for_profile
    from app.legal.enums import EmbeddingProviderKind
    from app.legal.models import EmbeddingProfile

    profile = EmbeddingProfile(
        name="worker-shutdown",
        provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
        model_name="test",
        vector_dimensions=1024,
    )
    provider = embedding_provider_for_profile(profile)
    run_worker(max_iterations=0)
    assert provider.client.is_closed


def test_worker_sentry_initialisation_is_a_noop_without_a_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ingestion_worker import cli

    from app.core import sentry
    from app.core.config import settings

    monkeypatch.setattr(settings, "FASTAPI_ENV", "production")
    monkeypatch.setattr(settings, "SENTRY_DSN", None)
    calls: list[tuple[str, bool]] = []

    def init(component: str) -> bool:
        enabled = sentry.init_sentry(component)
        calls.append((component, enabled))
        return enabled

    def unexpected_init(**_kwargs: Any) -> None:
        raise AssertionError("The Sentry SDK must stay off without SENTRY_DSN")

    monkeypatch.setattr(sentry.sentry_sdk, "init", unexpected_init)
    monkeypatch.setattr(cli, "init_sentry", init)
    monkeypatch.setattr(cli, "configure_logging", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "_signal_stop_flag", lambda: lambda: True)
    assert cli.main() == 0
    assert calls == [("ingestion-worker", False)]
