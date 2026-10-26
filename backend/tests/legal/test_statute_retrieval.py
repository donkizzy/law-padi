"""Synthetic mixed releases exercise routing without approving any real Act."""

import hashlib
import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.chat.worker import _relative_query, _source_crossrefs
from app.ingestion.pgvector_repository import (
    fuse_rankings,
    topic_search,
    write_segments,
)
from app.ingestion.retrieval import build_retrieval_documents
from app.legal.enums import (
    CorpusReleaseStatus,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
)
from app.legal.models import (
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import load_public_corpus
from app.legal.references import SectionReference
from app.legal.release_scope import release_instruments
from app.legal.titles import catalogue_titles
from app.legal.topics import demoted_sections, rights_question, section_target

pytest_plugins = ["tests.api.routes.test_legal_search"]
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def statute_texts() -> dict[str, str]:
    return {}


@pytest.fixture
def statute_corpus(db: Session, corpus, statute_texts: dict[str, str]):
    release, source, _nodes, _pdf = corpus
    release.status = CorpusReleaseStatus.BUILDING
    db.add(release)
    db.commit()
    db.refresh(source)
    instruments, provisions, versions, entries = {}, {}, {}, []
    for slug, label in (
        ("acja-2015", "ACJA 2015"),
        ("police-act-2020", "Police Act 2020"),
    ):
        instrument = LegalInstrument(
            slug=slug,
            title=label,
            short_title=label,
            instrument_type=InstrumentType.ACT,
        )
        db.add(instrument)
        db.flush()
        instruments[instrument.id] = instrument
        document = SourceDocument.model_validate(
            {
                **source.model_dump(),
                "id": uuid4(),
                "legal_instrument_id": instrument.id,
                "title": f"Synthetic {label}",
                "sha256": hashlib.sha256(slug.encode()).hexdigest(),
            }
        )
        db.add(document)
        db.flush()
        for number, title in catalogue_titles(slug, "sections").items():
            provision = Provision(
                instrument_id=instrument.id,
                kind=ProvisionKind.SECTION,
                number=number,
                heading=title,
                canonical_path=f"{slug}.section{number}",
                sort_key=number.zfill(3),
            )
            db.add(provision)
            db.flush()
            text = statute_texts.get(
                f"{slug}:{number}", f"Synthetic test wording: {title}."
            )
            version = ProvisionVersion(
                provision_id=provision.id,
                source_document_id=document.id,
                text=text,
                normalized_text=text.lower(),
                text_sha256=legal_text_sha256(text),
                valid_from=date(2020, 1, 1),
                legal_status=LegalStatus.HISTORICAL,
            )
            db.add(version)
            db.flush()
            entry = CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=document.id,
            )
            db.add(entry)
            entries.append(entry)
            versions[version.id] = version
            provisions[provision.id] = provision
    db.flush()
    documents = build_retrieval_documents(
        release_version=release.version,
        entries=entries,
        versions_by_id=versions,
        provisions_by_id=provisions,
        instruments_by_id=instruments,
    )
    write_segments(db, release_id=release.id, documents=documents)
    release.status = CorpusReleaseStatus.PRODUCTION
    db.add(release)
    db.commit()
    return release


@pytest.mark.parametrize(
    "query,path",
    [
        ("ACJA s.9", "acja-2015.section9"),
        (
            "Section 9 of the Administration of Criminal Justice Act",
            "acja-2015.section9",
        ),
        ("s.49 Police Act", "police-act-2020.section49"),
        ("Nigeria Police Act 2020 section 35", "police-act-2020.section35"),
        ("Section 37", "constitution-1999.chapter4.section37"),
    ],
)
def test_public_exact_lookup_preserves_law_identity(
    client: TestClient, statute_corpus, query: str, path: str
) -> None:
    assert statute_corpus
    response = client.post("/api/v1/legal/search", json={"query": query})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "exact"
    assert body["data"][0]["canonical_path"] == path
    assert body["evidence"][0]["instrument_slug"] == path.partition(".")[0]


def test_recognised_act_absent_from_release_is_not_a_constitution_lookup(
    client: TestClient, corpus
) -> None:
    assert corpus
    body = client.post("/api/v1/legal/search", json={"query": "ACJA s.37"}).json()
    assert body["outcome"] == "not_found"
    assert body["data"] == []
    assert "ACJA 2015 isn't included" in body["message"]
    assert body["citation_outcomes"][0]["reference"] == "Section 37, ACJA 2015"


def test_present_act_missing_number_is_reported_separately(
    client: TestClient, statute_corpus
) -> None:
    assert statute_corpus
    body = client.post("/api/v1/legal/search", json={"query": "ACJA s.400"}).json()
    assert body["outcome"] == "not_found"
    assert "This section isn't in this edition of ACJA 2015" in body["message"]


def test_rights_search_keeps_constitution_first_and_includes_act_detail(
    db: Session, statute_corpus
) -> None:
    question = "Can police search my house?"
    topics = topic_search(db, release_id=statute_corpus.id, query=question)
    ranked = fuse_rankings(
        topics=topics,
        top_k=6,
        prefer_constitution=rights_question(question),
        demoted=demoted_sections(question),
        balance_instruments=True,
    )
    targets = [section_target(item.segment.canonical_path) for item in ranked]
    assert targets[0] == "constitution-1999:37"
    assert any(
        target and target.startswith(("acja-2015:", "police-act-2020:"))
        for target in targets[1:]
    )


@pytest.mark.parametrize("split", ["benchmark", "heldout"])
def test_provisional_statute_cases_route_through_synthetic_release(
    db: Session, statute_corpus, split: str
) -> None:
    dataset = json.loads(
        (ROOT / "docs" / f"statute-retrieval-{split}-v1.json").read_text()
    )
    for case in dataset["cases"]:
        rows = topic_search(db, release_id=statute_corpus.id, query=case["query"])
        ranked = fuse_rankings(topics=rows, top_k=6)
        targets = {section_target(item.segment.canonical_path) for item in ranked}
        assert targets & set(case["expected_sections"]), case["id"]
    assert {i.slug for i in release_instruments(db, statute_corpus.id).values()} == {
        "constitution-1999",
        "acja-2015",
        "police-act-2020",
    }


def test_internal_reference_explicit_law_wins_over_source_default() -> None:
    assert _source_crossrefs(
        "Subject to section 35 of the Constitution.", "acja-2015"
    ) == [SectionReference("35")]
    assert _source_crossrefs("See section 49 of the Police Act.", "acja-2015") == [
        SectionReference("49", instrument_slug="police-act-2020")
    ]


def test_relative_subsection_retains_act_and_same_number_laws_are_ambiguous(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.chat.worker._prior_citations", lambda *_: ["Section 9, ACJA 2015"]
    )
    assert (
        _relative_query(db, uuid4(), "What about subsection 2?")
        == "Section 9(2), ACJA 2015"
    )
    monkeypatch.setattr(
        "app.chat.worker._prior_citations",
        lambda *_: ["Section 9", "Section 9, ACJA 2015"],
    )
    assert _relative_query(db, uuid4(), "What does it mean?") is None


def test_act_titles_use_arrangement_headings_beyond_the_partial_catalogue(
    db: Session, statute_corpus
) -> None:
    corpus = load_public_corpus(db, statute_corpus)
    act = next(item for item in corpus.instruments.values() if item.slug == "acja-2015")
    parent = Provision(
        instrument_id=act.id,
        canonical_path="acja-2015.section400",
        number="400",
        kind=ProvisionKind.SECTION,
        heading="Synthetic arrangement heading",
    )
    child = Provision(
        instrument_id=act.id,
        canonical_path="acja-2015.section400.subsection1",
        number="1",
        kind=ProvisionKind.SUBSECTION,
        parent_id=parent.id,
    )
    corpus.provisions[parent.id] = parent
    corpus.provisions[child.id] = child
    assert corpus.reference(parent).title == "Synthetic arrangement heading"
    assert corpus.reference(child).title == "Synthetic arrangement heading"


def test_nested_act_paragraphs_load_into_the_public_corpus(
    client: TestClient, db: Session, statute_corpus
) -> None:
    section = db.exec(
        select(Provision).where(Provision.canonical_path == "acja-2015.section9")
    ).one()
    version = db.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == section.id)
    ).one()
    parent_id = section.id
    for path, number in (
        ("acja-2015.section9.paragraphb", "b"),
        ("acja-2015.section9.paragraphb.paragraphi", "i"),
    ):
        paragraph = Provision(
            instrument_id=section.instrument_id,
            kind=ProvisionKind.PARAGRAPH,
            number=number,
            canonical_path=path,
            sort_key=f"009.{number}",
            parent_id=parent_id,
        )
        db.add(paragraph)
        db.flush()
        text = f"Synthetic paragraph ({number})."
        nested = ProvisionVersion(
            provision_id=paragraph.id,
            source_document_id=version.source_document_id,
            text=text,
            normalized_text=text.lower(),
            text_sha256=legal_text_sha256(text),
            valid_from=date(2020, 1, 1),
            legal_status=LegalStatus.HISTORICAL,
        )
        db.add(nested)
        db.flush()
        db.add(
            CorpusReleaseEntry(
                release_id=statute_corpus.id,
                provision_version_id=nested.id,
                source_document_id=version.source_document_id,
            )
        )
        parent_id = paragraph.id
    db.commit()

    corpus = load_public_corpus(db, statute_corpus)
    assert parent_id in corpus.provisions
    response = client.get("/api/v1/legal/instruments")
    assert response.status_code == 200
    assert "acja-2015" in {item["slug"] for item in response.json()["data"]}
