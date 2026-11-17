import asyncio
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import health


@pytest.fixture(autouse=True)
def fresh_schema_cache() -> Iterator[None]:
    health.reset_schema_cache()
    yield
    health.reset_schema_cache()


@pytest.mark.parametrize("path", ["/livez", "/healthz"])
def test_liveness_does_no_io(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def no_database() -> str | None:
        raise AssertionError("liveness must not touch the database")

    monkeypatch.setattr(health, "readiness_failure", no_database)
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_readiness_checks_the_database_and_migration_head(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert health._SchemaState.at_head


def test_readiness_remembers_the_head_check(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/readyz").status_code == 200

    def heads_again() -> frozenset[str]:
        raise AssertionError("the head check is cached once seen")

    monkeypatch.setattr(health, "migration_heads", heads_again)
    assert client.get("/readyz").status_code == 200


def test_readiness_fails_while_migrations_are_pending(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "migration_heads", lambda: frozenset({"newer"}))
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "reason": "migrations_pending"}
    assert not health._SchemaState.at_head


def test_readiness_fails_when_the_database_is_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Unreachable:
        def connect(self) -> None:
            raise OperationalError("SELECT 1", {}, Exception("refused"))

    monkeypatch.setattr(health, "engine", Unreachable())
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "database_unavailable"


def test_readiness_times_out_quickly(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "READINESS_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(health, "readiness_failure", lambda: time.sleep(0.5))
    started = time.perf_counter()
    response = client.get("/readyz")
    assert time.perf_counter() - started < 0.4
    assert response.status_code == 503
    assert response.json()["reason"] == "database_timeout"


def test_migration_heads_match_the_shipped_revisions() -> None:
    heads = health.migration_heads()
    assert len(heads) == 1
    assert asyncio.run(asyncio.to_thread(health.readiness_failure)) is None


def test_probes_are_not_in_the_public_schema(client: TestClient) -> None:
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert not {"/livez", "/readyz", "/healthz"} & set(paths)
