import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    InstrumentStatus,
    InstrumentType,
    PageInclusionStatus,
    PageRole,
    SourceTier,
    SourceUploadStatus,
    VerificationStatus,
)
from app.legal.schemas.common import IdempotentMutation
from app.legal.schemas.ingestion import IngestionRunPublic


class SourceUploadCreate(SQLModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    expected_size: int = Field(gt=0, le=500 * 1024 * 1024)
    expected_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    original_filename: str = Field(min_length=1, max_length=512)
    mime_type: str
    instrument_slug: str = Field(min_length=1, max_length=255)
    instrument_title: str = Field(min_length=1, max_length=512)
    instrument_type: Literal[InstrumentType.CONSTITUTION, InstrumentType.ACT] = (
        InstrumentType.CONSTITUTION
    )
    instrument_short_title: str | None = Field(default=None, max_length=255)
    instrument_year: int = Field(ge=1)
    instrument_status: InstrumentStatus
    enacted_at: date | None = None
    effective_at: date | None = None
    ceased_at: date | None = None
    is_legal_revision: bool = False
    legal_revision_effective_at: date | None = None
    source_title: str = Field(min_length=1, max_length=512)
    authority: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1, max_length=2048)
    source_tier: SourceTier
    published_at: date
    retrieved_at: date

    @field_validator("mime_type")
    @classmethod
    def validate_pdf_mime_type(cls, value: str) -> str:
        if value != "application/pdf":
            raise ValueError("Ingestion accepts PDF sources only")
        return value

    @model_validator(mode="after")
    def validate_legal_revision_metadata(self) -> SourceUploadCreate:
        if self.is_legal_revision and self.legal_revision_effective_at is None:
            raise ValueError("Legal revisions require an effective date")
        return self


class SourceUploadPublic(SQLModel):
    id: uuid.UUID
    idempotency_key: str
    source_document_id: uuid.UUID | None = None
    instrument_slug: str
    instrument_title: str
    instrument_type: InstrumentType = InstrumentType.CONSTITUTION
    source_title: str
    authority: str
    source_url: str
    source_tier: SourceTier
    is_legal_revision: bool
    legal_revision_effective_at: date | None = None
    original_filename: str
    mime_type: str
    expected_size: int
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    upload_backend: str
    quarantine_key: str
    canonical_key: str | None = None
    upload_url: str
    upload_headers: dict[str, str]
    multipart_required: bool
    status: SourceUploadStatus
    error_message: str | None = None
    lock_version: int
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CompletedMultipartPart(SQLModel):
    part_number: int = Field(ge=1)
    etag: str = Field(min_length=1, max_length=512)


class SourceUploadComplete(IdempotentMutation):
    actual_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    completed_parts: list[CompletedMultipartPart] | None = None


class MultipartPartsRequest(IdempotentMutation):
    part_count: int = Field(ge=1, le=10000)


class MultipartPartPublic(SQLModel):
    part_number: int
    upload_url: str


class MultipartPartsPublic(SQLModel):
    upload_id: uuid.UUID
    multipart_upload_id: str
    parts: list[MultipartPartPublic]


class SourceDocumentPublic(SQLModel):
    id: uuid.UUID
    legal_instrument_id: uuid.UUID
    authority: str
    title: str
    source_url: str
    mime_type: str
    sha256: str
    storage_backend: str
    storage_bucket: str | None = None
    storage_key: str
    original_filename: str
    file_size: int
    page_count: int | None = None
    published_at: date
    retrieved_at: datetime
    source_tier: SourceTier
    is_legal_revision: bool
    legal_revision_effective_at: date | None = None
    parser_version: str | None = None
    verification_status: VerificationStatus
    created_by: uuid.UUID | None = None
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    lock_version: int
    created_at: datetime


class SourceDocumentVerificationRequest(IdempotentMutation):
    reason: str = Field(min_length=3, max_length=1024)


class SourceUploadCompleteResponse(SQLModel):
    upload: SourceUploadPublic
    source_document: SourceDocumentPublic | None = None
    run: IngestionRunPublic | None = None
    duplicate: bool = False


class SourcePagePublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_document_id: uuid.UUID | None = None
    page_number: int
    role: PageRole
    inclusion_status: PageInclusionStatus
    inclusion_reason: str | None = None
    thumbnail_key: str | None = None
    thumbnail_url: str | None = None
    text_density: float | None = None
    orientation: str | None = None
    column_count: int | None = None
    image_coverage: float | None = None
    width: float | None = None
    height: float | None = None
    quality_signals: dict[str, Any] | None = None
    lock_version: int
    created_at: datetime


class SourcePagesPublic(SQLModel):
    data: list[SourcePagePublic]
    count: int


class PageSelectionItem(SQLModel):
    page_number: int = Field(ge=1)
    inclusion_status: PageInclusionStatus
    inclusion_reason: str | None = None
    expected_version: int = Field(ge=1)


class PageSelectionUpdate(SQLModel):
    idempotency_key: str = Field(min_length=8, max_length=256)
    expected_run_version: int = Field(ge=1)
    pages: list[PageSelectionItem] = Field(min_length=1)
