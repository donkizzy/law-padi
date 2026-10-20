import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel

from app.legal.enums import (
    AdminRole,
    AuditSeverity,
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    InstrumentStatus,
    InstrumentType,
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    ReleasePromotionStatus,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    SourceTier,
    SourceUploadStatus,
    VectorIndexStatus,
    VerificationStatus,
)


class IdempotentMutation(SQLModel):
    idempotency_key: str = Field(min_length=8, max_length=256)
    expected_version: int = Field(ge=1)


class AdminMetrics(SQLModel):
    active_runs: int
    blocked_runs: int
    failed_runs: int
    queue_depth: int
    worker_heartbeat: datetime | None = None
    pages_processed: int
    ocr_fallback_rate: float
    review_issues: int
    auto_approval_rate: float
    embedding_progress: float
    current_production_release: str | None = None


class AdminOperationalAlertPublic(SQLModel):
    id: str
    alert_type: str
    severity: AuditSeverity
    title: str
    message: str
    detected_at: datetime
    run_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    issue_id: uuid.UUID | None = None
    release_id: uuid.UUID | None = None
    embedding_run_id: uuid.UUID | None = None
    promotion_attempt_id: uuid.UUID | None = None
    evidence: dict[str, Any] | None = None


class AdminOperationalAlertsPublic(SQLModel):
    data: list[AdminOperationalAlertPublic]
    count: int


class SourceUploadCreate(SQLModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    expected_size: int = Field(gt=0, le=500 * 1024 * 1024)
    expected_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    original_filename: str = Field(min_length=1, max_length=512)
    mime_type: str
    instrument_slug: str = Field(min_length=1, max_length=255)
    instrument_title: str = Field(min_length=1, max_length=512)
    instrument_type: Literal[InstrumentType.CONSTITUTION, InstrumentType.ACT] = (
        InstrumentType.CONSTITUTION
    )
    instrument_short_title: str | None = Field(default=None, max_length=255)
    instrument_year: int = Field(ge=1)
    instrument_status: InstrumentStatus
    enacted_at: date | None = None
    effective_at: date | None = None
    ceased_at: date | None = None
    is_legal_revision: bool = False
    legal_revision_effective_at: date | None = None
    source_title: str = Field(min_length=1, max_length=512)
    authority: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1, max_length=2048)
    source_tier: SourceTier
    published_at: date
    retrieved_at: date

    @field_validator("mime_type")
    @classmethod
    def validate_pdf_mime_type(cls, value: str) -> str:
        if value != "application/pdf":
            raise ValueError("Ingestion accepts PDF sources only")
        return value

    @model_validator(mode="after")
    def validate_legal_revision_metadata(self) -> SourceUploadCreate:
        if self.is_legal_revision and self.legal_revision_effective_at is None:
            raise ValueError("Legal revisions require an effective date")
        return self


class SourceUploadPublic(SQLModel):
    id: uuid.UUID
    idempotency_key: str
    source_document_id: uuid.UUID | None = None
    instrument_slug: str
    instrument_title: str
    instrument_type: InstrumentType = InstrumentType.CONSTITUTION
    source_title: str
    authority: str
    source_url: str
    source_tier: SourceTier
    is_legal_revision: bool
    legal_revision_effective_at: date | None = None
    original_filename: str
    mime_type: str
    expected_size: int
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    upload_backend: str
    quarantine_key: str
    canonical_key: str | None = None
    upload_url: str
    upload_headers: dict[str, str]
    multipart_required: bool
    status: SourceUploadStatus
    error_message: str | None = None
    lock_version: int
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CompletedMultipartPart(SQLModel):
    part_number: int = Field(ge=1)
    etag: str = Field(min_length=1, max_length=512)


class SourceUploadComplete(IdempotentMutation):
    actual_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    completed_parts: list[CompletedMultipartPart] | None = None


class MultipartPartsRequest(IdempotentMutation):
    part_count: int = Field(ge=1, le=10000)


class MultipartPartPublic(SQLModel):
    part_number: int
    upload_url: str


class MultipartPartsPublic(SQLModel):
    upload_id: uuid.UUID
    multipart_upload_id: str
    parts: list[MultipartPartPublic]


class SourceDocumentPublic(SQLModel):
    id: uuid.UUID
    legal_instrument_id: uuid.UUID
    authority: str
    title: str
    source_url: str
    mime_type: str
    sha256: str
    storage_backend: str
    storage_bucket: str | None = None
    storage_key: str
    original_filename: str
    file_size: int
    page_count: int | None = None
    published_at: date
    retrieved_at: datetime
    source_tier: SourceTier
    is_legal_revision: bool
    legal_revision_effective_at: date | None = None
    parser_version: str | None = None
    verification_status: VerificationStatus
    created_by: uuid.UUID | None = None
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    lock_version: int
    created_at: datetime


class SourceDocumentVerificationRequest(IdempotentMutation):
    reason: str = Field(min_length=3, max_length=1024)


class IngestionStepPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    dependency_step_id: uuid.UUID | None = None
    stage: IngestionStage
    status: IngestionStepStatus
    attempt_count: int
    lease_owner: str | None = None
    leased_until: datetime | None = None
    heartbeat_at: datetime | None = None
    total_units: int
    completed_units: int
    failed_units: int
    lock_version: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metrics: dict[str, Any] | None = None
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class IngestionEventPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None = None
    sequence: int
    event_type: str
    stage: IngestionStage | None = None
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class IngestionTaskPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None = None
    task_type: str
    status: IngestionTaskStatus
    priority: int
    attempt_count: int
    max_attempts: int
    lease_owner: str | None = None
    leased_until: datetime | None = None
    heartbeat_at: datetime | None = None
    lock_version: int
    payload: dict[str, Any]
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class IngestionRunPublic(SQLModel):
    id: uuid.UUID
    source_upload_id: uuid.UUID | None = None
    source_document_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    status: IngestionRunStatus
    current_stage: IngestionStage
    pipeline_version: str
    pipeline_config: dict[str, Any]
    expected_page_count: int | None = None
    total_units: int
    completed_units: int
    failed_units: int
    lock_version: int
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class SourceUploadCompleteResponse(SQLModel):
    upload: SourceUploadPublic
    source_document: SourceDocumentPublic | None = None
    run: IngestionRunPublic | None = None
    duplicate: bool = False


class IngestionRunDetail(IngestionRunPublic):
    steps: list[IngestionStepPublic]
    events: list[IngestionEventPublic]
    tasks: list[IngestionTaskPublic]


class IngestionRunsPublic(SQLModel):
    data: list[IngestionRunPublic]
    count: int


class IngestionRunControlRequest(IdempotentMutation):
    reason: str | None = None


class SourcePagePublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_document_id: uuid.UUID | None = None
    page_number: int
    role: PageRole
    inclusion_status: PageInclusionStatus
    inclusion_reason: str | None = None
    thumbnail_key: str | None = None
    thumbnail_url: str | None = None
    text_density: float | None = None
    orientation: str | None = None
    column_count: int | None = None
    image_coverage: float | None = None
    width: float | None = None
    height: float | None = None
    quality_signals: dict[str, Any] | None = None
    lock_version: int
    created_at: datetime


class SourcePagesPublic(SQLModel):
    data: list[SourcePagePublic]
    count: int


class PageSelectionItem(SQLModel):
    page_number: int = Field(ge=1)
    inclusion_status: PageInclusionStatus
    inclusion_reason: str | None = None
    expected_version: int = Field(ge=1)


class PageSelectionUpdate(SQLModel):
    idempotency_key: str = Field(min_length=8, max_length=256)
    expected_run_version: int = Field(ge=1)
    pages: list[PageSelectionItem] = Field(min_length=1)


class IngestionArtifactPublic(SQLModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_page_id: uuid.UUID | None = None
    artifact_type: IngestionArtifactType
    storage_key: str
    sha256: str | None = None
    mime_type: str | None = None
    retention_policy: str
    artifact_metadata: dict[str, Any] | None = None
    created_at: datetime


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
            self.kind in {ProvisionKind.CHAPTER, ProvisionKind.PART}
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


class OcrBenchmarkSampleInput(SQLModel):
    item_key: str
    provider: str
    text: str | None = None
    confidence: float | None = None
    cost_usd: float | None = None
    timing_ms: float | None = None
    failure: str | None = None


class OcrBenchmarkEvaluateRequest(IdempotentMutation):
    dataset_version: str
    samples: list[OcrBenchmarkSampleInput]


class OcrBenchmarkProviderResult(SQLModel):
    provider: str
    page_count: int
    failure_count: int
    mean_character_accuracy: float
    mean_confidence: float | None = None
    total_cost_usd: float | None = None
    mean_timing_ms: float | None = None


class OcrBenchmarkPublic(SQLModel):
    dataset_version: str
    sample_count: int
    winner: str | None = None
    providers: list[OcrBenchmarkProviderResult]
    active_dataset_items: int


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


class LegalSearchRequest(SQLModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    index_kind: Literal["enacted", "proposals"] = "enacted"
    mode: Literal["auto", "semantic"] = "auto"
    instrument: str | None = Field(
        default=None,
        max_length=255,
        schema_extra={"pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$"},
    )
    release_version: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter a section reference or topic")
        return value


class InstrumentIdentity(SQLModel):
    # Defaults retain compatibility with saved Constitution evidence snapshots.
    instrument_slug: str = "constitution-1999"
    instrument_title: str = "Constitution of the Federal Republic of Nigeria 1999"
    instrument_short_title: str | None = None
    instrument_type: InstrumentType = InstrumentType.CONSTITUTION
    short_citation: str | None = None


class ProvisionReference(InstrumentIdentity):
    id: uuid.UUID
    canonical_path: str
    kind: ProvisionKind
    number: str | None = None
    heading: str | None = None
    title: str | None = None
    citation: str
    has_text: bool
    authoritative_text: str | None = None


class LegalSearchResult(InstrumentIdentity):
    canonical_path: str
    citation: str
    heading: str | None = None
    title: str | None = None
    ancestor_headings: list[str]
    authoritative_text: str
    source_document_id: uuid.UUID
    source_page_start: int | None = None
    source_page_end: int | None = None
    legal_status: str
    release_version: str
    dense_rank: int | None = None
    lexical_rank: int | None = None
    hybrid_score: float
    provision_id: uuid.UUID
    provision_version_id: uuid.UUID
    release_id: uuid.UUID
    kind: ProvisionKind
    edition_label: str
    source_title: str
    source_authority: str
    source_url: str
    source_content_url: str
    ancestors: list[ProvisionReference]
    children: list[ProvisionReference]


class CitationOutcome(SQLModel):
    reference: str
    status: Literal["resolved", "ambiguous", "missing", "unsupported"]
    evidence_ids: list[str] = Field(default_factory=list)
    message: str | None = None


class EvidenceItem(InstrumentIdentity):
    evidence_id: str
    provision_id: uuid.UUID
    provision_version_id: uuid.UUID
    canonical_path: str
    citation: str
    title: str | None = None
    authoritative_text: str
    text_sha256: str
    ancestor_citations: list[str]
    legal_status: str
    edition_label: str
    release_id: uuid.UUID
    release_version: str
    source_document_id: uuid.UUID
    source_title: str
    source_authority: str
    source_url: str
    source_content_url: str
    source_page_start: int | None = None
    source_page_end: int | None = None


class LegalSearchResponse(SQLModel):
    data: list[LegalSearchResult]
    count: int
    outcome: Literal[
        "exact", "matches", "ambiguous", "not_found", "unsupported_reference", "partial"
    ] = "matches"
    retrieval_mode: Literal["exact", "hybrid", "lexical"] = "exact"
    message: str | None = None
    # Stable key for message, so clients can show it in the reader's language.
    message_code: str | None = None
    release_version: str
    edition_label: str
    citation_outcomes: list[CitationOutcome] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    # Language detected in the query, and the English text searched when the
    # query was translated.
    query_language: str | None = None
    searched_query: str | None = None


class LegalReleasePublic(SQLModel):
    release_id: uuid.UUID
    release_version: str
    index_kind: str
    embedding_run_id: uuid.UUID
    retrieval_index_build_id: uuid.UUID
    edition_label: str
    available: bool = True
    legal_statuses: list[str]


class LegalInstrumentPublic(SQLModel):
    slug: str
    title: str
    short_title: str | None = None
    instrument_type: InstrumentType
    edition_label: str
    edition_note: str
    section_count: int
    legal_statuses: list[str]


class LegalInstrumentsPublic(SQLModel):
    data: list[LegalInstrumentPublic]
    count: int
    release_version: str


class ProvisionTreePublic(SQLModel):
    data: list[ProvisionReference]
    count: int
    release_version: str
    edition_label: str
    parent: ProvisionReference | None = None
    scope: Literal["children", "all"] = "children"
    instrument_slug: str = "constitution-1999"


class MyAdminRolesPublic(SQLModel):
    user_id: uuid.UUID
    is_superuser: bool
    roles: list[AdminRole]


class AuditEventPublic(SQLModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    severity: AuditSeverity
    reason: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class AuditEventsPublic(SQLModel):
    data: list[AuditEventPublic]
    count: int
