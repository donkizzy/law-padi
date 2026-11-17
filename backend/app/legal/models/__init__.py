"""Bounded-context definitions and complete import-time model registration."""

from app.legal.models.access import AdminRoleAssignment as AdminRoleAssignment
from app.legal.models.access import AuditEvent as AuditEvent
from app.legal.models.chat import Conversation as Conversation
from app.legal.models.chat import ConversationMessage as ConversationMessage
from app.legal.models.chat import MessageEvidence as MessageEvidence
from app.legal.models.chat import MessageFeedback as MessageFeedback
from app.legal.models.common import (
    RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH as RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH,
)
from app.legal.models.common import get_datetime_utc as get_datetime_utc
from app.legal.models.corpus import CorpusRelease as CorpusRelease
from app.legal.models.corpus import CorpusReleaseEntry as CorpusReleaseEntry
from app.legal.models.corpus import ReleasePromotionAttempt as ReleasePromotionAttempt
from app.legal.models.evaluation import EvaluationDataset as EvaluationDataset
from app.legal.models.evaluation import EvaluationItem as EvaluationItem
from app.legal.models.generation import GenerationAdmission as GenerationAdmission
from app.legal.models.generation import GenerationBudgetDay as GenerationBudgetDay
from app.legal.models.generation import GenerationBudgetMonth as GenerationBudgetMonth
from app.legal.models.generation import GenerationCapacity as GenerationCapacity
from app.legal.models.generation import GenerationEvent as GenerationEvent
from app.legal.models.generation import GenerationReservation as GenerationReservation
from app.legal.models.generation import GenerationRun as GenerationRun
from app.legal.models.ingestion import IdempotencyRecord as IdempotencyRecord
from app.legal.models.ingestion import IngestionArtifact as IngestionArtifact
from app.legal.models.ingestion import IngestionEvent as IngestionEvent
from app.legal.models.ingestion import IngestionRun as IngestionRun
from app.legal.models.ingestion import IngestionStep as IngestionStep
from app.legal.models.ingestion import IngestionTask as IngestionTask
from app.legal.models.ingestion import TransactionalOutbox as TransactionalOutbox
from app.legal.models.instruments import LegalConcept as LegalConcept
from app.legal.models.instruments import LegalConceptAlias as LegalConceptAlias
from app.legal.models.instruments import LegalInstrument as LegalInstrument
from app.legal.models.instruments import Provision as Provision
from app.legal.models.instruments import ProvisionVersion as ProvisionVersion
from app.legal.models.legislation import Amendment as Amendment
from app.legal.models.legislation import AmendmentOperation as AmendmentOperation
from app.legal.models.legislation import ConstitutionalBill as ConstitutionalBill
from app.legal.models.legislation import LegislativeEvent as LegislativeEvent
from app.legal.models.retrieval import ActiveRetrievalTarget as ActiveRetrievalTarget
from app.legal.models.retrieval import EmbeddingProfile as EmbeddingProfile
from app.legal.models.retrieval import EmbeddingRun as EmbeddingRun
from app.legal.models.retrieval import RetrievalEmbedding as RetrievalEmbedding
from app.legal.models.retrieval import RetrievalIndexBuild as RetrievalIndexBuild
from app.legal.models.retrieval import RetrievalSegment as RetrievalSegment
from app.legal.models.retrieval import VectorIndex as VectorIndex
from app.legal.models.review import CandidateRevision as CandidateRevision
from app.legal.models.review import ExtractionCandidate as ExtractionCandidate
from app.legal.models.review import ReviewDecisionRecord as ReviewDecisionRecord
from app.legal.models.review import ReviewIssue as ReviewIssue
from app.legal.models.sources import SourceDocument as SourceDocument
from app.legal.models.sources import SourcePage as SourcePage
from app.legal.models.sources import SourceUpload as SourceUpload
