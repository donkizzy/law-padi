import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import EvaluationDatasetKind, EvaluationItemKind, ProvisionKind
from app.legal.models.common import get_datetime_utc


class EvaluationDataset(SQLModel, table=True):
    __tablename__ = "evaluation_dataset"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: str = Field(unique=True, index=True, max_length=128)
    name: str = Field(max_length=255)
    dataset_kind: EvaluationDatasetKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    language: str = Field(default="en", max_length=16, index=True)
    jurisdiction: str = Field(default="NG", max_length=255, index=True)
    instrument_slug: str | None = Field(default=None, max_length=255, index=True)
    source_document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="source_document.id",
        index=True,
        ondelete="SET NULL",
    )
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    content_sha256: str | None = Field(default=None, max_length=64, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EvaluationItem(SQLModel, table=True):
    __tablename__ = "evaluation_item"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "item_key",
            name="uq_evaluation_item_dataset_key",
        ),
        CheckConstraint(
            "(item_kind <> 'gold_provision') OR "
            "(canonical_path IS NOT NULL AND expected_text IS NOT NULL)",
            name="ck_evaluation_item_gold_provision_fields",
        ),
        CheckConstraint(
            "(item_kind <> 'retrieval_query') OR "
            "(query_text IS NOT NULL AND expected_canonical_paths IS NOT NULL)",
            name="ck_evaluation_item_retrieval_query_fields",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dataset_id: uuid.UUID = Field(
        foreign_key="evaluation_dataset.id",
        index=True,
        ondelete="CASCADE",
    )
    item_key: str = Field(max_length=255, index=True)
    item_kind: EvaluationItemKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    canonical_path: str | None = Field(default=None, max_length=512, index=True)
    provision_kind: ProvisionKind | None = Field(
        default=None,
        sa_column=Column(String(length=32), nullable=True, index=True),
    )
    section_number: str | None = Field(default=None, max_length=64, index=True)
    citation: str | None = Field(default=None, max_length=255)
    expected_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    query_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    expected_canonical_paths: list[str] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_spans: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    item_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("metadata", JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
