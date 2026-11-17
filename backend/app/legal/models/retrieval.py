import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlmodel import Field, SQLModel

from app.legal.enums import EmbeddingProviderKind, EmbeddingRunStatus, VectorIndexStatus
from app.legal.models.common import (
    RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH,
    get_datetime_utc,
)


class EmbeddingProfile(SQLModel, table=True):
    __tablename__ = "embedding_profile"
    __table_args__ = (
        CheckConstraint(
            "vector_dimensions = 1024",
            name="ck_embedding_profile_vector_dimensions",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=128)
    provider: EmbeddingProviderKind = Field(
        sa_column=Column(String(length=32), nullable=False, index=True)
    )
    model_name: str = Field(max_length=255, index=True)
    model_revision: str | None = Field(default=None, max_length=128)
    vector_dimensions: int = Field(index=True)
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EmbeddingRun(SQLModel, table=True):
    __tablename__ = "embedding_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id",
        index=True,
        ondelete="CASCADE",
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id",
        index=True,
        ondelete="CASCADE",
    )
    status: EmbeddingRunStatus = Field(
        default=EmbeddingRunStatus.PENDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    benchmark_dataset_version: str | None = Field(
        default=None, max_length=RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH
    )
    recall_at_10: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    ndcg_at_10: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    cost_usd: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    p95_latency_ms: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    selected_for_release: bool = Field(default=False, index=True)
    metrics: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
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


class RetrievalSegment(SQLModel, table=True):
    """Immutable, release-scoped retrieval text derived from canonical law."""

    __tablename__ = "retrieval_segment"
    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "provision_version_id",
            "segment_index",
            name="uq_retrieval_segment_release_version_index",
        ),
        CheckConstraint(
            "segment_index >= 1", name="ck_retrieval_segment_index_positive"
        ),
        CheckConstraint(
            "segment_count >= segment_index",
            name="ck_retrieval_segment_count_covers_index",
        ),
        CheckConstraint("language = 'en'", name="ck_retrieval_segment_language_en"),
        CheckConstraint(
            "retrieval_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_segment_text_hash",
        ),
        CheckConstraint(
            "authoritative_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_segment_authoritative_hash",
        ),
        Index("ix_retrieval_segment_release_kind", "release_id", "index_kind"),
        Index("ix_retrieval_segment_release_instrument", "release_id", "instrument_id"),
        Index("ix_retrieval_segment_provision_version", "provision_version_id"),
        Index(
            "ix_retrieval_segment_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id", index=True, ondelete="CASCADE"
    )
    release_entry_id: uuid.UUID = Field(
        foreign_key="corpus_release_entry.id", ondelete="CASCADE"
    )
    instrument_id: uuid.UUID = Field(
        foreign_key="legal_instrument.id", index=True, ondelete="CASCADE"
    )
    provision_id: uuid.UUID = Field(foreign_key="provision.id", ondelete="CASCADE")
    provision_version_id: uuid.UUID = Field(
        foreign_key="provision_version.id", ondelete="CASCADE"
    )
    source_document_id: uuid.UUID = Field(
        foreign_key="source_document.id", ondelete="CASCADE"
    )
    index_kind: str = Field(default="enacted", max_length=32)
    segment_index: int
    segment_count: int
    language: str = Field(default="en", max_length=16)
    citation: str = Field(max_length=255)
    canonical_path: str = Field(max_length=512, index=True)
    ancestor_headings: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    ancestor_text: str = Field(sa_column=Column(Text, nullable=False))
    heading: str | None = Field(default=None, max_length=512)
    retrieval_text: str = Field(sa_column=Column(Text, nullable=False))
    retrieval_text_sha256: str = Field(max_length=64)
    authoritative_text_sha256: str = Field(max_length=64)
    lexical_profile_version: str = Field(default="postgres-simple-v1", max_length=128)
    search_vector: Any = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed(
                "setweight(to_tsvector('simple', coalesce(citation, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(heading, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(ancestor_text, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(retrieval_text, '')), 'D')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RetrievalEmbedding(SQLModel, table=True):
    """A model-specific vector; never overwrite vectors from another run."""

    __tablename__ = "retrieval_embedding"
    __table_args__ = (
        Index("ix_retrieval_embedding_release_profile", "release_id", "profile_id"),
        UniqueConstraint(
            "embedding_run_id",
            "segment_id",
            name="uq_retrieval_embedding_run_segment",
        ),
        CheckConstraint(
            "vector_dimensions = 1024",
            name="ck_retrieval_embedding_dimensions",
        ),
        CheckConstraint(
            "vector_dims(embedding) = vector_dimensions",
            name="ck_retrieval_embedding_vector_dims",
        ),
        CheckConstraint(
            "embedding_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_embedding_hash",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    segment_id: uuid.UUID = Field(
        foreign_key="retrieval_segment.id", index=True, ondelete="CASCADE"
    )
    release_id: uuid.UUID = Field(foreign_key="corpus_release.id", ondelete="CASCADE")
    embedding_run_id: uuid.UUID = Field(
        foreign_key="embedding_run.id", index=True, ondelete="CASCADE"
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id", ondelete="CASCADE"
    )
    vector_dimensions: int = Field(default=1024)
    embedding: list[float] = Field(sa_column=Column(Vector(1024), nullable=False))
    embedding_sha256: str = Field(max_length=64)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RetrievalIndexBuild(SQLModel, table=True):
    """Validation evidence for a release-scoped retrieval dataset."""

    __tablename__ = "retrieval_index_build"
    __table_args__ = (
        CheckConstraint("backend = 'pgvector'", name="ck_retrieval_index_backend"),
        CheckConstraint(
            "vector_dimensions = 1024",
            name="ck_retrieval_index_dimensions",
        ),
        UniqueConstraint(
            "release_id",
            "embedding_run_id",
            "index_kind",
            name="uq_retrieval_index_build_release_run_kind",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id", index=True, ondelete="CASCADE"
    )
    embedding_run_id: uuid.UUID = Field(
        foreign_key="embedding_run.id", index=True, ondelete="CASCADE"
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id", index=True, ondelete="CASCADE"
    )
    backend: str = Field(default="pgvector", max_length=32)
    index_kind: str = Field(default="enacted", max_length=32, index=True)
    relation_name: str = Field(default="retrieval_embedding", max_length=128)
    physical_index_name: str | None = Field(default=None, max_length=255)
    status: VectorIndexStatus = Field(
        default=VectorIndexStatus.BUILDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    expected_segment_count: int = Field(default=0)
    stored_segment_count: int = Field(default=0)
    stored_embedding_count: int = Field(default=0)
    vector_dimensions: int = Field(default=1024)
    profile_hash: str | None = Field(default=None, max_length=64)
    payload_schema_hash: str | None = Field(default=None, max_length=64)
    checksum: str | None = Field(default=None, max_length=64)
    validation_report: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ActiveRetrievalTarget(SQLModel, table=True):
    """The transactional production pointer for one retrieval index kind."""

    __tablename__ = "active_retrieval_target"

    index_kind: str = Field(primary_key=True, max_length=32)
    release_id: uuid.UUID = Field(
        foreign_key="corpus_release.id", ondelete="RESTRICT", index=True
    )
    embedding_run_id: uuid.UUID = Field(
        foreign_key="embedding_run.id", ondelete="RESTRICT"
    )
    retrieval_index_build_id: uuid.UUID = Field(
        foreign_key="retrieval_index_build.id", ondelete="RESTRICT"
    )
    profile_id: uuid.UUID = Field(
        foreign_key="embedding_profile.id", ondelete="RESTRICT"
    )
    lock_version: int = Field(default=1)
    activated_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    activated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
