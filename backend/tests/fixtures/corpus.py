import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlmodel import Session

from app.core.config import settings
from app.core.db import init_db
from app.ingestion.pgvector_repository import (
    write_embeddings,
    write_segments,
)
from app.ingestion.retrieval import build_retrieval_documents
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
    VectorIndexStatus,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256
from tests.db import reset_database


@pytest.fixture
def corpus(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reset_database(db)
    init_db(db)
    instrument = LegalInstrument(
        slug="constitution-1999",
        title="Test Constitution",
        instrument_type=InstrumentType.CONSTITUTION,
    )
    db.add(instrument)
    db.flush()
    pdf = b"%PDF-1.4\nretained original test source\n%%EOF"
    folder = tmp_path / "original"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(pdf)
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Test authority",
        title="Historical Constitution compilation",
        source_url="https://example.test/constitution.pdf",
        mime_type="application/pdf",
        sha256=hashlib.sha256(pdf).hexdigest(),
        storage_backend="local",
        storage_key="original/source.pdf",
        original_filename="source.pdf",
        file_size=len(pdf),
        page_count=100,
        published_at=date(2004, 1, 1),
        retrieved_at=datetime.now(UTC),
    )
    release = CorpusRelease(
        version="published-test",
        validation_report={
            "source_edition_review": {
                "edition": "Historical/source Constitution compilation (LFN 2004)"
            }
        },
    )
    db.add(source)
    db.add(release)
    db.flush()
    specs = [
        ("chapter4", "chapter", "4", None, None),
        (
            "chapter4.section33",
            "section",
            "33",
            "chapter4",
            "(1) Right to life.\n(2) Lawful exceptions.\n(a) Defence.\n(b) Arrest.",
        ),
        (
            "chapter4.section33.subsection2",
            "subsection",
            "2",
            "chapter4.section33",
            "(2) Lawful exceptions.\n(a) Defence.\n(b) Arrest.",
        ),
        (
            "chapter4.section33.subsection2.paragrapha",
            "paragraph",
            "a",
            "chapter4.section33.subsection2",
            "(a) Defence of any person from unlawful violence.",
        ),
        (
            "chapter4.section33.subsection2.paragraphb",
            "paragraph",
            "b",
            "chapter4.section33.subsection2",
            "(b) Lawful arrest.",
        ),
        (
            "chapter4.section37",
            "section",
            "37",
            "chapter4",
            "Privacy of citizens is protected. Privacy of homes is protected. Privacy of correspondence is protected.",
        ),
        ("chapter6", "chapter", "6", None, None),
        ("chapter6.part1", "part", "1", "chapter6", None),
        (
            "chapter6.part1.section189",
            "section",
            "189",
            "chapter6.part1",
            "First printed Section 189.",
        ),
        ("chapter6.part2", "part", "2", "chapter6", None),
        (
            "chapter6.part2.section189",
            "section",
            "189",
            "chapter6.part2",
            "Second printed Section 189.",
        ),
    ]
    nodes = {}
    versions = {}
    entries = []
    for index, (path, kind, number, parent, text) in enumerate(specs):
        provision = Provision(
            instrument_id=instrument.id,
            parent_id=nodes[parent].id if parent else None,
            kind=ProvisionKind(kind),
            number=number,
            heading="Privacy" if number == "37" else path,
            canonical_path=f"constitution-1999.{path}",
            sort_key=f"{index:04d}",
        )
        db.add(provision)
        db.flush()
        nodes[path] = provision
        if text:
            version = ProvisionVersion(
                provision_id=provision.id,
                text=text,
                normalized_text=text.lower(),
                valid_from=date(2004, 1, 1),
                legal_status=LegalStatus.HISTORICAL,
                source_document_id=source.id,
                source_page_start=10 + index,
                source_page_end=10 + index,
                text_sha256=legal_text_sha256(text),
            )
            db.add(version)
            db.flush()
            versions[version.id] = version
            entry = CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=source.id,
            )
            db.add(entry)
            entries.append(entry)
    db.flush()
    profile = EmbeddingProfile(
        name="test-profile",
        provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
        model_name="test",
        model_revision="pinned",
        vector_dimensions=1024,
    )
    db.add(profile)
    db.flush()
    run = EmbeddingRun(release_id=release.id, profile_id=profile.id)
    db.add(run)
    db.flush()
    documents = build_retrieval_documents(
        release_version=release.version,
        entries=entries,
        versions_by_id=versions,
        provisions_by_id={p.id: p for p in nodes.values()},
        max_chars=55,
    )
    segments = write_segments(db, release_id=release.id, documents=documents)
    vector = [1.0] + [0.0] * 1023
    write_embeddings(
        db,
        release_id=release.id,
        embedding_run=run,
        profile=profile,
        segments=segments,
        vectors=[vector] * len(segments),
    )
    build = RetrievalIndexBuild(
        release_id=release.id,
        embedding_run_id=run.id,
        profile_id=profile.id,
        status=VectorIndexStatus.READY,
    )
    db.add(build)
    db.flush()
    db.add(
        ActiveRetrievalTarget(
            index_kind="enacted",
            release_id=release.id,
            embedding_run_id=run.id,
            retrieval_index_build_id=build.id,
            profile_id=profile.id,
        )
    )
    release.status = CorpusReleaseStatus.PRODUCTION
    db.add(release)
    db.commit()
    yield release, source, nodes, pdf
    reset_database(db)
    init_db(db)
