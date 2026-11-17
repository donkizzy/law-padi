import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
)
from app.legal.models.common import get_datetime_utc


class IngestionRun(SQLModel, table=True):
    __tablename__ = "ingestion_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_upload_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_upload.id",
        index=True,
        ondelete="SET NULL",
    )
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    status: IngestionRunStatus = Field(
        default=IngestionRunStatus.QUEUED,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    current_stage: IngestionStage = Field(
        default=IngestionStage.UPLOADING,
        sa_column=Column(String(length=64), nullable=False, index=True),
    )
    pipeline_version: str = Field(default="legal-ingestion-v1", max_length=128)
    pipeline_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    expected_page_count: int | None = None
    total_units: int = Field(default=0)
    completed_units: int = Field(default=0)
    failed_units: int = Field(default=0)
    lock_version: int = Field(default=1)
    error_details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class IngestionStep(SQLModel, table=True):
    __tablename__ = "ingestion_step"
    __table_args__ = (
        UniqueConstraint("run_id", "stage", name="uq_ingestion_step_run_stage"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="CASCADE",
    )
    dependency_step_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="ingestion_step.id",
        index=True,
        ondelete="SET NULL",
    )
    stage: IngestionStage = Field(
        sa_column=Column(String(length=64), nullable=False, index=True)
    )
    status: IngestionStepStatus = Field(
        default=IngestionStepStatus.PENDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    attempt_count: int = Field(default=0)
    lease_owner: str | None = Field(default=None, max_length=255, index=True)
    leased_until: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    heartbeat_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    total_units: int = Field(default=0)
    completed_units: int = Field(default=0)
    failed_units: int = Field(default=0)
    lock_version: int = Field(default=1)
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    metrics: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    error_details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    idempotency_key: str | None = Field(default=None, max_length=256, unique=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class IngestionEvent(SQLModel, table=True):
    __tablename__ = "ingestion_event"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_ingestion_event_sequence"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="CASCADE",
    )
    step_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="ingestion_step.id",
        index=True,
        ondelete="SET NULL",
    )
    sequence: int = Field(index=True)
    event_type: str = Field(max_length=64, index=True)
    stage: IngestionStage | None = Field(
        default=None,
        sa_column=Column(String(length=64), nullable=True, index=True),
    )
    message: str = Field(sa_column=Column(Text, nullable=False))
    payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class IngestionTask(SQLModel, table=True):
    __tablename__ = "ingestion_task"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="CASCADE",
    )
    step_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="ingestion_step.id",
        index=True,
        ondelete="CASCADE",
    )
    task_type: str = Field(max_length=128, index=True)
    status: IngestionTaskStatus = Field(
        default=IngestionTaskStatus.PENDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    lock_version: int = Field(default=1)
    priority: int = Field(default=100, index=True)
    attempt_count: int = Field(default=0)
    max_attempts: int = Field(default=3)
    lease_owner: str | None = Field(default=None, max_length=255, index=True)
    leased_until: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    heartbeat_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    available_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    idempotency_key: str = Field(max_length=256, unique=True, index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    error_details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TransactionalOutbox(SQLModel, table=True):
    __tablename__ = "transactional_outbox"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    aggregate_type: str = Field(max_length=128, index=True)
    aggregate_id: uuid.UUID = Field(index=True)
    event_type: str = Field(max_length=128, index=True)
    idempotency_key: str = Field(max_length=256, unique=True, index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    attempt_count: int = Field(default=0)
    published_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    error_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class IdempotencyRecord(SQLModel, table=True):
    __tablename__ = "idempotency_record"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "idempotency_key",
            name="uq_idempotency_record_scope_key",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    scope: str = Field(max_length=128, index=True)
    idempotency_key: str = Field(max_length=256, index=True)
    request_hash: str = Field(max_length=64, index=True)
    result_type: str = Field(max_length=128, index=True)
    result_id: uuid.UUID | None = Field(default=None, index=True)
    result_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class IngestionArtifact(SQLModel, table=True):
    __tablename__ = "ingestion_artifact"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="CASCADE",
    )
    source_page_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_page.id",
        index=True,
        ondelete="SET NULL",
    )
    artifact_type: IngestionArtifactType = Field(
        sa_column=Column(String(length=64), nullable=False, index=True)
    )
    storage_key: str = Field(max_length=1024, index=True)
    sha256: str | None = Field(default=None, max_length=64, index=True)
    mime_type: str | None = Field(default=None, max_length=255)
    retention_policy: str = Field(default="retain_indefinitely", max_length=128)
    artifact_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
