import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.runtime.queue import enqueue_task
from app.ingestion.runtime.runner import run_until_idle
from app.legal.act_parser import ACT_PARSER_VERSION
from app.legal.enums import (
    CorpusReleaseStatus,
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    InstrumentType,
    LegalStatus,
    VerificationStatus,
)
from app.legal.models import (
    CorpusRelease,
    ExtractionCandidate,
    IngestionStep,
    LegalInstrument,
    ProvisionVersion,
    SourceUpload,
)
from tests.api.routes.admin.conftest import _source_upload_payload
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.ingestion.worker.conftest import (
    _clear_run_tasks,
    _store_raw_extraction,
    _stored_source_and_run,
)


def test_act_upload_is_opt_in_and_type_is_retained(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    body = {**_source_upload_payload(b"%PDF-1.4 synthetic"), "instrument_type": "act"}
    monkeypatch.setattr(
        settings, "INGESTION_ALLOWED_INSTRUMENT_TYPES", ["constitution"]
    )
    disabled = client.post(
        "/api/v1/admin/source-uploads", headers=superuser_token_headers, json=body
    )
    assert disabled.status_code == 422
    assert "disabled" in disabled.json()["detail"]
    monkeypatch.setattr(
        settings, "INGESTION_ALLOWED_INSTRUMENT_TYPES", ["constitution", "act"]
    )
    enabled = client.post(
        "/api/v1/admin/source-uploads", headers=superuser_token_headers, json=body
    )
    assert enabled.status_code == 200
    assert enabled.json()["instrument_type"] == "act"
    upload = db.get(SourceUpload, uuid.UUID(enabled.json()["id"]))
    assert upload and upload.instrument_type == InstrumentType.ACT


def test_act_review_and_materialization_force_historical_versions(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        settings, "INGESTION_ALLOWED_INSTRUMENT_TYPES", ["constitution", "act"]
    )
    instrument = LegalInstrument(
        slug=f"test-act-{uuid.uuid4().hex}",
        title="Synthetic test Act",
        instrument_type=InstrumentType.ACT,
        year=2015,
    )
    db.add(instrument)
    db.commit()
    source, run = _stored_source_and_run(
        db,
        tmp_path=tmp_path,
        pdf=_pdf_with_pages([uuid.uuid4().hex]),
        instrument=instrument,
    )
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text="ARRANGEMENT OF SECTIONS\n1. First heading.\nENACTED by the National Assembly\nPART I - PRELIMINARY\n1. (1) Synthetic first clause.\n(2) Synthetic second clause.",
    )
    normalize_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalize_step,
        task_type="normalizing",
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )
    run_until_idle(db, worker_id="act-test", max_tasks=3)
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert source.verification_status != VerificationStatus.VERIFIED
    candidates = db.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    assert candidates and all(
        c.status == ExtractionCandidateStatus.NEEDS_REVIEW for c in candidates
    )
    assert not any(c.materialized_version_id for c in candidates)
    # Test fixture simulates the existing human approval boundary.
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    for candidate in candidates:
        assert candidate.blocking_issue_count == 0
        candidate.status = ExtractionCandidateStatus.APPROVED
        db.add(candidate)
    run.pipeline_config = {
        **run.pipeline_config,
        "instrument_parser": "constitution",
        "corpus_legal_status": "current",
    }
    db.add(run)
    db.add(source)
    db.commit()
    step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=step,
        task_type="materializing",
        idempotency_key=f"{run.id}:materialize",
        payload={"source_document_id": str(source.id)},
    )
    results = run_until_idle(db, worker_id="act-test", max_tasks=2)
    assert [str(result.stage) for result in results] == [
        "materializing",
        "building_retrieval_documents",
    ]
    versions = [
        db.get(ProvisionVersion, c.materialized_version_id)
        for c in candidates
        if c.materialized_version_id
    ]
    assert versions and all(
        v and v.legal_status == LegalStatus.HISTORICAL for v in versions
    )
    release = db.exec(
        select(CorpusRelease).where(CorpusRelease.version == f"draft-{run.id.hex[:12]}")
    ).one()
    assert release.status == CorpusReleaseStatus.BUILDING
    assert release.parser_version == ACT_PARSER_VERSION
    assert (
        release.validation_report["source_edition_review"]["edition"]
        == "As enacted, 2015"
    )
    assert (
        release.validation_report["source_edition_review"]["notice"]
        == "As enacted, may have been amended."
    )
