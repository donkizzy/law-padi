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


class ProvisionKind(StrEnum):
    CHAPTER = "chapter"
    PART = "part"
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


class CorpusReleaseStatus(StrEnum):
    BUILDING = "building"
    VALIDATING = "validating"
    APPROVED = "approved"
    PRODUCTION = "production"
    RETIRED = "retired"
