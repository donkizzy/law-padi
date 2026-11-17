import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    AmendmentOperationType,
    AmendmentStatus,
    BillStatus,
    LegislativeChamber,
    LegislativeEventType,
    ReviewStatus,
)
from app.legal.models.common import get_datetime_utc


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
