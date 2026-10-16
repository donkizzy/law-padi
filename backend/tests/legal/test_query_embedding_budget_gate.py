import pytest
from fastapi.testclient import TestClient

from app.api.routes import search
from app.core.config import settings

pytest_plugins = ["tests.api.routes.test_legal_search"]


def test_disabled_query_embeddings_use_disclosed_keyword_and_topic_retrieval(
    client: TestClient, corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
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
