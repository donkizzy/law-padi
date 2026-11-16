from dataclasses import replace
from datetime import date
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import search
from app.core.config import settings
from app.core.db import init_db
from app.ingestion.embedding import EmbeddingBatch, EmbeddingProviderUnavailable
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
)
from app.legal import public_corpus
from app.legal.enums import (
    CorpusReleaseStatus,
    VectorIndexStatus,
)
from app.legal.evidence import clear_query_vector_cache, evidence_item
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    ProvisionVersion,
    RetrievalIndexBuild,
)
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import load_public_corpus, load_ranked_corpus
from tests.db import reset_database


@pytest.mark.usefixtures("corpus")
def test_exact_lookup_uses_canonical_hierarchy_without_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        search,
        "_query_embedding_provider",
        lambda _: pytest.fail("Exact lookup must not embed"),
    )
    response = client.post(
        "/api/v1/legal/search", json={"query": "What does §33(2)(a) say?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "exact"
    result = body["data"][0]
    assert result["citation"] == "Section 33(2)(a)"
    assert (
        result["authoritative_text"]
        == "(a) Defence of any person from unlawful violence."
    )
    assert result["legal_status"] == "historical"
    assert result["ancestors"][-1]["citation"] == "Section 33(2)"
    assert result["edition_label"].endswith("(LFN 2004)")
    detail = client.get(f"/api/v1/legal/provisions/{result['canonical_path']}").json()[
        "data"
    ][0]
    assert detail["ancestors"][-1]["authoritative_text"].startswith(
        "(2) Lawful exceptions"
    )


@pytest.mark.usefixtures("corpus")
def test_duplicate_missing_and_unsupported_references(client: TestClient) -> None:
    ambiguous = client.post(
        "/api/v1/legal/search", json={"query": "Section 189"}
    ).json()
    assert ambiguous["outcome"] == "ambiguous"
    assert len(ambiguous["data"]) == 2
    assert (
        ambiguous["data"][0]["source_page_start"]
        != ambiguous["data"][1]["source_page_start"]
    )
    assert (
        client.post("/api/v1/legal/search", json={"query": "Section 168"}).json()[
            "outcome"
        ]
        == "not_found"
    )
    assert (
        client.post(
            "/api/v1/legal/search", json={"query": "Section 33(2)(a)(i)"}
        ).json()["outcome"]
        == "unsupported_reference"
    )
    assert client.post("/api/v1/legal/search", json={"query": "   "}).status_code == 422


def test_citation_lookup_preserves_outcomes_and_deduplicates_evidence(
    client: TestClient, corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, _source, _nodes, _pdf = corpus
    monkeypatch.setattr(
        search,
        "_query_embedding_provider",
        lambda _: pytest.fail("Exact lookup must not embed"),
    )
    response = client.get(
        "/api/v1/legal/provisions/by-citation",
        params={
            "citation": "Sections 33, 37, 168, 189 and 33",
            "release_version": release.version,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "partial"
    assert [row["status"] for row in body["citation_outcomes"]] == [
        "resolved",
        "resolved",
        "missing",
        "ambiguous",
        "resolved",
    ]
    assert (
        body["citation_outcomes"][0]["evidence_ids"]
        == body["citation_outcomes"][4]["evidence_ids"]
    )
    assert body["count"] == 4
    assert all(row["release_version"] == release.version for row in body["data"])
    assert body["evidence"] == []
    assert (
        client.get(
            "/api/v1/legal/provisions/by-citation",
            params={"citation": "Section 33 of Evidence Act"},
        ).json()["citation_outcomes"][0]["status"]
        == "unsupported"
    )


def test_evidence_rejects_a_canonical_version_with_a_bad_stored_hash(
    corpus, db: Session
) -> None:
    release, _source, nodes, _pdf = corpus
    version = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == nodes["chapter4.section37"].id
        )
    ).one()
    version.text_sha256 = "0" * 64
    db.add(version)
    db.commit()
    focused = load_ranked_corpus(db, release, [version.id])
    with pytest.raises(PgVectorRetrievalError, match="legal text hash"):
        evidence_item(focused, focused.result(nodes["chapter4.section37"]), "E1")


def test_tree_history_and_source_are_published_and_release_scoped(
    client: TestClient, corpus, db: Session
) -> None:
    release, source, nodes, pdf = corpus
    tree = client.get("/api/v1/legal/provisions/tree").json()
    assert [node["kind"] for node in tree["data"]] == ["chapter", "chapter"]
    children = client.get(
        "/api/v1/legal/provisions/tree",
        params={"parent_path": nodes["chapter4.section33.subsection2"].canonical_path},
    ).json()
    assert [node["citation"] for node in children["data"]] == [
        "Section 33(2)(a)",
        "Section 33(2)(b)",
    ]
    history = client.get(
        "/api/v1/legal/provision-history",
        params={"canonical_path": nodes["chapter4.section37"].canonical_path},
    ).json()
    assert history["count"] == 1
    assert (
        history["message"]
        == "This is the only version of this section available so far."
    )
    content = client.get(f"/api/v1/legal/sources/{source.id}/content")
    assert content.status_code == 200 and content.content == pdf
    assert client.get(f"/api/v1/legal/sources/{uuid4()}/content").status_code == 404
    with patch("app.api.routes.search.get_blob_store") as store:
        store.return_value.head.side_effect = httpx.ReadTimeout("slow storage")
        unavailable = client.get(f"/api/v1/legal/sources/{source.id}/content")
    assert unavailable.status_code == 503
    draft = CorpusRelease(version="private-draft")
    db.add(draft)
    db.commit()
    assert (
        client.get(
            f"/api/v1/legal/provisions/{nodes['chapter4.section37'].canonical_path}",
            params={"release_version": draft.version},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/legal/sources/{source.id}/content",
            params={"release_version": draft.version},
        ).status_code
        == 404
    )
    # A previously published edition remains addressable after the active pointer is removed.
    release.status = CorpusReleaseStatus.RETIRED
    db.add(release)
    db.commit()
    assert client.get("/api/v1/legal/releases/current").status_code == 503
    pinned = client.get(
        f"/api/v1/legal/provisions/{nodes['chapter4.section37'].canonical_path}",
        params={"release_version": release.version},
    )
    assert pinned.status_code == 200


@pytest.mark.usefixtures("corpus")
def test_public_routes_share_one_corpus_load(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    loads: list[str] = []

    def counted(session, release, *, index_kind="enacted"):
        loads.append(release.version)
        return load_public_corpus(session, release, index_kind=index_kind)

    monkeypatch.setattr(public_corpus, "load_public_corpus", counted)
    for _ in range(2):
        assert client.get("/api/v1/legal/releases/current").status_code == 200
        assert client.get("/api/v1/legal/instruments").status_code == 200
        assert client.get("/api/v1/legal/provisions/tree").status_code == 200
    assert len(loads) == 1


def test_shared_corpus_keeps_lookups_and_stays_unfiltered(corpus, db: Session) -> None:
    release, _, nodes, _ = corpus
    first = public_corpus.cached_public_corpus(db, release)
    second = public_corpus.cached_public_corpus(db, release)
    assert first is not second
    assert first._by_parent is second._by_parent
    assert first.provision_at("absent") is None
    section = nodes["chapter4.section33"]
    found = first.provision_at(section.canonical_path)
    assert found is not None and found.id == section.id
    assert [p.id for p in first.children(section.id)] == [
        p.id
        for p in sorted(
            first.provisions.values(), key=lambda p: (p.sort_key, p.canonical_path)
        )
        if p.parent_id == section.id
    ]


def test_search_omits_evidence_but_keeps_children(client: TestClient, corpus) -> None:
    _, _, nodes, _ = corpus
    body = client.post("/api/v1/legal/search", json={"query": "Section 33"}).json()
    assert body["evidence"] == []
    assert (
        body["data"][0]["canonical_path"] == nodes["chapter4.section33"].canonical_path
    )
    assert body["data"][0]["children"]


def test_expired_corpus_shows_corrected_source_title(
    client: TestClient, corpus, db: Session
) -> None:
    _, source, nodes, _ = corpus
    path = f"/api/v1/legal/provisions/{nodes['chapter4.section37'].canonical_path}"
    assert client.get(path).json()["data"][0]["source_title"] == source.title
    source.title = "Corrected title"
    db.add(source)
    db.commit()
    assert client.get(path).json()["data"][0]["source_title"] != "Corrected title"
    for key, entry in public_corpus._corpus_cache.items():
        public_corpus._corpus_cache[key] = replace(entry, expires_at=0)
    assert client.get(path).json()["data"][0]["source_title"] == "Corrected title"


def test_cached_corpus_does_not_outlive_publication(
    client: TestClient, corpus, db: Session
) -> None:
    release, _, nodes, _ = corpus
    path = f"/api/v1/legal/provisions/{nodes['chapter4.section37'].canonical_path}"
    assert client.get(path).status_code == 200
    release.status = CorpusReleaseStatus.RETIRED
    db.add(release)
    db.commit()
    assert client.get("/api/v1/legal/releases/current").status_code == 503
    assert client.get(path).status_code == 503


def test_cache_keeps_only_the_newest_releases(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_ids = [uuid4(), uuid4(), uuid4()]
    monkeypatch.setattr(
        public_corpus,
        "load_public_corpus",
        lambda _session, item, **_kwargs: public_corpus.PublicCorpus(item, {}, {}, {}),
    )
    for release_id in release_ids:
        public_corpus.cached_public_corpus(
            db, CorpusRelease(id=release_id, version="x")
        )
    assert [key[0] for key in public_corpus._corpus_cache] == release_ids[1:]


def test_history_lists_each_version_without_loading_whole_releases(
    client: TestClient, corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, source, nodes, _ = corpus
    provision = nodes["chapter4.section37"]
    current = db.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == provision.id)
    ).one()
    text = "Earlier wording of section 37."
    earlier = ProvisionVersion(
        provision_id=provision.id,
        source_document_id=source.id,
        text=text,
        normalized_text=text,
        text_sha256=legal_text_sha256(text),
        legal_status=current.legal_status,
        valid_from=date(1979, 1, 1),
        valid_until=current.valid_from,
        revision_number=current.revision_number + 1,
    )
    retired = CorpusRelease(version="earlier", status=CorpusReleaseStatus.RETIRED)
    db.add_all([earlier, retired])
    db.flush()
    db.add(
        CorpusReleaseEntry(
            release_id=retired.id,
            provision_version_id=earlier.id,
            source_document_id=source.id,
        )
    )
    db.commit()
    public = public_corpus.cached_public_corpus
    calls: list[str] = []

    def counted(session, item, *, index_kind="enacted"):
        calls.append(item.version)
        return public(session, item, index_kind=index_kind)

    monkeypatch.setattr(search, "cached_public_corpus", counted)
    history = client.get(
        "/api/v1/legal/provision-history",
        params={"canonical_path": provision.canonical_path},
    ).json()
    assert calls == [release.version]
    assert history["count"] == 2
    assert {row["release_version"] for row in history["data"]} == {
        release.version,
        "earlier",
    }


@pytest.mark.usefixtures("corpus")
def test_semantic_and_fallback_results_are_unique_and_canonical(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        search,
        "cached_public_corpus",
        lambda *_args, **_kwargs: pytest.fail(
            "Semantic lookup must use targeted canonical reads"
        ),
    )

    class Provider:
        def embed(self, texts):
            assert texts == ["privacy"]
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023],
            )

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: Provider())
    result = client.post(
        "/api/v1/legal/search", json={"query": "privacy", "top_k": 4}
    ).json()
    assert result["retrieval_mode"] == "hybrid"
    assert result["count"] == 4
    assert len({row["provision_version_id"] for row in result["data"]}) == 4
    privacy = next(row for row in result["data"] if row["citation"] == "Section 37")
    assert privacy["authoritative_text"].endswith(
        "Privacy of correspondence is protected."
    )

    class Unavailable:
        def embed(self, _texts):
            raise EmbeddingProviderUnavailable("provider failed")

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: Unavailable())
    # A vector this process already holds needs no provider; forget it.
    clear_query_vector_cache()
    fallback = client.post("/api/v1/legal/search", json={"query": "privacy"}).json()
    assert fallback["retrieval_mode"] == "lexical"
    assert fallback["count"] == 1
    assert "keyword matches" in fallback["message"]

    # Everyday wording reaches the right section through the topic guide,
    # in both keyword-only and hybrid modes.
    topical = client.post(
        "/api/v1/legal/search", json={"query": "Can police search my phone?"}
    ).json()
    assert topical["retrieval_mode"] == "lexical"
    assert topical["data"][0]["citation"] == "Section 37"
    assert topical["data"][0]["title"] == "Right to private and family life"

    class AnyQuery:
        def embed(self, _texts):
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023],
            )

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: AnyQuery())
    topical = client.post(
        "/api/v1/legal/search", json={"query": "Can police search my phone?"}
    ).json()
    assert topical["retrieval_mode"] == "hybrid"
    assert topical["data"][0]["citation"] == "Section 37"


def test_missing_target_and_database_failure_have_unavailable_state(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    reset_database(db)
    init_db(db)
    assert client.get("/api/v1/legal/releases/current").status_code == 503
    from sqlalchemy.exc import OperationalError

    def unavailable(*_args, **_kwargs):
        raise OperationalError("query", {}, Exception("private connection detail"))

    monkeypatch.setattr(search, "_corpus", unavailable)
    response = client.get("/api/v1/legal/releases/current")
    assert response.status_code == 503
    assert response.json()["detail"] == "Legal corpus database is unavailable"


def test_full_public_index_is_release_scoped_and_contains_hub_metadata(
    client: TestClient, corpus, db: Session
) -> None:
    release, _source, nodes, _pdf = corpus
    index = client.get("/api/v1/legal/provisions/tree", params={"all_nodes": True})
    assert index.status_code == 200
    body = index.json()
    assert body["scope"] == "all"
    assert body["release_version"] == release.version
    assert {item["canonical_path"] for item in body["data"]} == {
        node.canonical_path for node in nodes.values()
    }
    # Discovery must not publish document text or unpublished releases.
    assert all(item["authoritative_text"] is None for item in body["data"])
    parent_path = nodes["chapter4"].canonical_path
    hub = client.get(
        "/api/v1/legal/provisions/tree", params={"parent_path": parent_path}
    ).json()
    assert hub["parent"]["canonical_path"] == parent_path
    assert hub["scope"] == "children"
    assert (
        client.get(
            "/api/v1/legal/provisions/tree",
            params={"parent_path": parent_path, "all_nodes": True},
        ).status_code
        == 422
    )
    draft = CorpusRelease(version="private-discovery-draft")
    db.add(draft)
    db.commit()
    assert (
        client.get(
            "/api/v1/legal/provisions/tree",
            params={"release_version": draft.version, "all_nodes": True},
        ).status_code
        == 404
    )


@pytest.mark.usefixtures("corpus")
@pytest.mark.parametrize("query", ["zxqvplm nonsense xyz", "Who won the World Cup?"])
def test_dense_neighbours_without_a_direct_match_are_disclosed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:

    class Provider:
        def embed(self, texts):
            assert texts == [query]
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023],
            )

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: Provider())
    body = client.post("/api/v1/legal/search", json={"query": query}).json()
    assert body[
        "data"
    ]  # Nearest neighbours remain inspectable, not certified relevant.
    assert body["message_code"] == "not_covered"
    assert "don't seem to answer" in body["message"]


@pytest.mark.usefixtures("corpus")
def test_curated_topic_does_not_receive_an_unrelated_query_warning(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:

    class Provider:
        def embed(self, _texts):
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023],
            )

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: Provider())
    body = client.post("/api/v1/legal/search", json={"query": "privacy"}).json()
    assert body["message_code"] != "not_covered"


@pytest.mark.parametrize(
    "release_status", [CorpusReleaseStatus.PRODUCTION, CorpusReleaseStatus.RETIRED]
)
def test_pinned_semantic_search_accepts_a_promoted_published_build(
    client: TestClient,
    db: Session,
    corpus,
    monkeypatch: pytest.MonkeyPatch,
    release_status: CorpusReleaseStatus,
) -> None:
    release, *_ = corpus
    release.status = release_status
    build = db.exec(
        select(RetrievalIndexBuild).where(RetrievalIndexBuild.release_id == release.id)
    ).one()
    build.status = VectorIndexStatus.PROMOTED
    db.add(release)
    db.add(build)
    db.commit()

    class Provider:
        def embed(self, _texts):
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023],
            )

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: Provider())
    response = client.post(
        "/api/v1/legal/search",
        json={"query": "privacy", "release_version": release.version},
    )
    assert response.status_code == 200, response.text
    assert response.json()["release_version"] == release.version
    assert response.json()["data"][0]["canonical_path"].endswith("section37")


def test_failed_pinned_index_is_not_mistaken_for_a_promoted_build(
    client: TestClient, db: Session, corpus
) -> None:
    release, *_ = corpus
    build = db.exec(
        select(RetrievalIndexBuild).where(RetrievalIndexBuild.release_id == release.id)
    ).one()
    build.status = VectorIndexStatus.FAILED
    db.add(build)
    db.commit()
    response = client.post(
        "/api/v1/legal/search",
        json={"query": "privacy", "release_version": release.version},
    )
    assert response.status_code == 503


@pytest.mark.usefixtures("corpus")
def test_query_vectors_are_reused_and_paid_calls_are_capped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    class Provider:
        def embed(self, texts):
            calls.extend(texts)
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023],
            )

    monkeypatch.setattr(search, "_query_embedding_provider", lambda _: Provider())
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "QUERY_EMBEDDING_DAILY_LIMIT", 1)
    modes = [
        client.post("/api/v1/legal/search", json={"query": query}).json()[
            "retrieval_mode"
        ]
        for query in ("privacy", "privacy", "liberty")
    ]
    # The repeat is served from memory; the new query is over the daily cap
    # and falls back to keyword ranking instead of another paid call.
    assert modes == ["hybrid", "hybrid", "lexical"]
    assert calls == ["privacy"]
