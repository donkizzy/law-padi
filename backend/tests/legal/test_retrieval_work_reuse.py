from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.routes import search
from app.chat import pipeline, preparation
from app.core.config import settings
from app.ingestion.embedding import EmbeddingBatch
from app.legal import evidence, release_scope, topics


class QueryEmbedding:
    def embed(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            provider="test",
            model_name="test",
            model_revision=None,
            vectors=[[1.0] + [0.0] * 1023 for _ in texts],
        )


@pytest.mark.parametrize("hybrid", [False, True])
@pytest.mark.usefixtures("corpus")
def test_search_loads_scope_and_analyzes_topics_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, hybrid: bool
) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", hybrid)
    monkeypatch.setattr(evidence, "_paid_query_embedding_allowed", lambda: True)
    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: QueryEmbedding())
    topics._analyze_topics.cache_clear()
    with (
        patch.object(
            release_scope,
            "_load_release_instruments",
            wraps=release_scope._load_release_instruments,
        ) as load_scope,
        patch.object(
            topics, "_topic_sections", wraps=topics._topic_sections
        ) as sections,
    ):
        response = client.post(
            "/api/v1/legal/search", json={"query": "Can police search my phone?"}
        )
    assert response.status_code == 200
    assert response.json()["retrieval_mode"] == ("hybrid" if hybrid else "lexical")
    assert load_scope.call_count == 1
    assert sections.call_count == 1


@pytest.mark.parametrize("question", ["Section 37", "Can police search my phone?"])
@pytest.mark.usefixtures("corpus")
def test_chat_reuses_scope_through_lookup_context_and_packet(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, question: str
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", True)
    monkeypatch.setattr(evidence, "_paid_query_embedding_allowed", lambda: True)
    monkeypatch.setattr(
        preparation, "default_embedding_provider", lambda _: QueryEmbedding()
    )
    conversation = client.post("/api/v1/conversations", json={}).json()
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"question": question, "idempotency_key": "scope-reuse"},
    )
    assert response.status_code == 202
    with patch.object(
        release_scope,
        "_load_release_instruments",
        wraps=release_scope._load_release_instruments,
    ) as load_scope:
        prepared = pipeline.prepare_run(UUID(response.json()["run_id"]))
    assert prepared.selected
    assert prepared.covered_laws
    assert load_scope.call_count == 1


def test_scope_cache_ends_with_operation_and_separates_index_kinds(db: Session) -> None:
    from uuid import uuid4

    identity = uuid4()
    with patch.object(
        release_scope, "_load_release_instruments", return_value={}
    ) as load:
        with pytest.raises(ValueError), release_scope.release_scope_cache(db):
            release_scope.release_instruments(db, identity)
            with release_scope.release_scope_cache(db):
                release_scope.release_instruments(db, identity)
                release_scope.release_instruments(db, identity, index_kind="proposals")
            assert load.call_count == 2
            raise ValueError("retrieval failed")
        assert "retrieval_release_scope" not in db.info
        release_scope.release_instruments(db, identity)
        assert load.call_count == 3


def test_topic_helpers_share_analysis_without_sharing_mutable_results() -> None:
    query = "Can police search my phone?"
    topics._analyze_topics.cache_clear()
    topics._match_topics.cache_clear()
    with patch.object(topics, "match_topics", wraps=topics.match_topics) as matches:
        original = topics.topic_sections(query)
        topics.demoted_sections(query)
        topics.rights_question(query)
        topics.related_laws(query)
        topics.topic_sections(query).clear()
        assert topics.topic_sections(query) == original
    assert matches.call_count == 2  # One window for the Constitution and one for Acts.
    assert topics._match_topics.cache_info().misses == 2
