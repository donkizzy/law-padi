from collections.abc import Generator
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, update

from app.core.config import settings
from app.core.db import engine, init_db
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
from app.main import app
from app.models import User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    database_name = urlsplit(str(settings.DATABASE_URL)).path.removeprefix("/")
    if not database_name.endswith("_test"):
        raise RuntimeError(
            "Refusing to run destructive tests against a non-test database. "
            "Set DATABASE_URL to a dedicated database whose name ends in '_test'."
        )
    with Session(engine) as session:
        init_db(session)
        _cleanup_db(session)
        init_db(session)
        yield session
        _cleanup_db(session)


def _cleanup_db(session: Session) -> None:
    session.rollback()
    # Published releases are intentionally immutable in application traffic.
    # Test teardown must first move them back to a draft state so the
    # immutability trigger does not turn cleanup into a failed test run.
    session.exec(update(CorpusRelease).values(status=CorpusReleaseStatus.BUILDING))
    session.commit()
    for model in (
        AuditEvent,
        AdminRoleAssignment,
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
    session.exec(delete(User))
    session.exec(update(GenerationCapacity).values(active_count=0))
    session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
