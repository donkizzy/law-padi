import uuid
from datetime import UTC, date, datetime
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
    AmendmentOperationType,
    AmendmentStatus,
    AnswerStatus,
    BillStatus,
    CorpusReleaseStatus,
    EvidenceRole,
    ExtractionMethod,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    LegislativeChamber,
    LegislativeEventType,
    MessageRole,
    ProvisionKind,
    ReviewStatus,
    SourceTier,
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

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    legal_instrument_id: uuid.UUID = Field(
        foreign_key="legal_instrument.id",
        index=True,
        ondelete="CASCADE",
    )
    authority: str = Field(max_length=255, index=True)
    title: str = Field(max_length=512)
    source_url: str | None = Field(default=None, max_length=2048)
    mime_type: str | None = Field(default=None, max_length=255)
    sha256: str | None = Field(default=None, unique=True, index=True, max_length=64)
    storage_key: str | None = Field(default=None, max_length=1024)
    published_at: date | None = None
    retrieved_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
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
    verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
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


class CorpusRelease(SQLModel, table=True):
    __tablename__ = "corpus_release"

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
