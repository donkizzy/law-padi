import json
import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.ocr import OcrPageInput, OcrPageResult, OcrWord
from app.ingestion.rendering import RenderedPageThumbnail
from app.ingestion.worker import (
    run_until_idle,
)
from app.ingestion.workflow import enqueue_task
from app.legal.enums import (
    IngestionArtifactType,
    IngestionStage,
    IngestionStepStatus,
)
from app.legal.models import (
    IngestionArtifact,
    IngestionStep,
)
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.ingestion.worker.conftest import (
    _clear_run_tasks,
    _store_raw_extraction,
    _stored_source_and_run,
)


def test_worker_local_ocr_artifact_feeds_normalization(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.ingestion.worker.render_page_thumbnail",
        lambda _content, *, page_number, scale_to=1600: RenderedPageThumbnail(
            page_number=page_number,
            content=b"\x89PNG\r\n\x1a\nfake",
        ),
    )

    class FakeLocalOcrProvider:
        def extract_page(self, page: OcrPageInput) -> OcrPageResult:
            return OcrPageResult(
                page_number=page.page_number,
                text="37. Right to private and family life",
                words=[
                    OcrWord(
                        text="37.",
                        bbox={"x0": 10, "y0": 20, "x1": 22, "y1": 32},
                        confidence=0.95,
                        reading_order=1,
                    ),
                    OcrWord(
                        text="Right",
                        bbox={"x0": 24, "y0": 20, "x1": 58, "y1": 32},
                        confidence=0.96,
                        reading_order=2,
                    ),
                ],
                method="local_ocr",
                provider="fake-tesseract",
                provider_version="fake-local-ocr-v1",
                confidence=0.955,
                timing_ms=3.4,
                cost_usd=0,
                quality_flags={
                    "empty_text": False,
                    "word_count": 2,
                    "low_confidence": False,
                    "requires_managed_ocr": False,
                },
            )

    monkeypatch.setattr(
        "app.ingestion.worker.TesseractOcrProvider",
        lambda: FakeLocalOcrProvider(),
    )
    pdf = _pdf_with_pages([f"Scanned placeholder {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text="",
        spans=[],
        quality_flags={"span_count": 0, "needs_ocr": True},
    )
    local_ocr_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.LOCAL_OCR,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=local_ocr_step,
        task_type=IngestionStage.LOCAL_OCR.value,
        idempotency_key=f"{run.id}:local-ocr",
        payload={"source_document_id": str(source.id), "included_pages": [1]},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=2)

    assert [result.stage for result in results] == [
        IngestionStage.LOCAL_OCR,
        IngestionStage.NORMALIZING,
    ]
    artifacts = db.exec(
        select(IngestionArtifact).where(IngestionArtifact.run_id == run.id)
    ).all()
    assert {
        IngestionArtifactType.OCR_OUTPUT,
        IngestionArtifactType.NORMALIZED_PAGES,
    }.issubset({artifact.artifact_type for artifact in artifacts})
    normalized_artifact = next(
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.NORMALIZED_PAGES
    )
    normalized_payload = json.loads(
        LocalBlobStore(tmp_path).read_bytes(normalized_artifact.storage_key)
    )
    assert normalized_payload["pages"][0]["text"] == (
        "37. Right to private and family life"
    )
    assert normalized_payload["pages"][0]["method"] == "local_ocr"


def test_worker_managed_ocr_replaces_low_confidence_local_ocr(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.ingestion.worker.render_page_thumbnail",
        lambda _content, *, page_number, scale_to=1600: RenderedPageThumbnail(
            page_number=page_number,
            content=b"\x89PNG\r\n\x1a\nfake",
        ),
    )

    class FakeLocalOcrProvider:
        def extract_page(self, page: OcrPageInput) -> OcrPageResult:
            return OcrPageResult(
                page_number=page.page_number,
                text="37. R1ght to prlvate life",
                words=[
                    OcrWord(
                        text="R1ght",
                        bbox={"x0": 10, "y0": 20, "x1": 44, "y1": 32},
                        confidence=0.42,
                        reading_order=1,
                    )
                ],
                method="local_ocr",
                provider="fake-tesseract",
                provider_version="fake-local-ocr-v1",
                confidence=0.42,
                timing_ms=3.4,
                cost_usd=0,
                quality_flags={
                    "empty_text": False,
                    "word_count": 1,
                    "low_confidence": True,
                    "requires_managed_ocr": True,
                },
            )

    class FakeManagedOcrProvider:
        def extract_page(self, page: OcrPageInput) -> OcrPageResult:
            return OcrPageResult(
                page_number=page.page_number,
                text="37. Right to private and family life",
                words=[
                    OcrWord(
                        text="Right",
                        bbox={"x0": 10, "y0": 20, "x1": 46, "y1": 32},
                        confidence=0.97,
                        reading_order=1,
                    )
                ],
                method="managed_ocr",
                provider="fake-managed",
                provider_version="fake-managed-ocr-v1",
                confidence=0.97,
                timing_ms=12.5,
                cost_usd=0.002,
                quality_flags={
                    "empty_text": False,
                    "word_count": 1,
                    "low_confidence": False,
                },
            )

    monkeypatch.setattr(
        "app.ingestion.worker.TesseractOcrProvider",
        lambda: FakeLocalOcrProvider(),
    )
    monkeypatch.setattr(
        "app.ingestion.worker.managed_ocr_provider_from_settings",
        lambda: FakeManagedOcrProvider(),
    )
    pdf = _pdf_with_pages([f"Scanned placeholder {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text="",
        spans=[],
        quality_flags={"span_count": 0, "needs_ocr": True},
    )
    local_ocr_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.LOCAL_OCR,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=local_ocr_step,
        task_type=IngestionStage.LOCAL_OCR.value,
        idempotency_key=f"{run.id}:local-ocr-managed-fallback",
        payload={"source_document_id": str(source.id), "included_pages": [1]},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.LOCAL_OCR,
        IngestionStage.MANAGED_OCR,
        IngestionStage.NORMALIZING,
    ]
    managed_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MANAGED_OCR,
        )
    ).one()
    assert managed_step.status == IngestionStepStatus.SUCCEEDED
    assert managed_step.metrics == {"managed_ocr_page_count": 1}

    artifacts = db.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.OCR_OUTPUT,
        )
        .order_by(IngestionArtifact.storage_key)
    ).all()
    assert len(artifacts) == 2
    assert [artifact.artifact_metadata["provider"] for artifact in artifacts] == [
        "fake-tesseract",
        "fake-managed",
    ]
    normalized_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.NORMALIZED_PAGES,
        )
    ).one()
    normalized_payload = json.loads(
        LocalBlobStore(tmp_path).read_bytes(normalized_artifact.storage_key)
    )
    assert normalized_payload["pages"][0]["text"] == (
        "37. Right to private and family life"
    )
    assert normalized_payload["pages"][0]["method"] == "managed_ocr"
