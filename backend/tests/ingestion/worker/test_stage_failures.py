import uuid
from pathlib import Path

import pytest
from sqlmodel import Session

from app.core.config import settings
from app.ingestion.runtime.runner import run_once
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
)
from app.legal.models import (
    IngestionRun,
    IngestionTask,
)
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.ingestion.worker.conftest import _stored_source_and_run


def test_worker_failure_retries_then_marks_run_failed(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages(["1. Safe page"])
    _source, run = _stored_source_and_run(
        db,
        tmp_path=tmp_path,
        pdf=pdf,
        expected_sha256=(uuid.uuid4().hex + uuid.uuid4().hex),
        max_attempts=1,
    )

    result = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.VERIFYING_UPLOAD.value,
    )

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "SHA-256" in run.error_details["message"]


def test_worker_records_database_failure_after_rolling_back_partial_stage(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=_pdf_with_pages(["1. Safe page"]), max_attempts=1
    )
    original_title = source.title

    def fail_flush(session: Session, _run: IngestionRun, _task: IngestionTask) -> None:
        source.title = "x" * 513
        session.add(source)
        session.flush()

    monkeypatch.setattr(
        "app.ingestion.runtime.runner.handler_for", lambda _stage: fail_flush
    )
    result = run_once(db, worker_id="worker-test", task_type="verifying_upload")

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    db.refresh(source)
    assert source.title == original_title
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details["error_type"] == "DataError"


def test_deterministic_failure_does_not_spend_three_attempts(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ingestion.runtime.errors import IngestionWorkerError

    _source, run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=_pdf_with_pages(["page"]), max_attempts=3
    )

    def handler(*_args: object) -> None:
        raise IngestionWorkerError("Run does not have confirmed included pages")

    monkeypatch.setattr(
        "app.ingestion.runtime.runner.handler_for", lambda _stage: handler
    )
    result = run_once(db, worker_id="test", task_type="verifying_upload")
    assert result is not None and result.task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
