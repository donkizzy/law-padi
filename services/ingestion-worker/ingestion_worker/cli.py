import json
import logging
import os
import signal
import socket
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.core.db import engine
from app.ingestion.worker import run_once

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerSettings:
    worker_id: str
    poll_interval_seconds: float
    lease_seconds: int
    max_tasks_per_poll: int
    task_type: str | None = None
    stage_concurrency_limits: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> WorkerSettings:
        return cls(
            worker_id=os.getenv("INGESTION_WORKER_ID") or socket.gethostname(),
            poll_interval_seconds=_env_float(
                "INGESTION_WORKER_POLL_INTERVAL_SECONDS", default=5.0
            ),
            lease_seconds=_env_int("INGESTION_WORKER_LEASE_SECONDS", default=900),
            max_tasks_per_poll=_env_int(
                "INGESTION_WORKER_MAX_TASKS_PER_POLL", default=10
            ),
            task_type=os.getenv("INGESTION_WORKER_TASK_TYPE") or None,
            stage_concurrency_limits=_env_int_map(
                "INGESTION_STAGE_CONCURRENCY_LIMITS"
            ),
        )


@dataclass(frozen=True)
class WorkerLoopStats:
    iterations: int = 0
    tasks_processed: int = 0
    idle_polls: int = 0


SessionFactory = Callable[[], Iterator[Session]]
SleepFn = Callable[[float], None]
StopRequested = Callable[[], bool]
RunOnceFn = Callable[..., Any]


@contextmanager
def database_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def run_worker(
    *,
    settings: WorkerSettings | None = None,
    session_factory: SessionFactory = database_session,
    sleep: SleepFn = time.sleep,
    stop_requested: StopRequested | None = None,
    max_iterations: int | None = None,
    run_once_fn: RunOnceFn = run_once,
) -> WorkerLoopStats:
    worker_settings = settings or WorkerSettings.from_env()
    if worker_settings.max_tasks_per_poll < 1:
        raise ValueError("INGESTION_WORKER_MAX_TASKS_PER_POLL must be at least 1")
    if worker_settings.lease_seconds < 1:
        raise ValueError("INGESTION_WORKER_LEASE_SECONDS must be at least 1")
    if worker_settings.poll_interval_seconds < 0:
        raise ValueError("INGESTION_WORKER_POLL_INTERVAL_SECONDS cannot be negative")
    for stage, limit in worker_settings.stage_concurrency_limits.items():
        if limit < 1:
            raise ValueError(
                f"INGESTION_STAGE_CONCURRENCY_LIMITS for {stage} must be at least 1"
            )

    iterations = 0
    tasks_processed = 0
    idle_polls = 0

    while True:
        if stop_requested and stop_requested():
            break
        if max_iterations is not None and iterations >= max_iterations:
            break

        iterations += 1
        processed_this_poll = 0
        for _ in range(worker_settings.max_tasks_per_poll):
            if stop_requested and stop_requested():
                break
            with session_factory() as session:
                result = run_once_fn(
                    session,
                    worker_id=worker_settings.worker_id,
                    task_type=worker_settings.task_type,
                    lease_seconds=worker_settings.lease_seconds,
                    stage_concurrency_limits=(
                        worker_settings.stage_concurrency_limits
                    ),
                )
            if result is None:
                break
            processed_this_poll += 1
            tasks_processed += 1
            logger.info(
                "processed ingestion task",
                extra={
                    "task_id": str(result.task_id),
                    "run_id": str(result.run_id),
                    "stage": result.stage.value,
                    "task_status": result.task_status.value,
                    "run_status": result.run_status.value,
                },
            )

        if processed_this_poll == 0:
            idle_polls += 1
            if worker_settings.poll_interval_seconds:
                sleep(worker_settings.poll_interval_seconds)

    return WorkerLoopStats(
        iterations=iterations,
        tasks_processed=tasks_processed,
        idle_polls=idle_polls,
    )


def main() -> int:
    logging.basicConfig(
        level=os.getenv("INGESTION_WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop_requested = _signal_stop_flag()
    stats = run_worker(stop_requested=stop_requested)
    logger.info(
        "ingestion worker stopped",
        extra={
            "iterations": stats.iterations,
            "tasks_processed": stats.tasks_processed,
            "idle_polls": stats.idle_polls,
        },
    )
    return 0


def _signal_stop_flag() -> StopRequested:
    stopping = False

    def request_stop(signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        logger.info("received stop signal", extra={"signal": signum})

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    return lambda: stopping


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _env_float(name: str, *, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _env_int_map(name: str) -> dict[str, int]:
    value = os.getenv(name)
    if value is None or value == "":
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    limits: dict[str, int] = {}
    for key, raw_limit in payload.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{name} keys must be non-empty stage names")
        if not isinstance(raw_limit, int) or isinstance(raw_limit, bool):
            raise ValueError(f"{name} values must be integers")
        limits[key] = raw_limit
    return limits


if __name__ == "__main__":
    raise SystemExit(main())
