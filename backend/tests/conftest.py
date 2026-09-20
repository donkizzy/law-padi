from collections.abc import Generator

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
        MessageEvidence,
        ConversationMessage,
        Conversation,
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
