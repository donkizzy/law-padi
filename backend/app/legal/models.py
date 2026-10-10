import uuid
from datetime import UTC, date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    AdminRole,
    AmendmentOperationType,
    AmendmentStatus,
    AnswerStatus,
    AuditSeverity,
    BillStatus,
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
    EvidenceRole,
    ExtractionCandidateStatus,
    ExtractionMethod,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    LegislativeChamber,
    LegislativeEventType,
    MessageRole,
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    ReleasePromotionStatus,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    ReviewStatus,
    SourceTier,
    SourceUploadStatus,
    VectorIndexStatus,
    VerificationStatus,
)


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class LegalInstrument(SQLModel, table=True):
    __tablename__ = "legal_instrument"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str = Field(unique=True, index=True, max_length=255)
    title: str = Field(max_length=512)
    short_title: str | None = Field(default=None, max_length=255)
    instrument_type: InstrumentType = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    jurisdiction: str = Field(default="NG", max_length=255, index=True)
    year: int | None = Field(default=None, index=True)
    status: InstrumentStatus = Field(
        default=InstrumentStatus.DRAFT,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    enacted_at: date | None = None
    effective_at: date | None = None
    ceased_at: date | None = None
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SourceDocument(SQLModel, table=True):
    __tablename__ = "source_document"
    __table_args__ = (
        CheckConstraint(
            "(is_legal_revision = false) OR (legal_revision_effective_at IS NOT NULL)",
            name="ck_source_document_legal_revision_effective_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    legal_instrument_id: uuid.UUID = Field(
        foreign_key="legal_instrument.id",
        index=True,
        ondelete="CASCADE",
    )
    authority: str = Field(max_length=255, index=True)
    title: str = Field(max_length=512)
    source_url: str = Field(max_length=2048)
    mime_type: str = Field(max_length=255)
    sha256: str = Field(unique=True, index=True, max_length=64)
    storage_backend: str = Field(max_length=64, index=True)
    storage_bucket: str | None = Field(default=None, max_length=255)
    storage_key: str = Field(max_length=1024)
    original_filename: str = Field(max_length=512)
    file_size: int
    page_count: int | None = None
    published_at: date
    retrieved_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    is_legal_revision: bool = Field(default=False, index=True)
    legal_revision_effective_at: date | None = None
    source_tier: SourceTier = Field(
        default=SourceTier.UNKNOWN,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    parser_version: str | None = Field(default=None, max_length=64)
    extraction_method: ExtractionMethod | None = Field(
        default=None,
        sa_column=Column(String(length=32), nullable=True),
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    verified_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    lock_version: int = Field(default=1)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SourceUpload(SQLModel, table=True):
    __tablename__ = "source_upload"
    __table_args__ = (
        CheckConstraint("expected_size > 0", name="ck_source_upload_expected_size"),
        CheckConstraint(
            "(is_legal_revision = false) OR (legal_revision_effective_at IS NOT NULL)",
            name="ck_source_upload_legal_revision_effective_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    idempotency_key: str = Field(unique=True, index=True, max_length=128)
    created_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    legal_instrument_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="legal_instrument.id",
        index=True,
        ondelete="SET NULL",
    )
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    instrument_slug: str = Field(max_length=255, index=True)
    instrument_title: str = Field(max_length=512)
    instrument_short_title: str | None = Field(default=None, max_length=255)
    instrument_year: int = Field(index=True)
    instrument_status: InstrumentStatus = Field(
        default=InstrumentStatus.DRAFT,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    enacted_at: date | None = None
    effective_at: date | None = None
    ceased_at: date | None = None
    is_legal_revision: bool = Field(default=False, index=True)
    legal_revision_effective_at: date | None = None
    source_title: str = Field(max_length=512)
    authority: str = Field(max_length=255, index=True)
    source_url: str = Field(max_length=2048)
    source_tier: SourceTier = Field(
        default=SourceTier.UNKNOWN,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    published_at: date
    retrieved_at: date
    original_filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=255)
    expected_size: int
    expected_sha256: str | None = Field(default=None, max_length=64, index=True)
    actual_sha256: str | None = Field(default=None, max_length=64, index=True)
    upload_backend: str = Field(default="local", max_length=64, index=True)
    quarantine_key: str = Field(max_length=1024, unique=True)
    canonical_key: str | None = Field(default=None, max_length=1024, index=True)
    multipart_upload_id: str | None = Field(default=None, max_length=512)
    status: SourceUploadStatus = Field(
        default=SourceUploadStatus.CREATED,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    lock_version: int = Field(default=1)
    error_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


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


class SourcePage(SQLModel, table=True):
    __tablename__ = "source_page"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="ck_source_page_number_positive"),
        UniqueConstraint("run_id", "page_number", name="uq_source_page_run_number"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="CASCADE",
    )
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    page_number: int = Field(index=True)
    role: PageRole = Field(
        default=PageRole.LEGAL_BODY,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    inclusion_status: PageInclusionStatus = Field(
        default=PageInclusionStatus.SUGGESTED_INCLUDE,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    inclusion_reason: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    thumbnail_key: str | None = Field(default=None, max_length=1024)
    text_density: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    orientation: str | None = Field(default=None, max_length=32)
    column_count: int | None = None
    image_coverage: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    width: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    height: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    quality_signals: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    lock_version: int = Field(default=1)
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


class Provision(SQLModel, table=True):
    __tablename__ = "provision"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    instrument_id: uuid.UUID = Field(
        foreign_key="legal_instrument.id",
        index=True,
        ondelete="CASCADE",
    )
    parent_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="provision.id",
        index=True,
        ondelete="CASCADE",
    )
    kind: ProvisionKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    number: str | None = Field(default=None, max_length=64, index=True)
    heading: str | None = Field(default=None, max_length=512)
    canonical_path: str = Field(unique=True, index=True, max_length=512)
    sort_key: str = Field(index=True, max_length=255)


class Amendment(SQLModel, table=True):
    __tablename__ = "amendment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    instrument_id: uuid.UUID = Field(
        foreign_key="legal_instrument.id",
        index=True,
        ondelete="CASCADE",
    )
    title: str = Field(max_length=512)
    act_number: str | None = Field(default=None, max_length=128, index=True)
    year: int | None = Field(default=None, index=True)
    status: AmendmentStatus = Field(
        default=AmendmentStatus.DRAFT,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    passed_at: date | None = None
    effective_at: date | None = None
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ProvisionVersion(SQLModel, table=True):
    __tablename__ = "provision_version"
    __table_args__ = (
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_provision_version_valid_period",
        ),
        UniqueConstraint(
            "provision_id",
            "revision_number",
            name="uq_provision_version_revision",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provision_id: uuid.UUID = Field(
        foreign_key="provision.id",
        index=True,
        ondelete="CASCADE",
    )
    text: str = Field(sa_column=Column(Text, nullable=False))
    normalized_text: str = Field(sa_column=Column(Text, nullable=False))
    valid_from: date = Field(index=True)
    valid_until: date | None = Field(default=None, index=True)
    legal_status: LegalStatus = Field(
        default=LegalStatus.CURRENT,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    revision_number: int = Field(default=1)
    source_document_id: uuid.UUID = Field(
        foreign_key="source_document.id",
        index=True,
    )
    source_page_start: int | None = None
    source_page_end: int | None = None
    text_sha256: str = Field(index=True, max_length=64)
    created_by_amendment_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="amendment.id",
        index=True,
        ondelete="SET NULL",
    )
    supersedes_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="provision_version.id",
        index=True,
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ExtractionCandidate(SQLModel, table=True):
    __tablename__ = "extraction_candidate"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "canonical_path",
            "revision_number",
            name="uq_extraction_candidate_revision_path",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="CASCADE",
    )
    source_document_id: uuid.UUID = Field(
        foreign_key="source_document.id",
        index=True,
        ondelete="CASCADE",
    )
    parent_candidate_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="extraction_candidate.id",
        index=True,
        ondelete="SET NULL",
    )
    materialized_provision_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="provision.id",
        index=True,
        ondelete="SET NULL",
    )
    materialized_version_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="provision_version.id",
        index=True,
        ondelete="SET NULL",
    )
    kind: ProvisionKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    number: str | None = Field(default=None, max_length=64, index=True)
    heading: str | None = Field(default=None, max_length=512)
    canonical_path: str = Field(max_length=512, index=True)
    sort_key: str = Field(max_length=255, index=True)
    raw_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    normalized_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    text_sha256: str | None = Field(default=None, max_length=64, index=True)
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_spans: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    ancestor_headings: list[str] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    parser_version: str | None = Field(default=None, max_length=128)
    extractor_version: str | None = Field(default=None, max_length=128)
    parser_confidence: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    extractor_confidence: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    status: ExtractionCandidateStatus = Field(
        default=ExtractionCandidateStatus.NEEDS_REVIEW,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    blocking_issue_count: int = Field(default=0)
    revision_number: int = Field(default=1)
    lock_version: int = Field(default=1)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class CandidateRevision(SQLModel, table=True):
    __tablename__ = "candidate_revision"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "revision_number",
            name="uq_candidate_revision_number",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    candidate_id: uuid.UUID = Field(
        foreign_key="extraction_candidate.id",
        index=True,
        ondelete="CASCADE",
    )
    revision_number: int = Field(index=True)
    previous_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    revised_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    diff: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    before_snapshot: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    after_snapshot: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    changed_fields: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    reason: str = Field(sa_column=Column(Text, nullable=False))
    revised_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ReviewIssue(SQLModel, table=True):
    __tablename__ = "review_issue"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    candidate_id: uuid.UUID = Field(
        foreign_key="extraction_candidate.id",
        index=True,
        ondelete="CASCADE",
    )
    issue_type: str = Field(max_length=128, index=True)
    severity: ReviewIssueSeverity = Field(
        default=ReviewIssueSeverity.MEDIUM,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    status: ReviewIssueStatus = Field(
        default=ReviewIssueStatus.OPEN,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    blocking: bool = Field(default=False, index=True)
    message: str = Field(sa_column=Column(Text, nullable=False))
    evidence: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    resolved_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    resolved_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    resolution_reason: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    resolution_evidence: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ReviewDecisionRecord(SQLModel, table=True):
    __tablename__ = "review_decision"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    candidate_id: uuid.UUID = Field(
        foreign_key="extraction_candidate.id",
        index=True,
        ondelete="CASCADE",
    )
    decision: ReviewDecisionType = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    decided_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    reason: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AmendmentOperation(SQLModel, table=True):
    __tablename__ = "amendment_operation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    amendment_id: uuid.UUID = Field(
        foreign_key="amendment.id",
        index=True,
        ondelete="CASCADE",
    )
    target_provision_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="provision.id",
        index=True,
        ondelete="SET NULL",
    )
    target_version_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="provision_version.id",
        index=True,
        ondelete="SET NULL",
    )
    operation_type: AmendmentOperationType = Field(
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    selector: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    old_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    new_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    old_text_hash: str | None = Field(default=None, max_length=64, index=True)
    sort_order: int = Field(default=0, index=True)
    review_status: ReviewStatus = Field(
        default=ReviewStatus.UNREVIEWED,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    reviewed_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    reviewed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ConstitutionalBill(SQLModel, table=True):
    __tablename__ = "constitutional_bill"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    instrument_id: uuid.UUID = Field(
        foreign_key="legal_instrument.id",
        index=True,
        ondelete="CASCADE",
    )
    bill_number: str | None = Field(default=None, max_length=128, index=True)
    title: str = Field(max_length=512)
    introduced_at: date | None = None
    originating_chamber: LegislativeChamber | None = Field(
        default=None,
        sa_column=Column(String(length=32), nullable=True, index=True),
    )
    status: BillStatus = Field(
        default=BillStatus.DRAFT,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    current_stage: str | None = Field(default=None, max_length=128, index=True)
    last_verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class LegislativeEvent(SQLModel, table=True):
    __tablename__ = "legislative_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bill_id: uuid.UUID = Field(
        foreign_key="constitutional_bill.id",
        index=True,
        ondelete="CASCADE",
    )
    event_type: LegislativeEventType = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    event_date: date = Field(index=True)
    chamber: LegislativeChamber | None = Field(
        default=None,
        sa_column=Column(String(length=32), nullable=True, index=True),
    )
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    source_url: str | None = Field(default=None, max_length=2048)
    verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class Conversation(SQLModel, table=True):
    __tablename__ = "conversation"
    __table_args__ = (
        CheckConstraint(
            "user_id IS NOT NULL OR anonymous_session_id IS NOT NULL",
            name="ck_conversation_has_owner_or_anonymous_session",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="CASCADE",
    )
    anonymous_session_id: str | None = Field(default=None, max_length=255, index=True)
    title: str | None = Field(default=None, max_length=255)
    preferred_language: str | None = Field(default=None, max_length=16, index=True)
    pinned_release_id: uuid.UUID | None = Field(
        default=None, foreign_key="corpus_release.id", index=True
    )
    pinned_index_build_id: uuid.UUID | None = Field(
        default=None, foreign_key="retrieval_index_build.id", index=True
    )
    index_kind: str = Field(default="enacted", max_length=32)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_message"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="conversation.id",
        index=True,
        ondelete="CASCADE",
    )
    role: MessageRole = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    detected_language: str | None = Field(default=None, max_length=16, index=True)
    answer_status: AnswerStatus | None = Field(
        default=None,
        sa_column=Column(String(length=32), nullable=True, index=True),
    )
    model_provider: str | None = Field(default=None, max_length=64)
    model_name: str | None = Field(default=None, max_length=128)
    retrieval_trace_id: uuid.UUID | None = Field(default=None, index=True)
    answer_content: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    evidence_snapshot: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    prompt_version: str | None = Field(default=None, max_length=64)
    usage: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    validation_result: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class MessageEvidence(SQLModel, table=True):
    __tablename__ = "message_evidence"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    message_id: uuid.UUID = Field(
        foreign_key="conversation_message.id",
        index=True,
        ondelete="CASCADE",
    )
    provision_version_id: uuid.UUID = Field(
        foreign_key="provision_version.id",
        index=True,
        ondelete="CASCADE",
    )
    evidence_role: EvidenceRole = Field(
        default=EvidenceRole.SUPPORTING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    retrieval_rank: int | None = Field(default=None, index=True)
    retrieval_score: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    citation_label: str | None = Field(default=None, max_length=255)
    release_id: uuid.UUID | None = Field(
        default=None, foreign_key="corpus_release.id", index=True
    )
    evidence_snapshot: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class GenerationRun(SQLModel, table=True):
    __tablename__ = "generation_run"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "idempotency_key", name="uq_generation_run_submission"
        ),
        Index(
            "ix_generation_run_one_active",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="conversation.id", index=True, ondelete="CASCADE"
    )
    user_message_id: uuid.UUID = Field(
        foreign_key="conversation_message.id", ondelete="CASCADE"
    )
    selected_provision_version_id: uuid.UUID | None = Field(
        default=None, foreign_key="provision_version.id", index=True
    )
    assistant_message_id: uuid.UUID | None = Field(
        default=None, foreign_key="conversation_message.id", ondelete="SET NULL"
    )
    idempotency_key: str = Field(max_length=128)
    status: str = Field(default="pending", max_length=32, index=True)
    outcome: str | None = Field(default=None, max_length=64)
    lease_owner: str | None = Field(default=None, max_length=128)
    lease_until: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    provider_started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    attempt_count: int = Field(default=0)
    cancellation_requested: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class GenerationEvent(SQLModel, table=True):
    __tablename__ = "generation_event"

    id: int | None = Field(default=None, sa_type=BigInteger, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="conversation.id", index=True, ondelete="CASCADE"
    )
    run_id: uuid.UUID = Field(
        foreign_key="generation_run.id", index=True, ondelete="CASCADE"
    )
    event_type: str = Field(max_length=64)
    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class GenerationBudgetDay(SQLModel, table=True):
    __tablename__ = "generation_budget_day"

    day: date = Field(primary_key=True)
    reserved_micro_usd: int = Field(default=0, sa_type=BigInteger)
    spent_micro_usd: int = Field(default=0, sa_type=BigInteger)


class GenerationReservation(SQLModel, table=True):
    __tablename__ = "generation_reservation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID | None = Field(
        default=None, foreign_key="generation_run.id", index=True, ondelete="SET NULL"
    )
    day: date = Field(foreign_key="generation_budget_day.day", index=True)
    purpose: str = Field(max_length=32)
    reserved_micro_usd: int = Field(sa_type=BigInteger)
    actual_micro_usd: int | None = Field(default=None, sa_type=BigInteger)
    status: str = Field(default="reserved", max_length=32)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class GenerationCapacity(SQLModel, table=True):
    __tablename__ = "generation_capacity"

    id: int = Field(default=1, primary_key=True)
    active_count: int = Field(default=0)


class LegalConcept(SQLModel, table=True):
    __tablename__ = "legal_concept"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str = Field(unique=True, index=True, max_length=255)
    canonical_name: str = Field(max_length=255)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class LegalConceptAlias(SQLModel, table=True):
    __tablename__ = "legal_concept_alias"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    concept_id: uuid.UUID = Field(
        foreign_key="legal_concept.id",
        index=True,
        ondelete="CASCADE",
    )
    language: str = Field(max_length=16, index=True)
    phrase: str = Field(max_length=512)
    normalized_phrase: str = Field(max_length=512, index=True)
    weight: float = Field(default=1.0)
    reviewed: bool = Field(default=False, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EvaluationDataset(SQLModel, table=True):
    __tablename__ = "evaluation_dataset"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: str = Field(unique=True, index=True, max_length=128)
    name: str = Field(max_length=255)
    dataset_kind: EvaluationDatasetKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    language: str = Field(default="en", max_length=16, index=True)
    jurisdiction: str = Field(default="NG", max_length=255, index=True)
    instrument_slug: str | None = Field(default=None, max_length=255, index=True)
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    content_sha256: str | None = Field(default=None, max_length=64, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EvaluationItem(SQLModel, table=True):
    __tablename__ = "evaluation_item"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "item_key",
            name="uq_evaluation_item_dataset_key",
        ),
        CheckConstraint(
            "(item_kind <> 'gold_provision') OR "
            "(canonical_path IS NOT NULL AND expected_text IS NOT NULL)",
            name="ck_evaluation_item_gold_provision_fields",
        ),
        CheckConstraint(
            "(item_kind <> 'retrieval_query') OR "
            "(query_text IS NOT NULL AND expected_canonical_paths IS NOT NULL)",
            name="ck_evaluation_item_retrieval_query_fields",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dataset_id: uuid.UUID = Field(
        foreign_key="evaluation_dataset.id",
        index=True,
        ondelete="CASCADE",
    )
    item_key: str = Field(max_length=255, index=True)
    item_kind: EvaluationItemKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    canonical_path: str | None = Field(default=None, max_length=512, index=True)
    provision_kind: ProvisionKind | None = Field(
        default=None,
        sa_column=Column(String(length=32), nullable=True, index=True),
    )
    section_number: str | None = Field(default=None, max_length=64, index=True)
    citation: str | None = Field(default=None, max_length=255)
    expected_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    query_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    expected_canonical_paths: list[str] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_spans: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    item_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("metadata", JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class CorpusRelease(SQLModel, table=True):
    __tablename__ = "corpus_release"
    __table_args__ = (
        Index(
            "ix_corpus_release_single_production",
            "status",
            unique=True,
            postgresql_where=text("status = 'production'"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: str = Field(unique=True, index=True, max_length=128)
    status: CorpusReleaseStatus = Field(
        default=CorpusReleaseStatus.BUILDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    source_manifest_hash: str | None = Field(default=None, max_length=64, index=True)
    embedding_model: str | None = Field(default=None, max_length=255)
    embedding_model_version: str | None = Field(default=None, max_length=128)
    parser_version: str | None = Field(default=None, max_length=64)
    validation_report: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    lock_version: int = Field(default=1)
    approved_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    approved_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class CorpusReleaseEntry(SQLModel, table=True):
    __tablename__ = "corpus_release_entry"
    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "provision_version_id",
            name="uq_corpus_release_entry_version",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id",
        index=True,
        ondelete="CASCADE",
    )
    provision_version_id: uuid.UUID = Field(
        foreign_key="provision_version.id",
        index=True,
        ondelete="CASCADE",
    )
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    ingestion_run_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="ingestion_run.id",
        index=True,
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EmbeddingProfile(SQLModel, table=True):
    __tablename__ = "embedding_profile"
    __table_args__ = (
        CheckConstraint(
            "vector_dimensions = 1024",
            name="ck_embedding_profile_vector_dimensions",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=128)
    provider: EmbeddingProviderKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    model_name: str = Field(max_length=255, index=True)
    model_revision: str | None = Field(default=None, max_length=128)
    vector_dimensions: int = Field(index=True)
    supports_sparse: bool = Field(default=False, index=True)
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EmbeddingRun(SQLModel, table=True):
    __tablename__ = "embedding_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id",
        index=True,
        ondelete="CASCADE",
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id",
        index=True,
        ondelete="CASCADE",
    )
    status: EmbeddingRunStatus = Field(
        default=EmbeddingRunStatus.PENDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    benchmark_dataset_version: str | None = Field(default=None, max_length=128)
    recall_at_10: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    ndcg_at_10: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    cost_usd: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    p95_latency_ms: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    selected_for_release: bool = Field(default=False, index=True)
    metrics: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    error_details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class VectorIndex(SQLModel, table=True):
    __tablename__ = "vector_index"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id",
        index=True,
        ondelete="CASCADE",
    )
    embedding_run_id: uuid.UUID = Field(
        foreign_key="embedding_run.id",
        index=True,
        ondelete="CASCADE",
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id",
        index=True,
        ondelete="CASCADE",
    )
    collection_name: str = Field(unique=True, index=True, max_length=255)
    alias_name: str = Field(default="constitution_enacted", max_length=255, index=True)
    index_kind: str = Field(default="enacted", max_length=32, index=True)
    profile_hash: str | None = Field(default=None, max_length=64, index=True)
    status: VectorIndexStatus = Field(
        default=VectorIndexStatus.BUILDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    point_count: int = Field(default=0)
    vector_dimensions: int
    payload_schema_hash: str | None = Field(default=None, max_length=64, index=True)
    checksum: str | None = Field(default=None, max_length=64, index=True)
    validation_report: dict[str, Any] | None = Field(
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


class RetrievalSegment(SQLModel, table=True):
    """Immutable, release-scoped retrieval text derived from canonical law."""

    __tablename__ = "retrieval_segment"
    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "provision_version_id",
            "segment_index",
            name="uq_retrieval_segment_release_version_index",
        ),
        CheckConstraint(
            "segment_index >= 1", name="ck_retrieval_segment_index_positive"
        ),
        CheckConstraint(
            "segment_count >= segment_index",
            name="ck_retrieval_segment_count_covers_index",
        ),
        CheckConstraint("language = 'en'", name="ck_retrieval_segment_language_en"),
        CheckConstraint(
            "retrieval_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_segment_text_hash",
        ),
        CheckConstraint(
            "authoritative_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_segment_authoritative_hash",
        ),
        Index("ix_retrieval_segment_release_kind", "release_id", "index_kind"),
        Index("ix_retrieval_segment_provision_version", "provision_version_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id", index=True, ondelete="CASCADE"
    )
    release_entry_id: uuid.UUID = Field(
        foreign_key="corpus_release_entry.id", index=True, ondelete="CASCADE"
    )
    provision_id: uuid.UUID = Field(
        foreign_key="provision.id", index=True, ondelete="CASCADE"
    )
    provision_version_id: uuid.UUID = Field(
        foreign_key="provision_version.id", index=True, ondelete="CASCADE"
    )
    source_document_id: uuid.UUID = Field(
        foreign_key="source_document.id", index=True, ondelete="CASCADE"
    )
    index_kind: str = Field(default="enacted", max_length=32, index=True)
    segment_index: int
    segment_count: int
    language: str = Field(default="en", max_length=16)
    citation: str = Field(max_length=255)
    canonical_path: str = Field(max_length=512, index=True)
    ancestor_headings: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    ancestor_text: str = Field(sa_column=Column(Text, nullable=False))
    heading: str | None = Field(default=None, max_length=512)
    retrieval_text: str = Field(sa_column=Column(Text, nullable=False))
    retrieval_text_sha256: str = Field(max_length=64)
    authoritative_text_sha256: str = Field(max_length=64)
    lexical_profile_version: str = Field(default="postgres-simple-v1", max_length=128)
    search_vector: Any = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed(
                "setweight(to_tsvector('simple', coalesce(citation, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(heading, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(ancestor_text, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(retrieval_text, '')), 'D')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RetrievalEmbedding(SQLModel, table=True):
    """A model-specific vector; never overwrite vectors from another run."""

    __tablename__ = "retrieval_embedding"
    __table_args__ = (
        UniqueConstraint(
            "embedding_run_id",
            "segment_id",
            name="uq_retrieval_embedding_run_segment",
        ),
        CheckConstraint(
            "vector_dimensions = 1024",
            name="ck_retrieval_embedding_dimensions",
        ),
        CheckConstraint(
            "vector_dims(embedding) = vector_dimensions",
            name="ck_retrieval_embedding_vector_dims",
        ),
        CheckConstraint(
            "embedding_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_embedding_hash",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    segment_id: uuid.UUID = Field(
        foreign_key="retrieval_segment.id", index=True, ondelete="CASCADE"
    )
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id", index=True, ondelete="CASCADE"
    )
    embedding_run_id: uuid.UUID = Field(
        foreign_key="embedding_run.id", index=True, ondelete="CASCADE"
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id", index=True, ondelete="CASCADE"
    )
    vector_dimensions: int = Field(default=1024)
    embedding: list[float] = Field(sa_column=Column(Vector(1024), nullable=False))
    embedding_sha256: str = Field(max_length=64)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RetrievalIndexBuild(SQLModel, table=True):
    """Validation evidence for a release-scoped retrieval dataset."""

    __tablename__ = "retrieval_index_build"
    __table_args__ = (
        CheckConstraint("backend = 'pgvector'", name="ck_retrieval_index_backend"),
        CheckConstraint(
            "vector_dimensions = 1024",
            name="ck_retrieval_index_dimensions",
        ),
        UniqueConstraint(
            "release_id",
            "embedding_run_id",
            "index_kind",
            name="uq_retrieval_index_build_release_run_kind",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id", index=True, ondelete="CASCADE"
    )
    embedding_run_id: uuid.UUID = Field(
        foreign_key="embedding_run.id", index=True, ondelete="CASCADE"
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id", index=True, ondelete="CASCADE"
    )
    backend: str = Field(default="pgvector", max_length=32)
    index_kind: str = Field(default="enacted", max_length=32, index=True)
    relation_name: str = Field(default="retrieval_embedding", max_length=128)
    physical_index_name: str | None = Field(default=None, max_length=255)
    status: VectorIndexStatus = Field(
        default=VectorIndexStatus.BUILDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    expected_segment_count: int = Field(default=0)
    stored_segment_count: int = Field(default=0)
    stored_embedding_count: int = Field(default=0)
    vector_dimensions: int = Field(default=1024)
    profile_hash: str | None = Field(default=None, max_length=64)
    payload_schema_hash: str | None = Field(default=None, max_length=64)
    checksum: str | None = Field(default=None, max_length=64)
    validation_report: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ActiveRetrievalTarget(SQLModel, table=True):
    """The transactional production pointer for one retrieval index kind."""

    __tablename__ = "active_retrieval_target"

    index_kind: str = Field(primary_key=True, max_length=32)
    release_id: uuid.UUID = Field(foreign_key="corpus_release.id", index=True)
    embedding_run_id: uuid.UUID = Field(foreign_key="embedding_run.id", index=True)
    retrieval_index_build_id: uuid.UUID = Field(
        foreign_key="retrieval_index_build.id", index=True
    )
    profile_id: uuid.UUID = Field(foreign_key="embedding_profile.id", index=True)
    lock_version: int = Field(default=1)
    activated_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    activated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ReleasePromotionAttempt(SQLModel, table=True):
    __tablename__ = "release_promotion_attempt"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id",
        index=True,
        ondelete="CASCADE",
    )
    vector_index_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="vector_index.id",
        index=True,
        ondelete="SET NULL",
    )
    retrieval_index_build_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="retrieval_index_build.id",
        index=True,
        ondelete="SET NULL",
    )
    index_kind: str | None = Field(default=None, max_length=32, index=True)
    requested_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    status: ReleasePromotionStatus = Field(
        default=ReleasePromotionStatus.PENDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    previous_release_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="corpus_release.id",
        index=True,
        ondelete="SET NULL",
    )
    previous_collection_name: str | None = Field(default=None, max_length=255)
    target_collection_name: str | None = Field(default=None, max_length=255)
    rollback_completed: bool = Field(default=False, index=True)
    error_details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AdminRoleAssignment(SQLModel, table=True):
    __tablename__ = "admin_role_assignment"
    __table_args__ = (
        Index(
            "ix_admin_role_assignment_active_unique",
            "user_id",
            "role",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        index=True,
        ondelete="CASCADE",
    )
    role: AdminRole = Field(
        sa_column=Column(String(length=64), nullable=False, index=True)
    )
    assigned_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    action: str = Field(max_length=128, index=True)
    entity_type: str = Field(max_length=128, index=True)
    entity_id: uuid.UUID | None = Field(default=None, index=True)
    severity: AuditSeverity = Field(
        default=AuditSeverity.INFO,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
