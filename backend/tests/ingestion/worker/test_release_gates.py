import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.service import (
    _release_source_and_review_gates,
    publish_corpus_release,
)
from app.legal.enums import (
    CorpusReleaseStatus,
    ExtractionCandidateStatus,
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
    ReviewIssue,
)
from app.legal.parser import PARSER_VERSION, legal_text_sha256, normalize_legal_text
from tests.ingestion.worker.conftest import (
    _approved_candidate,
    _release_with_retrieval_documents,
)
from tests.utils.user import create_random_user


def test_an_act_only_release_cannot_be_published(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, _run, _release, _profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    act = LegalInstrument(
        slug=f"act-{uuid.uuid4().hex[:12]}",
        title="Test Act",
        instrument_type=InstrumentType.ACT,
    )
    db.add(act)
    db.commit()
    provision = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SECTION,
        number="1",
        canonical_path=f"{act.slug}.section1",
        sort_key="001",
    )
    db.add(provision)
    db.commit()
    text = "This Act applies to criminal trials."
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalize_legal_text(text),
        valid_from=date(2015, 5, 13),
        legal_status=LegalStatus.HISTORICAL,
        source_document_id=source.id,
        text_sha256=legal_text_sha256(text),
    )
    release = CorpusRelease(
        version=f"draft-act-only-{uuid.uuid4().hex}",
        status=CorpusReleaseStatus.APPROVED,
        source_manifest_hash=legal_text_sha256(text),
        parser_version=PARSER_VERSION,
    )
    db.add_all([version, release])
    db.commit()
    db.add(
        CorpusReleaseEntry(
            release_id=release.id,
            provision_version_id=version.id,
            source_document_id=source.id,
        )
    )
    db.commit()
    db.refresh(release)

    with pytest.raises(HTTPException) as refused:
        publish_corpus_release(
            db,
            release.id,
            expected_version=release.lock_version,
            idempotency_key=f"publish-{uuid.uuid4().hex}",
            current_user=create_random_user(db),
            superuser_override_reason=None,
        )

    assert refused.value.status_code == 409
    assert "contains the Constitution" in str(refused.value.detail)
    db.refresh(release)
    assert release.status == CorpusReleaseStatus.APPROVED


def test_release_gates_ignore_rejected_candidates_and_their_findings(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, _profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    approved = _approved_candidate(db, run=run, source=source, text="Verified text")
    rejected = _approved_candidate(
        db,
        run=run,
        source=source,
        text="Duplicate scan (of section 37",
        canonical_path=f"{approved.canonical_path}.rejected-duplicate",
        sort_key="999",
    )
    rejected.status = ExtractionCandidateStatus.REJECTED
    db.add(rejected)
    db.add(
        ReviewIssue(
            candidate_id=rejected.id,
            issue_type="unbalanced_punctuation",
            blocking=True,
            message="Unbalanced brackets in a rejected duplicate.",
        )
    )
    db.commit()
    entries = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()

    assert _release_source_and_review_gates(db, entries, release=release) == []

    approved.status = ExtractionCandidateStatus.NEEDS_REVIEW
    db.add(approved)
    db.commit()
    assert _release_source_and_review_gates(db, entries, release=release) == [
        "release_candidate_not_approved"
    ]
