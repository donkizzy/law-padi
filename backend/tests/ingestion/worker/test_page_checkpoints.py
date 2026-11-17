import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.common import get_datetime_utc
from app.ingestion.ocr import OcrPageResult
from app.ingestion.rendering import RenderedPageThumbnail
from app.ingestion.runtime.queue import enqueue_task
from app.ingestion.runtime.runner import run_once
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
    PageInclusionStatus,
)
from app.legal.models import IngestionArtifact, SourcePage
from tests.factories.pdf import pdf_with_pages
from tests.ingestion.worker.conftest import (
    _clear_run_tasks,
    _store_raw_extraction,
    _stored_source_and_run,
)


@pytest.mark.parametrize(
    "stage",
    [
        IngestionStage.RENDERING,
        IngestionStage.NATIVE_EXTRACTION,
        IngestionStage.LOCAL_OCR,
        IngestionStage.MANAGED_OCR,
    ],
)
def test_page_retry_keeps_checkpoints_and_calls_providers_without_transaction(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: IngestionStage,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run = _stored_source_and_run(
        db,
        tmp_path=tmp_path,
        pdf=pdf_with_pages(["", "", ""]) + uuid.uuid4().hex.encode(),
    )
    _clear_run_tasks(db, run)
    for number in range(1, 4):
        if stage == IngestionStage.LOCAL_OCR:
            _store_raw_extraction(
                db,
                tmp_path=tmp_path,
                run=run,
                source=source,
                page_number=number,
                text="",
                quality_flags={"needs_ocr": True},
            )
        else:
            db.add(
                SourcePage(
                    run_id=run.id,
                    source_document_id=source.id,
                    page_number=number,
                    inclusion_status=PageInclusionStatus.INCLUDED,
                )
            )
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = stage
    db.add(run)
    db.commit()
    task = enqueue_task(
        db,
        run=run,
        step=None,
        task_type=stage.value,
        idempotency_key=f"{run.id}:{stage}",
        payload={"included_pages": [1, 2, 3], "page_numbers": [1, 2, 3]},
    )
    calls: list[int] = []
    transaction_states: list[bool] = []
    store = LocalBlobStore(tmp_path)
    put = store.put_artifact
    failed = False

    def put_artifact(**kwargs: Any) -> Any:
        nonlocal failed
        number = int(kwargs["metadata"]["page_number"])
        calls.append(number)
        transaction_states.append(db.in_transaction())
        if number == 2 and not failed:
            failed = True
            raise ConnectionError("temporary storage outage")
        return put(**kwargs)

    class Provider:
        def extract_page(self, page: Any) -> OcrPageResult:
            transaction_states.append(db.in_transaction())
            return OcrPageResult(
                page_number=page.page_number,
                text="text",
                words=[],
                method="managed_ocr"
                if stage == IngestionStage.MANAGED_OCR
                else "local_ocr",
                provider="test",
                provider_version="v1",
                confidence=0.99,
                timing_ms=1,
                cost_usd=0.01,
                quality_flags={},
            )

    def render(
        _content: Any, *, page_number: int, **_kwargs: Any
    ) -> RenderedPageThumbnail:
        transaction_states.append(db.in_transaction())
        return RenderedPageThumbnail(page_number, b"png")

    monkeypatch.setattr(store, "put_artifact", put_artifact)
    monkeypatch.setattr("app.ingestion.stages.pages.get_blob_store", lambda: store)
    monkeypatch.setattr("app.ingestion.stages.pages.render_page_thumbnail", render)
    monkeypatch.setattr(
        "app.ingestion.stages.pages.TesseractOcrProvider", lambda **_: Provider()
    )
    monkeypatch.setattr(
        "app.ingestion.stages.pages.managed_ocr_provider_from_settings", Provider
    )
    result = run_once(db, worker_id="page-worker", task_type=stage.value)
    assert result is not None and result.task_status == IngestionTaskStatus.PENDING
    artifacts = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type != "raw_extraction"
            if stage == IngestionStage.LOCAL_OCR
            else IngestionArtifact.artifact_type != "original_source",
        )
    ).all()
    assert len(artifacts) == 1
    assert not any(transaction_states)
    db.refresh(task)
    task.available_at = get_datetime_utc()
    db.add(task)
    db.commit()
    result = run_once(db, worker_id="page-worker", task_type=stage.value)
    assert result is not None and result.task_status == IngestionTaskStatus.SUCCEEDED
    assert calls == [1, 2, 2, 3]
    assert not any(transaction_states)


def test_native_artifact_versions_do_not_duplicate_pages(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    from app.ingestion.stages.artifacts import ensure_artifact
    from app.ingestion.stages.page_payloads import raw_extraction_payloads
    from app.legal.enums import IngestionArtifactType

    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=pdf_with_pages([uuid.uuid4().hex])
    )
    _store_raw_extraction(
        db, tmp_path=tmp_path, run=run, source=source, page_number=1, text="old"
    )
    blob = LocalBlobStore(tmp_path).put_artifact(
        run_id=str(run.id),
        artifact_type="raw_extraction",
        filename="page-0001-new.json",
        content=json.dumps(
            {"page_number": 1, "text": "new", "method": "native_pdf"}
        ).encode(),
        content_type="application/json",
    )
    ensure_artifact(
        db,
        run_id=run.id,
        artifact_type=IngestionArtifactType.RAW_EXTRACTION,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={"page_number": 1},
    )
    db.commit()
    assert [payload["text"] for payload in raw_extraction_payloads(db, run)] == ["new"]
