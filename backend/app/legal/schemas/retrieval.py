import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel

from app.legal.enums import EmbeddingProviderKind, EmbeddingRunStatus


class EmbeddingBenchmarkResult(SQLModel):
    profile_id: uuid.UUID
    provider: EmbeddingProviderKind
    model_name: str
    status: EmbeddingRunStatus
    recall_at_10: float | None = None
    ndcg_at_10: float | None = None
    cost_usd: float | None = None
    p95_latency_ms: float | None = None
    selected_for_release: bool
    metrics: dict[str, Any] | None = None


class EmbeddingBenchmarkPublic(SQLModel):
    release_id: uuid.UUID
    results: list[EmbeddingBenchmarkResult]


class EmbeddingProfileCreate(SQLModel):
    name: str = Field(min_length=1, max_length=128)
    provider: EmbeddingProviderKind
    model_name: str = Field(min_length=1, max_length=255)
    model_revision: str = Field(min_length=1, max_length=128)
    vector_dimensions: int = Field(default=1024, ge=1024, le=1024)
    configuration: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class EmbeddingProfileUpdate(SQLModel):
    model_revision: str | None = Field(default=None, min_length=1, max_length=128)
    configuration: dict[str, Any] | None = None
    is_active: bool | None = None


class EmbeddingProfilePublic(SQLModel):
    id: uuid.UUID
    name: str
    provider: EmbeddingProviderKind
    model_name: str
    model_revision: str | None
    vector_dimensions: int
    configuration: dict[str, Any]
    is_active: bool
    created_at: datetime
