import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import CorpusReleaseStatus, ReleasePromotionStatus
from app.legal.models.common import get_datetime_utc


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


class ReleasePromotionAttempt(SQLModel, table=True):
    __tablename__ = "release_promotion_attempt"
    __table_args__ = (
        Index("ix_release_promotion_index_kind", "index_kind"),
        Index(
            "ix_release_promotion_retrieval_index_build_id", "retrieval_index_build_id"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id",
        index=True,
        ondelete="CASCADE",
    )
    retrieval_index_build_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="retrieval_index_build.id",
        ondelete="SET NULL",
    )
    index_kind: str | None = Field(default=None, max_length=32)
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
