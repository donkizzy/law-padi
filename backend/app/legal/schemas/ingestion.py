import uuid
from datetime import datetime
from typing import Any

from sqlmodel import SQLModel

from app.legal.enums import (
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
)
from app.legal.schemas.common import IdempotentMutation


class IngestionStepPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    dependency_step_id: uuid.UUID | None = None
    stage: IngestionStage
    status: IngestionStepStatus
    attempt_count: int
    lease_owner: str | None = None
    leased_until: datetime | None = None
    heartbeat_at: datetime | None = None
    total_units: int
    completed_units: int
    failed_units: int
    lock_version: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metrics: dict[str, Any] | None = None
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class IngestionEventPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None = None
    sequence: int
    event_type: str
    stage: IngestionStage | None = None
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class IngestionTaskPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None = None
    task_type: str
    status: IngestionTaskStatus
    priority: int
    attempt_count: int
    max_attempts: int
    lease_owner: str | None = None
    leased_until: datetime | None = None
    heartbeat_at: datetime | None = None
    lock_version: int
    payload: dict[str, Any]
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class IngestionRunPublic(SQLModel):
    id: uuid.UUID
    source_upload_id: uuid.UUID | None = None
    source_document_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    status: IngestionRunStatus
    current_stage: IngestionStage
    pipeline_version: str
    pipeline_config: dict[str, Any]
    expected_page_count: int | None = None
    total_units: int
    completed_units: int
    failed_units: int
    lock_version: int
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class IngestionRunDetail(IngestionRunPublic):
    steps: list[IngestionStepPublic]
    events: list[IngestionEventPublic]
    tasks: list[IngestionTaskPublic]


class IngestionRunsPublic(SQLModel):
    data: list[IngestionRunPublic]
    count: int


class IngestionRunControlRequest(IdempotentMutation):
    reason: str | None = None


class IngestionArtifactPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_page_id: uuid.UUID | None = None
    artifact_type: IngestionArtifactType
    storage_key: str
    sha256: str | None = None
    mime_type: str | None = None
    retention_policy: str
    artifact_metadata: dict[str, Any] | None = None
    created_at: datetime


class OcrBenchmarkSampleInput(SQLModel):
    item_key: str
    provider: str
    text: str | None = None
    confidence: float | None = None
    cost_usd: float | None = None
    timing_ms: float | None = None
    failure: str | None = None


class OcrBenchmarkEvaluateRequest(IdempotentMutation):
    dataset_version: str
    samples: list[OcrBenchmarkSampleInput]


class OcrBenchmarkProviderResult(SQLModel):
    provider: str
    page_count: int
    failure_count: int
    mean_character_accuracy: float
    mean_confidence: float | None = None
    total_cost_usd: float | None = None
    mean_timing_ms: float | None = None


class OcrBenchmarkPublic(SQLModel):
    dataset_version: str
    sample_count: int
    winner: str | None = None
    providers: list[OcrBenchmarkProviderResult]
    active_dataset_items: int
