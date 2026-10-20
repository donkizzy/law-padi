import uuid
from datetime import datetime
from typing import Any, Literal

from sqlmodel import Field, SQLModel

from app.legal.schemas import CitationOutcome, EvidenceItem


class ConversationCreate(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    release_version: str | None = Field(default=None, min_length=1, max_length=128)


class ChatCapabilities(SQLModel):
    conversations_enabled: bool
    explanations_enabled: bool
    supported_languages: list[str]
    question_max_length: int = 2000
    build_revision: str
    prompt_version: str


class ConversationUpdate(SQLModel):
    title: str = Field(min_length=1, max_length=255)


class ConversationPublic(SQLModel):
    id: uuid.UUID
    title: str | None
    release_version: str
    edition_label: str
    created_at: datetime
    updated_at: datetime


class MessagePublic(SQLModel):
    id: uuid.UUID
    role: str
    content: str
    answer_status: str | None
    answer_content: dict[str, Any] | None
    evidence_snapshot: list[dict[str, Any]] | None
    helpful: bool | None = None
    created_at: datetime


class ConversationDetail(ConversationPublic):
    messages: list[MessagePublic]
    active_run_id: uuid.UUID | None = None
    has_more_messages: bool = False
    next_before: uuid.UUID | None = None


class ConversationList(SQLModel):
    data: list[ConversationPublic]
    count: int


class MessageCreate(SQLModel):
    question: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=128)
    selected_provision_version_id: uuid.UUID | None = None


class MessageAccepted(SQLModel):
    run_id: uuid.UUID
    user_message_id: uuid.UUID
    status: str


class ClaimResult(SQLModel):
    claimed_count: int


class FeedbackCreate(SQLModel):
    helpful: bool


class FeedbackPublic(SQLModel):
    message_id: uuid.UUID
    helpful: bool
    updated_at: datetime


class ChatMetrics(SQLModel):
    window_hours: int = 24
    accepted_questions: int
    finished_answers: int
    explained_answers: int
    average_finish_ms: float | None
    outcomes: dict[str, int]
    helpful_ratings: int
    unhelpful_ratings: int


class ExplanationBlock(SQLModel):
    text: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1)
    quotation: str | None = None


class ExplanationDraft(SQLModel):
    direct_answer: (
        Literal["yes", "no", "depends", "explain", "not_addressed"] | None
    ) = None
    blocks: list[ExplanationBlock] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class ExplanationAnswer(SQLModel):
    outcome: Literal[
        "completed",
        "partial_evidence",
        "insufficient_evidence",
        "clarification_required",
        "provider_failure",
        "cancelled",
        "capacity_exhausted",
        "budget_exhausted",
        "validation_failed",
    ]
    label: str = "Plain-language explanation"
    blocks: list[ExplanationBlock] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    citation_outcomes: list[CitationOutcome] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    related_laws: list[str] = Field(default_factory=list)
    notice: str | None = None
