"""Public law selection must follow the selected published release."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.legal.enums import CorpusReleaseStatus, InstrumentType
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
)


def test_only_published_instruments_are_listed(
    client: TestClient, db: Session, statute_corpus
) -> None:
    db.add(
        LegalInstrument(
            slug="unpublished-act",
            title="Unpublished Act",
            instrument_type=InstrumentType.ACT,
        )
    )
    db.commit()
    response = client.get("/api/v1/legal/instruments")
    assert response.status_code == 200
    body = response.json()
    assert body["release_version"] == statute_corpus.version
    assert body["count"] == 3
    assert [item["slug"] for item in body["data"]] == [
        "constitution-1999",
        "acja-2015",
        "police-act-2020",
    ]
    assert body["data"][0]["section_count"] == 4
    assert body["data"][1]["section_count"] == 17
    assert body["data"][1]["edition_note"] == "As enacted, may have been amended."


def test_instrument_list_is_pinned_to_a_retired_release(
    client: TestClient, db: Session, statute_corpus
) -> None:
    old = CorpusRelease(version="retired-constitution-only")
    db.add(old)
    db.flush()
    rows = db.exec(
        select(CorpusReleaseEntry)
        .join(
            ProvisionVersion,
            CorpusReleaseEntry.provision_version_id == ProvisionVersion.id,
        )
        .join(Provision, ProvisionVersion.provision_id == Provision.id)
        .where(
            CorpusReleaseEntry.release_id == statute_corpus.id,
            Provision.canonical_path.startswith("constitution-1999."),
        )
    ).all()
    for entry in rows:
        db.add(
            CorpusReleaseEntry(
                release_id=old.id,
                provision_version_id=entry.provision_version_id,
                source_document_id=entry.source_document_id,
            )
        )
    db.flush()
    old.status = CorpusReleaseStatus.RETIRED
    db.add(old)
    db.commit()
    body = client.get(
        "/api/v1/legal/instruments", params={"release_version": old.version}
    ).json()
    assert [item["slug"] for item in body["data"]] == ["constitution-1999"]
    draft = CorpusRelease(version="unpublished-edition")
    db.add(draft)
    db.commit()
    assert (
        client.get(
            "/api/v1/legal/instruments", params={"release_version": draft.version}
        ).status_code
        == 404
    )


def test_tree_filters_roots_full_index_and_parent_by_instrument(
    client: TestClient, statute_corpus
) -> None:
    assert statute_corpus
    for slug in ("constitution-1999", "acja-2015", "police-act-2020"):
        body = client.get(
            "/api/v1/legal/provisions/tree",
            params={"instrument": slug, "all_nodes": True},
        ).json()
        assert body["instrument_slug"] == slug
        assert body["data"]
        assert all(
            item["canonical_path"].startswith(slug + ".") for item in body["data"]
        )
    mismatch = client.get(
        "/api/v1/legal/provisions/tree",
        params={"instrument": "acja-2015", "parent_path": "constitution-1999.chapter4"},
    )
    assert mismatch.status_code == 404
    assert (
        client.get(
            "/api/v1/legal/provisions/tree", params={"instrument": "unpublished-act"}
        ).status_code
        == 404
    )
    legacy = client.get("/api/v1/legal/provisions/tree").json()
    assert all(
        item["canonical_path"].startswith("constitution-1999.")
        for item in legacy["data"]
    )


def test_picker_default_and_explicit_reference_scope(
    client: TestClient, statute_corpus
) -> None:
    assert statute_corpus
    body = client.post(
        "/api/v1/legal/search", json={"query": "Section 9", "instrument": "acja-2015"}
    ).json()
    assert body["data"][0]["canonical_path"] == "acja-2015.section9"
    explicit = client.post(
        "/api/v1/legal/search",
        json={"query": "Police Act s.49", "instrument": "acja-2015"},
    ).json()
    assert explicit["data"][0]["canonical_path"] == "police-act-2020.section49"
    assert (
        client.post(
            "/api/v1/legal/search",
            json={"query": "Section 9", "instrument": "unpublished-act"},
        ).status_code
        == 404
    )


def test_semantic_picker_filters_fallback_before_ranking(
    client: TestClient, statute_corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert statute_corpus
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", False)
    body = client.post(
        "/api/v1/legal/search",
        json={
            "query": "suspect",
            "mode": "semantic",
            "instrument": "acja-2015",
            "top_k": 10,
        },
    ).json()
    assert body["retrieval_mode"] == "lexical"
    assert len(body["data"]) > 3
    assert all(item["instrument_slug"] == "acja-2015" for item in body["data"])


def test_dense_picker_filters_candidates_before_limit(
    db: Session, statute_corpus
) -> None:
    from app.ingestion.pgvector_repository import (
        active_target,
        dense_search,
        hybrid_search,
        write_embeddings,
    )
    from app.legal.models import EmbeddingProfile, EmbeddingRun, RetrievalSegment

    target = active_target(db)
    run = db.get(EmbeddingRun, target.embedding_run_id)
    profile = db.get(EmbeddingProfile, target.profile_id)
    assert run and profile
    segments = db.exec(
        select(RetrievalSegment).where(
            RetrievalSegment.release_id == statute_corpus.id,
            RetrievalSegment.canonical_path.startswith("acja-2015."),
        )
    ).all()
    vector = [1.0] + [0.0] * 1023
    statute_corpus.status = CorpusReleaseStatus.BUILDING
    db.add(statute_corpus)
    db.commit()
    write_embeddings(
        db,
        release_id=statute_corpus.id,
        embedding_run=run,
        profile=profile,
        segments=segments,
        vectors=[vector] * len(segments),
    )
    statute_corpus.status = CorpusReleaseStatus.PRODUCTION
    db.add(statute_corpus)
    db.commit()
    dense = dense_search(
        db,
        release_id=statute_corpus.id,
        embedding_run_id=run.id,
        query_vector=vector,
        instrument_slug="acja-2015",
        limit=1,
    )
    assert len(dense) == 1
    assert dense[0][0].canonical_path.startswith("acja-2015.")
    ranked = hybrid_search(
        db,
        release_id=statute_corpus.id,
        embedding_run_id=run.id,
        query_vector=vector,
        query="suspect",
        top_k=6,
        instrument_slug="acja-2015",
    )
    assert len(ranked) == 6
    assert all(row.segment.canonical_path.startswith("acja-2015.") for row in ranked)


def test_invalid_law_slug_is_rejected(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/legal/search", json={"query": "Section 9", "instrument": "../acja"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/legal/provisions/tree", params={"instrument": "../acja"}
        ).status_code
        == 422
    )
