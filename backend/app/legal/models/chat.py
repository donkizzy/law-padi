import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import AnswerStatus, EvidenceRole, MessageRole
from app.legal.models.common import get_datetime_utc


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
    # English rendering of a non-English question; retrieval and follow-ups
    # use it, while content keeps what the reader wrote.
    english_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
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


class MessageFeedback(SQLModel, table=True):
    __tablename__ = "message_feedback"

    message_id: uuid.UUID = Field(
        primary_key=True, foreign_key="conversation_message.id", ondelete="CASCADE"
    )
    helpful: bool
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
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
