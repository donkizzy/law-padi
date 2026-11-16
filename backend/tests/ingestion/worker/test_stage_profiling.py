import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.runtime.runner import run_until_idle
from app.ingestion.worker import handle_profiling
from app.legal.enums import (
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    PageInclusionStatus,
    PageRole,
    VerificationStatus,
)
from app.legal.models import (
    IngestionArtifact,
    IngestionEvent,
    IngestionStep,
    IngestionTask,
    SourcePage,
)
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.factories.pdf import sha256 as _sha256
from tests.ingestion.worker.conftest import _stored_source_and_run


def test_worker_runs_verify_scan_and_profile_until_page_confirmation(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages(
        [
            f"Official copy {uuid.uuid4().hex}",
            f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}\n"
            "37. Right to private and family life",
            f"FIRST SCHEDULE - States of the Federation {uuid.uuid4().hex}\n1. Abia",
        ]
    )
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)

    results = run_until_idle(db, worker_id="worker-test", max_tasks=5)

    assert [result.stage for result in results] == [
        IngestionStage.VERIFYING_UPLOAD,
        IngestionStage.MALWARE_SCAN,
        IngestionStage.PROFILING,
        IngestionStage.RENDERING,
    ]
    db.refresh(run)
    db.refresh(source)
    assert run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    assert source.verification_status == VerificationStatus.NEEDS_REVIEW

    steps = db.exec(
        select(IngestionStep)
        .where(IngestionStep.run_id == run.id)
        .order_by(IngestionStep.created_at)
    ).all()
    by_stage = {step.stage: step for step in steps}
    assert by_stage[IngestionStage.VERIFYING_UPLOAD].status == (
        IngestionStepStatus.SUCCEEDED
    )
    assert by_stage[IngestionStage.MALWARE_SCAN].status == IngestionStepStatus.SUCCEEDED
    assert by_stage[IngestionStage.PROFILING].metrics == {
        "page_count": 3,
        "suggested_included_pages": 2,
        "requires_ocr_pages": 0,
    }
    assert by_stage[IngestionStage.AWAITING_PAGE_CONFIRMATION].status == (
        IngestionStepStatus.BLOCKED
    )

    pages = db.exec(
        select(SourcePage)
        .where(SourcePage.run_id == run.id)
        .order_by(SourcePage.page_number)
    ).all()
    assert [page.role for page in pages] == [
        PageRole.FRONT_MATTER,
        PageRole.LEGAL_BODY,
        PageRole.SCHEDULE,
    ]
    assert [page.inclusion_status for page in pages] == [
        PageInclusionStatus.SUGGESTED_EXCLUDE,
        PageInclusionStatus.SUGGESTED_INCLUDE,
        PageInclusionStatus.SUGGESTED_INCLUDE,
    ]
    assert pages[2].inclusion_reason == (
        "Suggested inclusion: schedules are part of the Constitution"
    )

    artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.ORIGINAL_SOURCE,
        )
    ).one()
    assert artifact.storage_key == source.storage_key
    assert artifact.sha256 == _sha256(pdf)

    events = db.exec(
        select(IngestionEvent)
        .where(IngestionEvent.run_id == run.id)
        .order_by(IngestionEvent.sequence)
    ).all()
    assert [event.event_type for event in events] == [
        "stage_started",
        "stage_succeeded",
        "stage_started",
        "stage_succeeded",
        "stage_started",
        "stage_succeeded",
        "stage_started",
        "stage_succeeded",
        "stage_blocked",
    ]


def test_worker_fails_malware_scan_before_profiling(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages(["1. Safe page"]) + b"\n/JavaScript"
    _source, run = _stored_source_and_run(
        db,
        tmp_path=tmp_path,
        pdf=pdf,
        max_attempts=1,
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=4)

    assert [result.stage for result in results] == [
        IngestionStage.VERIFYING_UPLOAD,
        IngestionStage.MALWARE_SCAN,
        IngestionStage.MALWARE_SCAN,
        IngestionStage.MALWARE_SCAN,
    ]
    assert results[-1].task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "active or embedded content" in run.error_details["message"]
    profiling_tasks = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.PROFILING.value,
        )
    ).all()
    assert profiling_tasks == []


def test_profile_stage_is_idempotent_and_preserves_admin_inclusion_choices(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages(
        [f"CHAPTER IV {uuid.uuid4().hex}\n37. Right to private and family life"]
    )
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.VERIFYING_UPLOAD.value,
        )
    ).one()
    task.task_type = IngestionStage.PROFILING.value
    task.payload = {"source_document_id": str(source.id)}
    db.add(task)
    db.commit()

    handle_profiling(db, run, task)
    page = db.exec(select(SourcePage).where(SourcePage.run_id == run.id)).one()
    page.inclusion_status = PageInclusionStatus.INCLUDED
    page.inclusion_reason = "Confirmed by legal reviewer"
    db.add(page)
    db.commit()

    handle_profiling(db, run, task)
    pages = db.exec(select(SourcePage).where(SourcePage.run_id == run.id)).all()

    assert len(pages) == 1
    assert pages[0].inclusion_status == PageInclusionStatus.INCLUDED
    assert pages[0].inclusion_reason == "Confirmed by legal reviewer"
