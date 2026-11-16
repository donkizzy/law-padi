import hashlib
from datetime import date
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.ingestion.pgvector_repository import (
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
from app.legal.titles import catalogue_titles


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
