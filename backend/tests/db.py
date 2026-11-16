from sqlmodel import Session, delete, update

from app.legal.enums import CorpusReleaseStatus
from app.legal.models import (
    ActiveRetrievalTarget,
    AdminRoleAssignment,
    Amendment,
    AmendmentOperation,
    AuditEvent,
    CandidateRevision,
    ConstitutionalBill,
    Conversation,
    ConversationMessage,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    GenerationAdmission,
    GenerationBudgetDay,
    GenerationBudgetMonth,
    GenerationCapacity,
    GenerationEvent,
    GenerationReservation,
    GenerationRun,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalConcept,
    LegalConceptAlias,
    LegalInstrument,
    LegislativeEvent,
    MessageEvidence,
    Provision,
    ProvisionVersion,
    ReleasePromotionAttempt,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    TransactionalOutbox,
    VectorIndex,
)
from app.models import RateLimitCounter, User


def reset_database(session: Session) -> None:
    session.rollback()
    # Published releases are intentionally immutable in application traffic.
    # Test teardown must first move them back to a draft state so the
    # immutability trigger does not turn cleanup into a failed test run.
    session.exec(update(CorpusRelease).values(status=CorpusReleaseStatus.BUILDING))
    session.commit()
    for model in (
        AuditEvent,
        AdminRoleAssignment,
        GenerationAdmission,
        GenerationEvent,
        GenerationReservation,
        GenerationRun,
        GenerationBudgetDay,
        GenerationBudgetMonth,
        MessageEvidence,
        ConversationMessage,
        Conversation,
        ReleasePromotionAttempt,
        ActiveRetrievalTarget,
        RetrievalEmbedding,
        RetrievalIndexBuild,
        RetrievalSegment,
        VectorIndex,
        EmbeddingRun,
        EmbeddingProfile,
        EvaluationItem,
        EvaluationDataset,
        ReviewDecisionRecord,
        ReviewIssue,
        CandidateRevision,
        ExtractionCandidate,
        IngestionArtifact,
        SourcePage,
        TransactionalOutbox,
        IngestionTask,
        IngestionEvent,
        IngestionStep,
        IngestionRun,
        SourceUpload,
        LegalConceptAlias,
        LegalConcept,
        LegislativeEvent,
        ConstitutionalBill,
        AmendmentOperation,
        CorpusReleaseEntry,
        ProvisionVersion,
        Amendment,
        Provision,
        SourceDocument,
        CorpusRelease,
        LegalInstrument,
    ):
        session.exec(delete(model))
    session.exec(delete(RateLimitCounter))
    session.exec(delete(User))
    session.exec(update(GenerationCapacity).values(active_count=0))
    session.commit()
