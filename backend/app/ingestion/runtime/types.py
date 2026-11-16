import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
)
from app.legal.models import (
    IngestionRun,
    IngestionTask,
)


@dataclass(frozen=True)
class StageOutcome:
    metrics: dict[str, Any]
    next_stage: IngestionStage | None = None
    next_status: IngestionRunStatus = IngestionRunStatus.RUNNING
    next_task_payload: dict[str, Any] | None = None
    block_next_stage: bool = False
    skipped_stages: tuple[IngestionStage, ...] = ()


@dataclass(frozen=True)
class WorkerResult:
    task_id: uuid.UUID
    run_id: uuid.UUID
    stage: IngestionStage
    task_status: IngestionTaskStatus
    run_status: IngestionRunStatus


StageHandler = Callable[[Session, IngestionRun, IngestionTask], StageOutcome]
