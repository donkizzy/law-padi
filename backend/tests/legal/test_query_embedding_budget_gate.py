from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import search
from app.core.config import settings
from app.legal.evidence import (
    QUERY_EMBEDDING_ATTEMPTS,
    QUERY_EMBEDDING_TIMEOUT_SECONDS,
    default_embedding_provider,
)


@pytest.mark.usefixtures("corpus")
def test_disabled_query_embeddings_use_disclosed_keyword_and_topic_retrieval(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", False)
    monkeypatch.setattr(
        search,
        "_query_embedding_provider",
        lambda _: pytest.fail("Disabled paid query embedding provider must not run"),
    )
    for question in ("privacy", "Can police search my phone?"):
        response = client.post("/api/v1/legal/search", json={"query": question})
        assert response.status_code == 200
        body = response.json()
        assert body["retrieval_mode"] == "lexical"
        assert "keyword matches" in body["message"]
        assert any(row["citation"] == "Section 37" for row in body["data"])


def test_query_embeddings_give_up_quickly_for_a_waiting_reader() -> None:
    provider = default_embedding_provider(
        SimpleNamespace(
            provider="huggingface_tei",
            vector_dimensions=settings.RETRIEVAL_VECTOR_DIMENSIONS,
            model_name="BAAI/bge-m3",
            model_revision="test",
        )
    )

    assert provider.max_attempts == QUERY_EMBEDDING_ATTEMPTS == 2
    assert provider.client.timeout.read == QUERY_EMBEDDING_TIMEOUT_SECONDS == 8
