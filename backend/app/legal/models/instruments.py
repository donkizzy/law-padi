import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.legal.enums import InstrumentStatus, InstrumentType, LegalStatus, ProvisionKind
from app.legal.models.common import get_datetime_utc


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
