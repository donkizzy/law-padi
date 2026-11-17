import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    ExtractionCandidateStatus,
    ProvisionKind,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.models.common import get_datetime_utc


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
