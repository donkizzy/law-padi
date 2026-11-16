"""Offline ranking gate over synthetic catalogue wording, not legal-answer quality."""

import hashlib
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from sqlmodel import Session

from app.core.config import settings
from app.ingestion.pgvector_repository import (
    fuse_rankings,
    lexical_search,
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
    CorpusRelease,
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256
from app.legal.titles import catalogue_titles
from app.legal.topics import demoted_sections, rights_question, section_target
from tests.conftest import _cleanup_db

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "eval/baselines/retrieval.json"
pytestmark = pytest.mark.retrieval


def _id(key: str) -> UUID:
    # Segment IDs break score ties in production. Fix all their inputs too.
    return uuid5(NAMESPACE_URL, f"constitution.ng/offline-ranking/{key}")


@pytest.fixture
def catalogue_corpus(db: Session) -> Iterator[CorpusRelease]:
    _cleanup_db(db)
    release = CorpusRelease(id=_id("release"), version="offline-catalogue-v1")
    instrument = LegalInstrument(
        id=_id("instrument"),
        slug="constitution-1999",
        title="Synthetic Constitution catalogue",
        instrument_type=InstrumentType.CONSTITUTION,
    )
    db.add(release)
    db.add(instrument)
    db.flush()
    source = SourceDocument(
        id=_id("source"),
        legal_instrument_id=instrument.id,
        authority="Synthetic test fixture",
        source_url="https://example.test/offline-catalogue",
        mime_type="application/pdf",
        storage_backend="local",
        storage_key="offline-catalogue.pdf",
        original_filename="offline-catalogue.pdf",
        file_size=1,
        published_at=date(2004, 1, 1),
        retrieved_at=date(2026, 11, 16),
        title="Catalogue headings only; not legal wording",
        sha256=hashlib.sha256(b"offline-catalogue-v1").hexdigest(),
    )
    db.add(source)
    db.flush()
    provisions, versions, entries = {}, {}, []
    # Use the whole catalogue as distractors; never construct text from evaluation queries.
    for number, title in catalogue_titles(instrument.slug, "sections").items():
        provision = Provision(
            id=_id(f"section/{number}"),
            instrument_id=instrument.id,
            kind=ProvisionKind.SECTION,
            number=number,
            heading=title,
            canonical_path=f"constitution-1999.section{number}",
            sort_key=number.zfill(3),
        )
        db.add(provision)
        db.flush()
        text = f"Synthetic catalogue wording: {title}."
        version = ProvisionVersion(
            id=_id(f"version/{number}"),
            provision_id=provision.id,
            source_document_id=source.id,
            text=text,
            normalized_text=text.lower(),
            text_sha256=legal_text_sha256(text),
            valid_from=date(2004, 1, 1),
            legal_status=LegalStatus.HISTORICAL,
        )
        db.add(version)
        db.flush()
        entry = CorpusReleaseEntry(
            id=_id(f"entry/{number}"),
            release_id=release.id,
            provision_version_id=version.id,
            source_document_id=source.id,
        )
        db.add(entry)
        provisions[provision.id] = provision
        versions[version.id] = version
        entries.append(entry)
    db.flush()
    documents = build_retrieval_documents(
        release_version=release.version,
        entries=entries,
        versions_by_id=versions,
        provisions_by_id=provisions,
        instruments_by_id={instrument.id: instrument},
    )
    write_segments(db, release_id=release.id, documents=documents)
    release.status = CorpusReleaseStatus.PRODUCTION
    db.add(release)
    db.commit()
    try:
        yield release
    finally:
        _cleanup_db(db)


@pytest.mark.parametrize("split", ["benchmark", "heldout"])
def test_plain_language_fallback_ranking(
    db: Session, catalogue_corpus: CorpusRelease, split: str
) -> None:
    name = f"plain-language-retrieval-{split}-v1"
    dataset = json.loads((ROOT / "eval/datasets" / f"{name}.json").read_text())
    baseline = json.loads(BASELINE.read_text())[name]
    available = {
        f"constitution-1999:{n}"
        for n in catalogue_titles("constitution-1999", "sections")
    }
    cases = [
        case
        for case in dataset["cases"]
        if available.intersection(case["expected_sections"])
    ]
    assert len(cases) == baseline["case_count"]
    assert len(dataset["cases"]) == baseline["dataset_case_count"]
    assert len(available) == baseline["corpus_section_count"]
    reciprocal_ranks = []
    for case in cases:
        query = case["query"]
        # These are the same rankers, weights and options as the evidence fallback.
        # No embedding provider is constructed or called.
        ranked = fuse_rankings(
            lexical=lexical_search(db, release_id=catalogue_corpus.id, query=query),
            topics=topic_search(db, release_id=catalogue_corpus.id, query=query),
            top_k=10,
            lexical_weight=settings.RETRIEVAL_LEXICAL_WEIGHT,
            demoted=demoted_sections(query),
            prefer_constitution=rights_question(query),
            balance_instruments=False,
        )
        targets = [section_target(row.segment.canonical_path) for row in ranked]
        rank = next(
            (
                i
                for i, target in enumerate(targets, 1)
                if target in case["expected_sections"]
            ),
            None,
        )
        reciprocal_ranks.append(1 / rank if rank else 0.0)
    count = len(cases)
    metrics = {
        "hit_at_1": sum(r == 1 for r in reciprocal_ranks) / count,
        "hit_at_5": sum(r >= 1 / 5 for r in reciprocal_ranks) / count,
        "mrr_at_10": sum(reciprocal_ranks) / count,
    }
    print(f"{name}: {json.dumps(metrics, sort_keys=True)}")  # noqa: T201
    for metric, value in metrics.items():
        assert value + 1e-12 >= baseline["floor"][metric], (
            f"{name} {metric}: {value:.12f} < floor {baseline['floor'][metric]:.12f} ({count} cases)"
        )
