import uuid
from datetime import datetime
from typing import Any

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    ExtractionCandidateStatus,
    ProvisionKind,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.schemas.common import IdempotentMutation
from app.legal.schemas.sources import SourceDocumentPublic


class ReviewIssuePublic(SQLModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    issue_type: str
    severity: ReviewIssueSeverity
    status: ReviewIssueStatus
    blocking: bool
    message: str
    evidence: dict[str, Any] | None = None
    resolved_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
    resolution_reason: str | None = None
    resolution_evidence: dict[str, Any] | None = None
    created_at: datetime


class CandidateRevisionPublic(SQLModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    revision_number: int
    previous_text: str | None = None
    revised_text: str | None = None
    diff: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    changed_fields: dict[str, Any] | None = None
    reason: str
    revised_by: uuid.UUID | None = None
    created_at: datetime


class ReviewDecisionPublic(SQLModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    decision: ReviewDecisionType
    decided_by: uuid.UUID | None = None
    reason: str
    created_at: datetime


class ReviewItemPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_document_id: uuid.UUID
    source_document: SourceDocumentPublic | None = None
    parent_candidate_id: uuid.UUID | None = None
    materialized_provision_id: uuid.UUID | None = None
    materialized_version_id: uuid.UUID | None = None
    kind: ProvisionKind
    number: str | None = None
    heading: str | None = None
    canonical_path: str
    sort_key: str
    raw_text: str | None = None
    latest_revision_text: str | None = None
    normalized_text: str | None = None
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_page_thumbnail_url: str | None = None
    source_spans: list[dict[str, Any]] | None = None
    ancestor_headings: list[str] | None = None
    parser_version: str | None = None
    extractor_version: str | None = None
    parser_confidence: float | None = None
    extractor_confidence: float | None = None
    status: ExtractionCandidateStatus
    blocking_issue_count: int
    revision_number: int
    lock_version: int
    issues: list[ReviewIssuePublic] = Field(default_factory=list)
    revisions: list[CandidateRevisionPublic] = Field(default_factory=list)
    decisions: list[ReviewDecisionPublic] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReviewItemsPublic(SQLModel):
    data: list[ReviewItemPublic]
    count: int


class ReviewItemUpdate(IdempotentMutation):
    revised_text: str | None = Field(default=None, min_length=1)
    heading: str | None = Field(default=None, max_length=512)
    kind: ProvisionKind | None = None
    number: str | None = Field(default=None, max_length=64)
    parent_candidate_id: uuid.UUID | None = None
    canonical_path: str | None = Field(default=None, min_length=1, max_length=512)
    sort_key: str | None = Field(default=None, min_length=1, max_length=255)
    source_page_start: int | None = Field(default=None, ge=1)
    source_page_end: int | None = Field(default=None, ge=1)
    source_spans: list[dict[str, Any]] | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_patch_field(self) -> ReviewItemUpdate:
        patch_fields = self.model_fields_set - {
            "idempotency_key",
            "expected_version",
            "reason",
        }
        if not patch_fields:
            raise ValueError("At least one candidate field must be revised")
        for name in ("kind", "canonical_path", "sort_key", "revised_text"):
            if name in patch_fields and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        if (
            self.source_page_start is not None
            and self.source_page_end is not None
            and self.source_page_end < self.source_page_start
        ):
            raise ValueError("source_page_end must be at least source_page_start")
        return self


class ReviewItemDerive(ReviewItemUpdate):
    """Recover a provision from a retained candidate without approving it."""

    kind: ProvisionKind
    canonical_path: str = Field(min_length=1, max_length=512)
    sort_key: str = Field(min_length=1, max_length=255)
    source_page_start: int = Field(ge=1)
    source_page_end: int = Field(ge=1)
    source_spans: list[dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def require_body_or_structural_heading(self) -> ReviewItemDerive:
        if not (self.revised_text or "").strip() and not (
            self.kind
            in {
                ProvisionKind.CHAPTER,
                ProvisionKind.PART,
                ProvisionKind.CROSS_HEADING,
            }
            and (self.heading or "").strip()
        ):
            raise ValueError("A provision needs body text or a structural heading")
        return self


class ReviewDecisionCreate(IdempotentMutation):
    decision: ReviewDecisionType
    reason: str = Field(min_length=1)
    superuser_override_reason: str | None = None


class ReviewIssueUpdate(IdempotentMutation):
    reason: str = Field(min_length=1)
    evidence: dict[str, Any] | None = None
    superuser_override_reason: str | None = None
