import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    ExtractionMethod,
    InstrumentStatus,
    InstrumentType,
    PageInclusionStatus,
    PageRole,
    SourceTier,
    SourceUploadStatus,
    VerificationStatus,
)
from app.legal.models.common import get_datetime_utc


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
    instrument_type: InstrumentType = Field(
        default=InstrumentType.CONSTITUTION,
        sa_column=Column(
            String(length=32), nullable=False, server_default="constitution"
        ),
    )
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
