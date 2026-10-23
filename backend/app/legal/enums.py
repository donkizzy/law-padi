from enum import StrEnum


class InstrumentType(StrEnum):
    CONSTITUTION = "constitution"
    ALTERATION_ACT = "alteration_act"
    BILL = "bill"
    ACT = "act"
    REGULATION = "regulation"


class InstrumentStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ENACTED = "enacted"
    REPEALED = "repealed"
    SUPERSEDED = "superseded"


class SourceTier(StrEnum):
    OFFICIAL = "official"
    TRUSTED_SECONDARY = "trusted_secondary"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


class ExtractionMethod(StrEnum):
    TEXT = "text"
    OCR = "ocr"
    MANUAL = "manual"
    MIXED = "mixed"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class SourceUploadStatus(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    UPLOADED_PENDING_VERIFICATION = "uploaded_pending_verification"
    COMPLETED = "completed"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_REVIEW = "waiting_for_review"
    READY_TO_EMBED = "ready_to_embed"
    INDEXING = "indexing"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionStage(StrEnum):
    UPLOADING = "uploading"
    VERIFYING_UPLOAD = "verifying_upload"
    MALWARE_SCAN = "malware_scan"
    PROFILING = "profiling"
    AWAITING_PAGE_CONFIRMATION = "awaiting_page_confirmation"
    RENDERING = "rendering"
    NATIVE_EXTRACTION = "native_extraction"
    LOCAL_OCR = "local_ocr"
    MANAGED_OCR = "managed_ocr"
    NORMALIZING = "normalizing"
    PARSING_STRUCTURE = "parsing_structure"
    VALIDATING_DOCUMENT = "validating_document"
    REVIEW = "review"
    MATERIALIZING = "materializing"
    BUILDING_RETRIEVAL_DOCUMENTS = "building_retrieval_documents"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    VALIDATING_INDEX = "validating_index"
    PUBLISHING = "publishing"


class IngestionStepStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class IngestionTaskStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PageRole(StrEnum):
    FRONT_MATTER = "front_matter"
    TABLE_OF_CONTENTS = "table_of_contents"
    LEGAL_BODY = "legal_body"
    SCHEDULE = "schedule"
    BACK_MATTER = "back_matter"


class PageInclusionStatus(StrEnum):
    SUGGESTED_INCLUDE = "suggested_include"
    SUGGESTED_EXCLUDE = "suggested_exclude"
    INCLUDED = "included"
    EXCLUDED = "excluded"


class IngestionArtifactType(StrEnum):
    ORIGINAL_SOURCE = "original_source"
    PAGE_THUMBNAIL = "page_thumbnail"
    RAW_EXTRACTION = "raw_extraction"
    NORMALIZED_PAGES = "normalized_pages"
    OCR_OUTPUT = "ocr_output"
    VALIDATION_REPORT = "validation_report"
    RETRIEVAL_DOCUMENTS = "retrieval_documents"
    EMBEDDINGS = "embeddings"
    RELEASE_MANIFEST = "release_manifest"


class ProvisionKind(StrEnum):
    CHAPTER = "chapter"
    PART = "part"
    CROSS_HEADING = "cross_heading"
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"
    SCHEDULE = "schedule"
    SCHEDULE_ITEM = "schedule_item"


class LegalStatus(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    REPEALED = "repealed"
    PROPOSED = "proposed"
    HISTORICAL = "historical"


class AmendmentStatus(StrEnum):
    DRAFT = "draft"
    PASSED = "passed"
    ENACTED = "enacted"
    REPEALED = "repealed"
    SUPERSEDED = "superseded"


class AmendmentOperationType(StrEnum):
    INSERT = "insert"
    SUBSTITUTE = "substitute"
    DELETE = "delete"
    REPEAL = "repeal"
    RENUMBER = "renumber"
    ADD_PROVISION = "add_provision"
    MOVE = "move"
    RENAME = "rename"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_CORRECTION = "needs_correction"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExtractionCandidateStatus(StrEnum):
    PROVISIONAL = "provisional"
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    NEEDS_CORRECTION = "needs_correction"
    APPROVED = "approved"
    REJECTED = "rejected"
    MATERIALIZED = "materialized"


class ReviewIssueSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


class ReviewIssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"


class ReviewDecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CORRECTION = "request_correction"


class AdminRole(StrEnum):
    INGESTION_UPLOADER = "ingestion_uploader"
    LEGAL_REVIEWER = "legal_reviewer"
    CORPUS_PUBLISHER = "corpus_publisher"


class AuditSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class BillStatus(StrEnum):
    DRAFT = "draft"
    INTRODUCED = "introduced"
    HOUSE_READING = "house_reading"
    HOUSE_PASSED = "house_passed"
    SENATE_READING = "senate_reading"
    SENATE_PASSED = "senate_passed"
    NASS_APPROVED = "nass_approved"
    STATE_RATIFICATION = "state_ratification"
    ENACTED = "enacted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class LegislativeChamber(StrEnum):
    HOUSE = "house"
    SENATE = "senate"
    NATIONAL_ASSEMBLY = "national_assembly"
    STATE_ASSEMBLIES = "state_assemblies"
    PRESIDENT = "president"
    OTHER = "other"


class LegislativeEventType(StrEnum):
    INTRODUCED = "introduced"
    READING = "reading"
    PASSED = "passed"
    APPROVED = "approved"
    RATIFIED = "ratified"
    ASSENTED = "assented"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    UPDATED = "updated"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AnswerStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    LOW_CONFIDENCE = "low_confidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceRole(StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    BACKGROUND = "background"


class EvaluationDatasetKind(StrEnum):
    LEGAL_GRADE_EXTRACTION = "legal_grade_extraction"
    RETRIEVAL_BENCHMARK = "retrieval_benchmark"
    OCR_BENCHMARK = "ocr_benchmark"


class EvaluationItemKind(StrEnum):
    GOLD_PROVISION = "gold_provision"
    RETRIEVAL_QUERY = "retrieval_query"
    OCR_PAGE = "ocr_page"


class CorpusReleaseStatus(StrEnum):
    BUILDING = "building"
    VALIDATING = "validating"
    APPROVED = "approved"
    PRODUCTION = "production"
    RETIRED = "retired"


class EmbeddingProviderKind(StrEnum):
    OPENAI = "openai"
    HUGGINGFACE_TEI = "huggingface_tei"


class EmbeddingRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BENCHMARKING = "benchmarking"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VectorIndexStatus(StrEnum):
    BUILDING = "building"
    VALIDATING = "validating"
    READY = "ready"
    PROMOTED = "promoted"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ReleasePromotionStatus(StrEnum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
