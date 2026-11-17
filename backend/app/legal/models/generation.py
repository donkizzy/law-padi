import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.models.common import get_datetime_utc


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
    # The reader's explicit answer language; None follows the question.
    answer_language: str | None = Field(default=None, max_length=16)
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
    # The API request that created the run, so worker logs can be joined to it.
    request_id: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class GenerationAdmission(SQLModel, table=True):
    """Short-lived quota history that survives deletion of chat content."""

    __tablename__ = "generation_admission"
    __table_args__ = (
        Index("ix_generation_admission_user_time", "user_id", "created_at"),
        Index("ix_generation_admission_guest_time", "guest_digest", "created_at"),
        Index("ix_generation_admission_client_time", "client_digest", "created_at"),
    )

    run_id: uuid.UUID = Field(primary_key=True)
    user_id: uuid.UUID | None = Field(default=None)
    guest_digest: str | None = Field(default=None, max_length=64)
    # SHA-256 of the client IP, kept only for guest-tier admissions so a new
    # guest cookie cannot reset the allowance of the network it came from.
    client_digest: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
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


class GenerationBudgetMonth(SQLModel, table=True):
    __tablename__ = "generation_budget_month"

    # First date of the Lagos calendar month. Only paid DeepSeek calls use this
    # ledger; query embeddings must have their own provider-enforced allowance.
    month: date = Field(primary_key=True)
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
