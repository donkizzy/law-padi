import uuid
from datetime import datetime
from typing import Any

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    CorpusReleaseStatus,
    InstrumentType,
    ReleasePromotionStatus,
    VectorIndexStatus,
)
from app.legal.schemas.common import IdempotentMutation
from app.legal.schemas.ingestion import IngestionArtifactPublic


class CorpusReleasePublic(SQLModel):
    id: uuid.UUID
    version: str
    status: CorpusReleaseStatus
    source_manifest_hash: str | None = None
    embedding_model: str | None = None
    embedding_model_version: str | None = None
    parser_version: str | None = None
    validation_report: dict[str, Any] | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    lock_version: int
    created_at: datetime
    evidence_count: int
    instrument_slugs: list[str] = Field(default_factory=list)
    instrument_types: list[InstrumentType] = Field(default_factory=list)


class CompositeReleaseMember(SQLModel):
    release_id: uuid.UUID
    expected_version: int = Field(ge=1)


class CompositeReleaseCreate(SQLModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    version: str = Field(
        min_length=1,
        max_length=128,
        schema_extra={"pattern": r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$"},
    )
    base_release_id: uuid.UUID
    expected_base_version: int = Field(ge=1)
    members: list[CompositeReleaseMember] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_members(self) -> CompositeReleaseCreate:
        ids = [member.release_id for member in self.members]
        if self.base_release_id in ids or len(set(ids)) != len(ids):
            raise ValueError(
                "Composite members must be distinct from one another and the base release"
            )
        return self


class CorpusReleasesPublic(SQLModel):
    data: list[CorpusReleasePublic]
    count: int


class CorpusReleaseManifestPublic(SQLModel):
    release_id: uuid.UUID
    release_version: str
    source_manifest_hash: str | None = None
    artifact: IngestionArtifactPublic | None = None
    manifest: dict[str, Any]


class CorpusReleaseVectorIndexPublic(SQLModel):
    id: uuid.UUID
    release_id: uuid.UUID
    embedding_run_id: uuid.UUID
    profile_id: uuid.UUID
    collection_name: str
    alias_name: str
    status: VectorIndexStatus
    point_count: int
    vector_dimensions: int
    payload_schema_hash: str | None = None
    checksum: str | None = None
    validation_report: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CorpusReleaseRetrievalIndexBuildPublic(SQLModel):
    id: uuid.UUID
    release_id: uuid.UUID
    embedding_run_id: uuid.UUID
    profile_id: uuid.UUID
    backend: str
    index_kind: str
    relation_name: str
    physical_index_name: str | None = None
    status: VectorIndexStatus
    expected_segment_count: int
    stored_segment_count: int
    stored_embedding_count: int
    vector_dimensions: int
    profile_hash: str | None = None
    payload_schema_hash: str | None = None
    checksum: str | None = None
    validation_report: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CorpusReleasePromotionAttemptPublic(SQLModel):
    id: uuid.UUID
    release_id: uuid.UUID
    vector_index_id: uuid.UUID | None = None
    retrieval_index_build_id: uuid.UUID | None = None
    index_kind: str | None = None
    requested_by: uuid.UUID | None = None
    status: ReleasePromotionStatus
    previous_release_id: uuid.UUID | None = None
    previous_collection_name: str | None = None
    target_collection_name: str | None = None
    rollback_completed: bool
    error_details: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class CorpusReleaseActorSeparationPublic(SQLModel):
    current_actor_id: uuid.UUID
    source_uploader_ids: list[uuid.UUID]
    current_actor_is_source_uploader: bool
    approved_by: uuid.UUID | None = None
    approved_by_differs_from_uploaders: bool | None = None
    superuser_override_recorded: bool
    override_reasons: list[str] = Field(default_factory=list)


class ActiveRetrievalTargetPublic(SQLModel):
    index_kind: str
    release_id: uuid.UUID
    embedding_run_id: uuid.UUID
    retrieval_index_build_id: uuid.UUID
    profile_id: uuid.UUID
    lock_version: int
    activated_by: uuid.UUID | None = None
    activated_at: datetime
    updated_at: datetime


class CorpusReleasePublicationEvidencePublic(SQLModel):
    release_id: uuid.UUID
    release_version: str
    vector_indexes: list[CorpusReleaseVectorIndexPublic]
    retrieval_index_builds: list[CorpusReleaseRetrievalIndexBuildPublic]
    promotion_attempts: list[CorpusReleasePromotionAttemptPublic]
    active_targets: list[ActiveRetrievalTargetPublic]
    actor_separation: CorpusReleaseActorSeparationPublic


class CorpusReleaseValidationRequest(IdempotentMutation):
    pass


class CorpusReleasePublishRequest(IdempotentMutation):
    superuser_override_reason: str | None = None


class CorpusReleasePublishResponse(SQLModel):
    release: CorpusReleasePublic
    promotion_status: ReleasePromotionStatus
    vector_index_status: VectorIndexStatus | None = None


class PublicProvisionVersion(SQLModel):
    id: uuid.UUID
    provision_id: uuid.UUID
    text: str
    canonical_path: str
    release_version: str
    status: CorpusReleaseStatus


class PublicProvisionVersions(SQLModel):
    data: list[PublicProvisionVersion]
    count: int
