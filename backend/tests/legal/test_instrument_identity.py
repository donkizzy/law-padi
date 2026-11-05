"""A second instrument must never satisfy a bare Constitution reference."""

import hashlib
import importlib
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, col, select

from app.chat.schemas import ExplanationBlock, ExplanationDraft
from app.chat.validation import EvidenceValidationError, validate_draft
from app.chat.worker import _source_crossrefs
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
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
from app.legal.evidence import exact_lookup
from app.legal.models import (
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalSegment,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import (
    load_public_corpus,
    load_ranked_corpus,
    load_reference_corpus,
)
from app.legal.references import (
    ReferenceParse,
    SectionReference,
    matches_reference,
    parse_section_reference,
)
from app.legal.schemas import EvidenceItem

pytest_plugins = ["tests.api.routes.test_legal_search"]


@pytest.fixture
def mixed_corpus(db: Session, corpus):
    release, source, nodes, _pdf = corpus
    release.status = CorpusReleaseStatus.BUILDING
    db.add(release)
    db.commit()
    constitution = db.get(LegalInstrument, nodes["chapter4"].instrument_id)
    assert constitution
    act = LegalInstrument(
        slug="acja-2015",
        title="Administration of Criminal Justice Act 2015",
        short_title="ACJA 2015",
        instrument_type=InstrumentType.ACT,
    )
    db.add(act)
    db.flush()
    db.refresh(source)
    act_source = SourceDocument.model_validate(
        {
            **source.model_dump(),
            "id": uuid4(),
            "legal_instrument_id": act.id,
            "title": "Synthetic test Act",
            "sha256": hashlib.sha256(b"synthetic-act").hexdigest(),
        }
    )
    db.add(act_source)
    db.flush()
    versions = {}
    provisions = {}
    entries = []
    for instrument, document in ((constitution, source), (act, act_source)):
        for number in ("9", "37"):
            provision = Provision(
                instrument_id=instrument.id,
                kind=ProvisionKind.SECTION,
                number=number,
                canonical_path=f"{instrument.slug}.section{number}",
                sort_key=f"{number:0>3}",
            )
            # The existing Constitution already includes Section 37.
            if instrument.id == constitution.id and number == "37":
                continue
            text = f"Synthetic {instrument.slug} section {number}."
            version = ProvisionVersion(
                provision_id=provision.id,
                text=text,
                normalized_text=text.lower(),
                valid_from=date(2015, 1, 1),
                legal_status=LegalStatus.HISTORICAL,
                source_document_id=document.id,
                text_sha256=legal_text_sha256(text),
            )
            entry = CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=document.id,
            )
            db.add(provision)
            db.flush()
            db.add(version)
            db.flush()
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
        instruments_by_id={constitution.id: constitution, act.id: act},
    )
    segments = write_segments(db, release_id=release.id, documents=documents)
    release.status = CorpusReleaseStatus.PRODUCTION
    db.add(release)
    db.commit()
    return release, act, segments, documents


def test_exact_search_and_evidence_remain_constitution_scoped(
    client: TestClient, mixed_corpus
) -> None:
    assert mixed_corpus
    body = client.post("/api/v1/legal/search", json={"query": "Section 9"}).json()
    assert body["outcome"] == "exact"
    assert [row["canonical_path"] for row in body["data"]] == [
        "constitution-1999.section9"
    ]
    result = body["data"][0]
    assert result["citation"] == "Section 9"
    assert result["instrument_type"] == "constitution"
    assert body["evidence"][0]["instrument_slug"] == "constitution-1999"
    assert (
        client.get(
            "/api/v1/legal/provisions/by-citation", params={"citation": "Section 9"}
        ).json()["data"][0]["canonical_path"]
        == "constitution-1999.section9"
    )


def test_all_canonical_loaders_supply_real_act_identity(
    db: Session, mixed_corpus
) -> None:
    release, act, segments, _documents = mixed_corpus
    reference = SectionReference("9", instrument_slug=act.slug)
    focused = load_reference_corpus(db, release, [reference])
    exact = exact_lookup(
        focused, ReferenceParse((reference,)), "synthetic lookup"
    ).response
    assert exact.count == 1
    result = exact.data[0]
    assert result.citation == "Section 9, ACJA 2015"
    assert result.short_citation == "ACJA s.9"
    assert result.title == "Search of arrested suspect"
    assert exact.evidence[0].instrument_title == act.title
    assert exact.evidence[0].instrument_type == InstrumentType.ACT
    for corpus in (
        load_public_corpus(db, release),
        load_ranked_corpus(db, release, [result.provision_version_id]),
    ):
        provision = corpus.provisions[result.provision_id]
        assert corpus.result(provision).instrument_slug == act.slug
        assert corpus.reference(provision).short_citation == "ACJA s.9"
    assert all(
        segment.instrument_id == db.get(Provision, segment.provision_id).instrument_id
        for segment in segments
    )


def test_public_loaders_accept_a_paragraph_under_a_schedule_item(
    db: Session, mixed_corpus
) -> None:
    release, act, segments, _documents = mixed_corpus
    source_id = db.exec(
        select(ProvisionVersion.source_document_id).where(
            ProvisionVersion.provision_id == segments[-1].provision_id
        )
    ).one()
    schedule = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SCHEDULE,
        number="1",
        canonical_path=f"{act.slug}.schedule1",
        sort_key="900",
    )
    db.add(schedule)
    db.flush()
    item = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SCHEDULE_ITEM,
        number="16",
        parent_id=schedule.id,
        canonical_path=f"{act.slug}.schedule1.item16",
        sort_key="901",
    )
    db.add(item)
    db.flush()
    paragraph = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.PARAGRAPH,
        number="a",
        parent_id=item.id,
        canonical_path=f"{act.slug}.schedule1.item16.paragrapha",
        sort_key="902",
    )
    db.add(paragraph)
    db.flush()
    text = "(a) any vacancy in the membership of the Council."
    version = ProvisionVersion(
        provision_id=paragraph.id,
        text=text,
        normalized_text=text.lower(),
        valid_from=date(2015, 1, 1),
        legal_status=LegalStatus.HISTORICAL,
        source_document_id=source_id,
        text_sha256=legal_text_sha256(text),
    )
    db.add(version)
    db.flush()
    db.add(
        CorpusReleaseEntry(
            release_id=release.id,
            provision_version_id=version.id,
            source_document_id=source_id,
        )
    )
    db.commit()

    for corpus in (
        load_public_corpus(db, release),
        load_ranked_corpus(db, release, [version.id]),
    ):
        assert corpus.result(corpus.provisions[paragraph.id]).instrument_slug == (
            act.slug
        )


def test_topics_do_not_promote_an_acts_same_numbered_section(
    db: Session, mixed_corpus
) -> None:
    release, _act, _segments, _documents = mixed_corpus
    rows = topic_search(db, release_id=release.id, query="privacy")
    assert rows
    assert all(
        segment.canonical_path.startswith("constitution-1999.")
        for segment, _score in rows
    )


def test_sql_matching_escapes_instrument_wildcards(db: Session, mixed_corpus) -> None:
    assert mixed_corpus
    reference = SectionReference("9", instrument_slug="%")
    assert not db.exec(
        select(Provision).where(
            matches_reference(col(Provision.canonical_path), reference)
        )
    ).all()


def test_segment_writer_rejects_wrong_instrument(db: Session, mixed_corpus) -> None:
    release, _act, _segments, documents = mixed_corpus
    document = documents[0]
    with pytest.raises(PgVectorRetrievalError, match="instrument"):
        write_segments(
            db,
            release_id=release.id,
            documents=[
                replace(
                    document,
                    payload={**document.payload, "instrument_id": str(uuid4())},
                )
            ],
        )


def test_migration_backfills_published_rows_without_changing_retrieval_data(
    db: Session, mixed_corpus
) -> None:
    release, _act, _segments, _documents = mixed_corpus
    connection = db.connection()
    snapshot = text(
        "SELECT to_jsonb(s) - 'instrument_id' FROM retrieval_segment s WHERE release_id = :release_id ORDER BY id"
    )
    before = connection.execute(snapshot, {"release_id": release.id}).all()
    migration = importlib.import_module(
        "app.alembic.versions.f5a6b7c8d9e0_scope_retrieval_segments_to_instruments"
    )
    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        migration.upgrade()
    assert connection.execute(snapshot, {"release_id": release.id}).all() == before
    assert (
        connection.execute(
            text(
                "SELECT count(*) FROM retrieval_segment s JOIN provision p ON p.id = s.provision_id WHERE s.instrument_id IS DISTINCT FROM p.instrument_id"
            )
        ).scalar_one()
        == 0
    )
    with pytest.raises(DBAPIError, match="immutable"):
        with db.begin_nested():
            db.exec(
                update(RetrievalSegment)
                .where(RetrievalSegment.release_id == release.id)
                .values(citation="tampered")
            )


@pytest.mark.parametrize(
    "path,ancestors,text",
    [
        ("acja-2015.section9", [], "Synthetic text."),
        ("acja-2015.section10", ["Section 9"], "Synthetic text."),
        ("acja-2015.section10", [], "See Section 9."),
    ],
)
def test_act_evidence_cannot_support_constitution_citations(
    path: str, ancestors: list[str], text: str
) -> None:
    release_id = uuid4()
    item = EvidenceItem.model_construct(
        evidence_id="E1",
        release_id=release_id,
        canonical_path=path,
        instrument_slug="acja-2015",
        ancestor_citations=ancestors,
        authoritative_text=text,
        legal_status="historical",
    )
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(text="Section 9 protects this right.", evidence_ids=["E1"])
        ]
    )
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [item], release_id=release_id)


def test_internal_cross_references_keep_the_source_instrument() -> None:
    assert _source_crossrefs("See section 9.", "acja-2015") == [
        SectionReference("9", instrument_slug="acja-2015")
    ]
    assert parse_section_reference("Section 9").reference == SectionReference("9")
    assert _source_crossrefs("See section 9 and section 9.", "acja-2015") == [
        SectionReference("9", instrument_slug="acja-2015")
    ]


def test_selected_act_provision_cannot_satisfy_a_constitution_question(
    client: TestClient, db: Session, mixed_corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    assert mixed_corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    provision = db.exec(
        select(Provision).where(Provision.canonical_path == "acja-2015.section9")
    ).one()
    version = db.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == provision.id)
    ).one()
    conversation = client.post("/api/v1/conversations", json={}).json()
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={
            "question": "Explain Section 9",
            "selected_provision_version_id": str(version.id),
            "idempotency_key": "cross-instrument-reference",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Selected provision does not match the question"
