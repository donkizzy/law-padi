from collections.abc import Generator
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine, init_db
from app.legal.public_corpus import clear_public_corpus_cache
from app.main import app
from tests.db import reset_database
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
        reset_database(session)
        init_db(session)
        yield session
        reset_database(session)


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limits() -> Generator[None]:
    """Tests sign in far more often than people do; rate-limit tests opt back in."""
    with patch.object(settings, "RATE_LIMIT_ENABLED", False):
        yield


@pytest.fixture(scope="session", autouse=True)
def disable_guest_network_limits() -> Generator[None]:
    """Every test client shares one address; network-limit tests opt back in."""
    with patch.multiple(
        settings, CHAT_GUEST_IP_DAILY_LIMIT=10_000, CHAT_GUEST_IP_BURST_LIMIT=10_000
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def local_storage_only() -> Generator[None]:
    """A developer's .env may point at a real bucket; R2 tests supply their own."""
    with patch.multiple(
        settings,
        INGESTION_STORAGE_BACKEND="local",
        R2_ENDPOINT_URL=None,
        R2_BUCKET_NAME=None,
        R2_ACCESS_KEY_ID=None,
        R2_SECRET_ACCESS_KEY=None,
    ):
        yield


@pytest.fixture(autouse=True)
def fresh_public_corpus() -> Generator[None]:
    """Fixtures rebuild releases in place, so no corpus outlives a test."""
    clear_public_corpus_cache()
    yield
    clear_public_corpus_cache()


@pytest.fixture(autouse=True)
def no_live_search_translation() -> Generator[None]:
    """Search never calls a real provider; tests opt in with a fake."""
    from app.chat import search_language
    from app.legal.evidence import clear_query_vector_cache

    search_language.clear_cache()
    clear_query_vector_cache()
    with patch.object(settings, "DEEPSEEK_API_KEY", None):
        yield
    search_language.clear_cache()
    clear_query_vector_cache()


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


pytest_plugins = [
    "tests.fixtures.corpus",
    "tests.fixtures.statute_corpus",
    "tests.fixtures.conversations",
]

# Compatibility for test modules that still import the original reset name.
_cleanup_db = reset_database
