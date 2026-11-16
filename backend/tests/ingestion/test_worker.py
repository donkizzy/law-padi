import hashlib
import json
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject
from sqlmodel import Session, col, delete, select

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.ocr import OcrPageInput, OcrPageResult, OcrWord
from app.ingestion.pgvector_repository import dense_search, hybrid_search
from app.ingestion.rendering import RenderedPageThumbnail
from app.ingestion.service import (
    _release_source_and_review_gates,
    publish_corpus_release,
    start_embedding,
)
from app.ingestion.worker import (
    NORMALIZER_VERSION,
    IngestionWorkerError,
    _benchmark_dataset_for_embedding_profiles,
    _embed_with_checkpoints,
    _normalize_page_text,
    _upsert_historical_version_from_candidate,
    handle_building_retrieval_documents,
    handle_embedding,
    handle_profiling,
    run_once,
    run_until_idle,
)
from app.ingestion.workflow import create_run_steps, enqueue_task
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    ReviewDecisionType,
    SourceTier,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    ReleasePromotionAttempt,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
)
from app.legal.parser import PARSER_VERSION, legal_text_sha256, normalize_legal_text
from tests.utils.user import create_random_user


@pytest.fixture(autouse=True)
def isolate_ingestion_tasks(db: Session) -> Generator[None]:
    db.rollback()
    db.exec(delete(IngestionTask))
    db.commit()
    yield
    db.rollback()
    db.exec(delete(IngestionTask))
    db.commit()


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


def test_normalize_page_text_rejoins_split_section_markers() -> None:
    assert (
        _normalize_page_text(
            "Chapter I\n1\n. (1) This Constitution is supreme.\n1\n2. Twelfth item"
        )
        == "Chapter I\n1. (1) This Constitution is supreme.\n12. Twelfth item"
    )


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

    monkeypatch.setattr("app.ingestion.worker._handler_for", lambda _stage: fail_flush)
    result = run_once(db, worker_id="worker-test", task_type="verifying_upload")

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    db.refresh(source)
    assert source.title == original_title
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details["error_type"] == "DataError"


def test_worker_renders_confirmed_pages_and_stores_native_extraction_artifacts(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages(
        [
            f"Official copy {uuid.uuid4().hex}",
            f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}\n"
            "37. Right to private and family life",
        ]
    )
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    create_run_steps(db, run)
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=1,
            role=PageRole.FRONT_MATTER,
            inclusion_status=PageInclusionStatus.EXCLUDED,
            inclusion_reason="Front matter excluded",
        ),
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=2,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.INCLUDED,
            inclusion_reason="Legal body confirmed",
        ),
    ]
    db.add_all(pages)
    db.commit()
    rendering_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.RENDERING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=rendering_step,
        task_type=IngestionStage.RENDERING.value,
        idempotency_key=f"{run.id}:render",
        payload={"source_document_id": str(source.id)},
    )

    rendered = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.RENDERING.value,
    )
    extracted = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
    )

    assert rendered is not None
    assert extracted is not None
    assert rendered.stage == IngestionStage.RENDERING
    assert extracted.stage == IngestionStage.NATIVE_EXTRACTION

    db.refresh(run)
    assert run.current_stage == IngestionStage.NORMALIZING
    skipped_steps = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage.in_(
                [IngestionStage.LOCAL_OCR, IngestionStage.MANAGED_OCR]
            ),
        )
    ).all()
    assert {step.status for step in skipped_steps} == {IngestionStepStatus.SKIPPED}
    page_records = db.exec(
        select(SourcePage)
        .where(SourcePage.run_id == run.id)
        .order_by(SourcePage.page_number)
    ).all()
    assert all(page.thumbnail_key for page in page_records)
    assert page_records[1].quality_signals
    assert page_records[1].quality_signals["native_extraction"]["span_count"] >= 1

    artifacts = db.exec(
        select(IngestionArtifact)
        .where(IngestionArtifact.run_id == run.id)
        .order_by(IngestionArtifact.artifact_type)
    ).all()
    thumbnail_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.PAGE_THUMBNAIL
    ]
    raw_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.RAW_EXTRACTION
    ]
    assert len(thumbnail_artifacts) == 2
    assert len(raw_artifacts) == 1
    assert raw_artifacts[0].source_page_id == page_records[1].id

    next_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.NORMALIZING.value,
        )
    ).one()
    assert next_task.status == IngestionTaskStatus.PENDING


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


def test_worker_normalizes_parses_candidates_and_blocks_for_review(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=5)

    assert [result.stage for result in results] == [
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    ]
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW

    normalized_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.NORMALIZED_PAGES,
        )
    ).one()
    assert normalized_artifact.artifact_metadata == {
        "normalizer_version": NORMALIZER_VERSION,
        "page_count": 1,
    }

    candidates = db.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.run_id == run.id)
        .order_by(ExtractionCandidate.sort_key)
    ).all()
    instrument_slug = _instrument_slug(db, source)
    assert [candidate.canonical_path for candidate in candidates] == [
        f"{instrument_slug}.chapter4",
        f"{instrument_slug}.chapter4.part1",
        f"{instrument_slug}.chapter4.part1.section37",
        f"{instrument_slug}.chapter4.part1.section37.subsection1",
    ]
    section = candidates[2]
    assert section.raw_text == (
        "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert section.normalized_text == normalize_legal_text(section.raw_text)
    assert section.text_sha256 == legal_text_sha256(section.raw_text)
    assert section.source_spans
    assert section.source_spans[0]["bbox"]["x1"] > section.source_spans[0]["bbox"]["x0"]
    assert section.ancestor_headings == ["Fundamental Rights", "Rights"]
    assert section.parser_version == PARSER_VERSION
    assert section.extractor_confidence == 0.96
    assert section.status == ExtractionCandidateStatus.NEEDS_REVIEW
    subsection = candidates[-1]
    assert subsection.kind == ProvisionKind.SUBSECTION
    assert subsection.parent_candidate_id == section.id
    assert subsection.raw_text == (
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert subsection.ancestor_headings == [
        "Fundamental Rights",
        "Rights",
        "Right to private and family life",
    ]

    review_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.REVIEW,
        )
    ).one()
    assert review_step.status == IngestionStepStatus.BLOCKED


def test_parse_stage_auto_approves_only_with_gold_calibration_policy(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    instrument_slug = _instrument_slug(db, source)
    section_text = (
        "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    gold_dataset_version = f"ng-constitution-gold-{uuid.uuid4().hex}"
    _create_legal_grade_dataset(
        db,
        version=gold_dataset_version,
        canonical_path=f"{instrument_slug}.chapter4.part1.section37",
        section_number="37",
        text=section_text,
        source_page_start=1,
        source_page_end=1,
        source_spans=[
            {
                "page_number": 1,
                "bbox": {"x0": 36.0, "y0": 422.0, "x1": 240.0, "y1": 434.0},
            },
            {
                "page_number": 1,
                "bbox": {"x0": 36.0, "y0": 408.0, "x1": 240.0, "y1": 420.0},
            },
        ],
    )
    run.pipeline_config = {
        "instrument_parser": "constitution",
        "auto_approval_policy": {
            "enabled": True,
            "gold_dataset_version": gold_dataset_version,
        },
    }
    db.add(run)
    db.commit()
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize-auto-approval",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    ]
    candidates = db.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    assert candidates
    assert all(
        candidate.status == ExtractionCandidateStatus.AUTO_APPROVED
        for candidate in candidates
    )
    parsing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.PARSING_STRUCTURE,
        )
    ).one()
    assert parsing_step.metrics
    assert parsing_step.metrics["auto_approved_count"] == len(candidates)
    quality_metrics = parsing_step.metrics["legal_grade_quality"]
    assert quality_metrics["metrics_source"] == "computed_gold_evaluation"
    assert quality_metrics["complete_section_number_coverage"] is True
    assert quality_metrics["complete_source_coordinate_coverage"] is True
    assert quality_metrics["character_accuracy"] == 1
    assert quality_metrics["meaning_changing_token_errors"] == 0
    db.refresh(run)
    assert run.pipeline_config
    policy = run.pipeline_config["auto_approval_policy"]
    assert policy["metrics_source"] == "computed_gold_evaluation"
    assert policy["passed_legal_grade_gate"] is True
    validation_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.VALIDATING_DOCUMENT,
        )
    ).one()
    assert validation_step.metrics
    assert validation_step.metrics["source_verification_required"] is True
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW


def test_parse_stage_rejects_metrics_only_auto_approval_policy(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    instrument_slug = _instrument_slug(db, source)
    run.pipeline_config = {
        "instrument_parser": "constitution",
        "auto_approval_policy": {
            "enabled": True,
            "gold_dataset_version": "ng-constitution-gold-v1",
            "complete_section_number_coverage": True,
            "character_accuracy": 1,
            "meaning_changing_token_errors": 0,
            "gold_provisions": [
                {
                    "canonical_path": f"{instrument_slug}.chapter4.part1.section37",
                    "section_number": "37",
                    "text": (
                        "Right to private and family life\n"
                        "(1) The privacy of citizens is hereby guaranteed and protected."
                    ),
                }
            ],
        },
    }
    db.add(run)
    db.commit()
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize-metrics-only-auto-approval",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    ]
    candidates = db.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    assert candidates
    assert all(
        candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
        for candidate in candidates
    )
    parsing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.PARSING_STRUCTURE,
        )
    ).one()
    assert parsing_step.metrics
    assert parsing_step.metrics["auto_approved_count"] == 0
    assert parsing_step.metrics["legal_grade_quality"] is None


def test_parse_stage_creates_blocking_issue_for_missing_source_spans(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text="CHAPTER IV - Fundamental Rights\n37. Broken text (missing close",
        spans=[],
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )

    run_until_idle(db, worker_id="worker-test", max_tasks=5)

    section = db.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == run.id,
            ExtractionCandidate.raw_text != None,  # noqa: E711
        )
    ).one()
    assert section.blocking_issue_count == 2
    issues = db.exec(
        select(ReviewIssue)
        .where(ReviewIssue.candidate_id == section.id)
        .order_by(ReviewIssue.issue_type)
    ).all()
    assert [issue.issue_type for issue in issues] == [
        "low_parser_confidence",
        "missing_source_spans",
        "unbalanced_punctuation",
    ]
    assert [issue.blocking for issue in issues] == [False, True, True]


def test_parse_stage_blocks_source_spans_that_do_not_cover_candidate_text(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "37. Right to private and family life\n"
            "The privacy of citizens is hereby guaranteed."
        ),
        spans=[
            {
                "text": "Official Gazette cover line",
                "bbox": {"x0": 36.0, "y0": 450.0, "x1": 240.0, "y1": 462.0},
                "reading_order": 1,
            }
        ],
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )

    run_until_idle(db, worker_id="worker-test", max_tasks=5)

    section = db.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == run.id,
            ExtractionCandidate.kind == ProvisionKind.SECTION,
        )
    ).one()
    issue = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == section.id,
            ReviewIssue.issue_type == "source_span_coverage",
        )
    ).one()
    assert issue.blocking is True
    assert issue.evidence
    assert issue.evidence["coverage"] == 0
    assert issue.evidence["precision"] == 0


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


@pytest.mark.parametrize("corpus_status", [LegalStatus.CURRENT, LegalStatus.HISTORICAL])
def test_worker_materializes_approved_candidates_and_builds_retrieval_artifact(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus_status: LegalStatus,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    run.pipeline_config = {"corpus_legal_status": corpus_status.value}
    db.add(run)
    db.commit()
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )
    run_until_idle(db, worker_id="worker-test", max_tasks=3)
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    candidates = db.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.run_id == run.id)
        .order_by(ExtractionCandidate.sort_key)
    ).all()
    for candidate in candidates:
        candidate.status = ExtractionCandidateStatus.APPROVED
        candidate.blocking_issue_count = 0
        db.add(candidate)
    db.add(source)
    db.commit()
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=2)

    assert [result.stage for result in results] == [
        IngestionStage.MATERIALIZING,
        IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
    ]
    assert [result.task_status for result in results] == [
        IngestionTaskStatus.SUCCEEDED,
        IngestionTaskStatus.SUCCEEDED,
    ]
    db.refresh(run)
    assert run.status == IngestionRunStatus.READY_TO_EMBED
    assert run.current_stage == IngestionStage.EMBEDDING

    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provisions = db.exec(
        select(Provision)
        .where(Provision.instrument_id == instrument.id)
        .order_by(Provision.sort_key)
    ).all()
    assert [str(provision.kind) for provision in provisions] == [
        ProvisionKind.CHAPTER.value,
        ProvisionKind.PART.value,
        ProvisionKind.SECTION.value,
        ProvisionKind.SUBSECTION.value,
    ]
    assert provisions[1].parent_id == provisions[0].id
    assert provisions[2].parent_id == provisions[1].id
    assert provisions[3].parent_id == provisions[2].id

    section_version = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == provisions[2].id
        )
    ).one()
    assert section_version.provision_id == provisions[2].id
    assert section_version.text == (
        "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert section_version.valid_from == date(1999, 5, 29)
    assert section_version.legal_status == corpus_status
    subsection_version = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == provisions[3].id
        )
    ).one()
    assert subsection_version.text == (
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )

    release = db.exec(
        select(CorpusRelease).where(CorpusRelease.version == f"draft-{run.id.hex[:12]}")
    ).one()
    assert release.status == CorpusReleaseStatus.BUILDING
    assert release.source_manifest_hash
    entries = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    assert {entry.provision_version_id for entry in entries} == {
        section_version.id,
        subsection_version.id,
    }
    assert {entry.ingestion_run_id for entry in entries} == {run.id}

    artifacts = db.exec(
        select(IngestionArtifact).where(IngestionArtifact.run_id == run.id)
    ).all()
    artifact_types = {artifact.artifact_type for artifact in artifacts}
    assert IngestionArtifactType.RELEASE_MANIFEST in artifact_types
    assert IngestionArtifactType.RETRIEVAL_DOCUMENTS in artifact_types
    retrieval_artifact = next(
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.RETRIEVAL_DOCUMENTS
    )
    retrieval_payload = json.loads(
        LocalBlobStore(tmp_path).read_bytes(retrieval_artifact.storage_key)
    )
    assert retrieval_payload["document_count"] == 2
    document = next(
        item
        for item in retrieval_payload["documents"]
        if item["citation"] == "Section 37"
    )
    assert document["citation"] == "Section 37"
    assert document["ancestor_headings"] == ["Fundamental Rights", "Rights"]
    assert (
        document["authoritative_text"] == "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert "Section 37" in document["retrieval_text"]
    assert document["payload"]["legal_status"] == corpus_status.value

    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    assert embedding_step.status == IngestionStepStatus.BLOCKED


def test_historical_materialization_does_not_reuse_current_law(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=_pdf_with_pages([uuid.uuid4().hex])
    )
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    candidate = _approved_candidate(db, run=run, source=source, text="Source wording")
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        canonical_path=candidate.canonical_path,
        sort_key="037",
    )
    db.add(provision)
    db.flush()
    current = ProvisionVersion(
        provision_id=provision.id,
        text="Source wording",
        normalized_text="source wording",
        valid_from=date(1999, 5, 29),
        source_document_id=source.id,
        text_sha256=legal_text_sha256("Source wording"),
    )
    db.add(current)
    db.commit()
    with pytest.raises(IngestionWorkerError, match="separate provision identity"):
        _upsert_historical_version_from_candidate(
            db,
            source=source,
            instrument=instrument,
            provision=provision,
            candidate=candidate,
            text="Source wording",
        )
    assert current.legal_status == LegalStatus.CURRENT
    assert current.valid_until is None


def test_materialization_release_snapshot_is_cumulative_across_sources_and_runs(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    first_pdf = _pdf_with_pages([f"37. First source {uuid.uuid4().hex}"])
    first_source, first_run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=first_pdf
    )
    _clear_run_tasks(db, first_run)
    first_source.verification_status = VerificationStatus.VERIFIED
    instrument = db.get(LegalInstrument, first_source.legal_instrument_id)
    assert instrument
    first_provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="037",
    )
    db.add(first_provision)
    db.commit()
    db.refresh(first_provision)
    first_version = ProvisionVersion(
        provision_id=first_provision.id,
        text="Existing current Section 37 text.",
        normalized_text=normalize_legal_text("Existing current Section 37 text."),
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=first_source.id,
        source_page_start=1,
        source_page_end=1,
        text_sha256=legal_text_sha256("Existing current Section 37 text."),
    )
    db.add(first_version)
    db.commit()
    db.refresh(first_version)
    first_candidate = _approved_candidate(
        db,
        run=first_run,
        source=first_source,
        number="37",
        canonical_path=first_provision.canonical_path,
        heading=first_provision.heading or "",
        sort_key=first_provision.sort_key,
        text=first_version.text,
    )
    first_candidate.status = ExtractionCandidateStatus.MATERIALIZED
    first_candidate.materialized_provision_id = first_provision.id
    first_candidate.materialized_version_id = first_version.id
    db.add(first_source)
    db.add(first_candidate)
    db.commit()

    second_pdf = _pdf_with_pages([f"38. Second source {uuid.uuid4().hex}"])
    second_source, second_run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=second_pdf, instrument=instrument
    )
    _clear_run_tasks(db, second_run)
    second_source.verification_status = VerificationStatus.VERIFIED
    second_candidate = _approved_candidate(
        db,
        run=second_run,
        source=second_source,
        number="38",
        canonical_path=f"{instrument.slug}.section38",
        heading="Right to freedom of thought",
        sort_key="038",
        text="New current Section 38 text.",
    )
    db.add(second_source)
    db.commit()
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == second_run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=second_run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{second_run.id}:materialize-cumulative",
        payload={"source_document_id": str(second_source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.stage == IngestionStage.MATERIALIZING
    db.refresh(second_candidate)
    assert second_candidate.materialized_version_id
    release = db.exec(
        select(CorpusRelease).where(
            CorpusRelease.version == f"draft-{second_run.id.hex[:12]}"
        )
    ).one()
    entries = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    entries_by_version = {entry.provision_version_id: entry for entry in entries}
    assert set(entries_by_version) == {
        first_version.id,
        second_candidate.materialized_version_id,
    }
    assert entries_by_version[first_version.id].source_document_id == first_source.id
    assert entries_by_version[first_version.id].ingestion_run_id == first_run.id
    assert (
        entries_by_version[second_candidate.materialized_version_id].source_document_id
        == second_source.id
    )
    assert (
        entries_by_version[second_candidate.materialized_version_id].ingestion_run_id
        == second_run.id
    )
    assert release.validation_report
    assert release.validation_report["source_document_count"] == 2
    assert set(release.validation_report["ingestion_run_ids"]) == {
        str(first_run.id),
        str(second_run.id),
    }
    manifest_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == second_run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.RELEASE_MANIFEST,
        )
    ).one()
    manifest = json.loads(
        LocalBlobStore(tmp_path).read_bytes(manifest_artifact.storage_key)
    )
    assert set(manifest["source_document_ids"]) == {
        str(first_source.id),
        str(second_source.id),
    }
    assert set(manifest["ingestion_run_ids"]) == {
        str(first_run.id),
        str(second_run.id),
    }
    assert {
        source_doc["source_document_id"] for source_doc in manifest["source_documents"]
    } == {str(first_source.id), str(second_source.id)}


def test_materialization_requires_document_source_verification(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf, max_attempts=1)
    _clear_run_tasks(db, run)
    candidate = _approved_candidate(db, run=run, source=source, text="Verified text")
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    materializing_task = enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-unverified",
        payload={"source_document_id": str(source.id)},
    )
    materializing_task.max_attempts = 1
    db.add(materializing_task)
    db.commit()

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(candidate)
    assert candidate.materialized_version_id is None
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "verified" in run.error_details["message"]


def test_materialization_skips_rejected_candidates_and_their_findings(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf, max_attempts=1)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    db.add(source)
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
    rejected.blocking_issue_count = 1
    db.add(rejected)
    db.add(
        ReviewIssue(
            candidate_id=rejected.id,
            issue_type="unbalanced_punctuation",
            blocking=True,
            message="Unbalanced brackets in a rejected duplicate.",
        )
    )
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    db.commit()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-with-rejected",
        payload={"source_document_id": str(source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.task_status == IngestionTaskStatus.SUCCEEDED
    db.refresh(approved)
    db.refresh(rejected)
    assert approved.status == ExtractionCandidateStatus.MATERIALIZED
    assert approved.materialized_version_id is not None
    assert rejected.status == ExtractionCandidateStatus.REJECTED
    assert rejected.materialized_provision_id is None


def test_rematerialization_after_review_correction_stores_a_new_manifest(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"65. Interpretation {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf, max_attempts=1)
    _clear_run_tasks(db, run)
    # As-enacted Act text: the release holds exactly what this run materialized.
    run.pipeline_config = {**(run.pipeline_config or {}), "instrument_parser": "act"}
    db.add(run)
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    db.add(source)
    section = _approved_candidate(db, run=run, source=source, text="Section text")
    fake = _approved_candidate(
        db,
        run=run,
        source=source,
        text="(a) part of a definition",
        canonical_path=f"{section.canonical_path}.paragrapha",
        sort_key="999",
    )
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    db.commit()

    for attempt in ("first", "corrected"):
        if attempt == "corrected":
            # A reviewer rejects an item after the first materialization.
            fake.status = ExtractionCandidateStatus.REJECTED
            db.add(fake)
            release = db.exec(
                select(CorpusRelease).where(
                    CorpusRelease.version == f"draft-{run.id.hex[:12]}"
                )
            ).one()
            for entry in db.exec(
                select(CorpusReleaseEntry).where(
                    CorpusReleaseEntry.release_id == release.id,
                    CorpusReleaseEntry.provision_version_id
                    == fake.materialized_version_id,
                )
            ).all():
                db.delete(entry)
            db.commit()
        enqueue_task(
            db,
            run=run,
            step=materializing_step,
            task_type=IngestionStage.MATERIALIZING.value,
            idempotency_key=f"{run.id}:materialize-{attempt}",
            payload={"source_document_id": str(source.id)},
        )
        result = run_once(db, worker_id="worker-test")
        assert result is not None
        assert result.task_status == IngestionTaskStatus.SUCCEEDED
        _clear_run_tasks(db, run)

    manifests = db.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.RELEASE_MANIFEST,
        )
        .order_by(col(IngestionArtifact.created_at))
    ).all()
    assert len(manifests) == 2
    latest = json.loads(LocalBlobStore(tmp_path).read_bytes(manifests[-1].storage_key))
    assert len(latest["entries"]) == 1


def test_materialization_blocks_changed_current_law_without_revision_metadata(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    db.add(source)
    db.commit()
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Bad old heading",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="999",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    bad_version = ProvisionVersion(
        provision_id=provision.id,
        text="Incorrect seeded text.",
        normalized_text="incorrect seeded text.",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        text_sha256=legal_text_sha256("Incorrect seeded text."),
    )
    db.add(bad_version)
    db.commit()
    db.refresh(bad_version)
    candidate = _approved_candidate(
        db,
        run=run,
        source=source,
        canonical_path=provision.canonical_path,
        heading="Right to private and family life",
        sort_key="037",
        text="Correct official text.",
    )
    db.add(
        CandidateRevision(
            candidate_id=candidate.id,
            revision_number=2,
            previous_text=candidate.raw_text,
            revised_text="Correct official text after review.",
            reason="Reviewer corrected seeded text.",
        )
    )
    candidate.revision_number = 2
    db.add(candidate)
    db.commit()
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-replace",
        payload={"source_document_id": str(source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.stage == IngestionStage.MATERIALIZING
    assert result.task_status == IngestionTaskStatus.SUCCEEDED
    db.refresh(provision)
    db.refresh(bad_version)
    db.refresh(candidate)
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW
    assert provision.heading == "Bad old heading"
    assert provision.sort_key == "999"
    assert bad_version.text == "Incorrect seeded text."
    assert bad_version.legal_status == LegalStatus.CURRENT
    assert bad_version.valid_until is None
    assert candidate.materialized_version_id is None
    assert candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    assert db.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == provision.id)
    ).all() == [bad_version]
    issue = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "changed_current_law_text",
        )
    ).one()
    assert issue.blocking
    assert issue.evidence
    assert issue.evidence["current_version_id"] == str(bad_version.id)


def test_materialization_supersedes_current_version_for_classified_legal_revision(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    source.is_legal_revision = True
    source.legal_revision_effective_at = date(2024, 1, 1)
    db.add(source)
    db.commit()
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    current_version = ProvisionVersion(
        provision_id=provision.id,
        text="Original current text.",
        normalized_text="original current text.",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        text_sha256=legal_text_sha256("Original current text."),
    )
    db.add(current_version)
    db.commit()
    db.refresh(current_version)
    candidate = _approved_candidate(
        db,
        run=run,
        source=source,
        canonical_path=provision.canonical_path,
        text="Revised current text.",
    )
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-legal-revision",
        payload={"source_document_id": str(source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.stage == IngestionStage.MATERIALIZING
    db.refresh(current_version)
    db.refresh(candidate)
    assert current_version.text == "Original current text."
    assert current_version.legal_status == LegalStatus.SUPERSEDED
    assert current_version.valid_until == date(2024, 1, 1)
    versions = db.exec(
        select(ProvisionVersion)
        .where(ProvisionVersion.provision_id == provision.id)
        .order_by(ProvisionVersion.revision_number)
    ).all()
    assert len(versions) == 2
    assert versions[1].text == "Revised current text."
    assert versions[1].legal_status == LegalStatus.CURRENT
    assert versions[1].valid_from == date(2024, 1, 1)
    assert versions[1].supersedes_id == current_version.id
    assert candidate.materialized_version_id == versions[1].id


def test_active_embedding_profiles_must_share_one_persisted_benchmark_dataset(
    db: Session,
) -> None:
    for existing_profile in db.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active == True)  # noqa: E712
    ).all():
        existing_profile.is_active = False
        db.add(existing_profile)
    dataset_version = f"golden-{uuid.uuid4().hex}"
    _create_retrieval_benchmark_dataset(
        db,
        version=dataset_version,
        canonical_path="constitution.1999.chapter4.section37",
    )
    openai_profile = EmbeddingProfile(
        name=f"openai-large-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="text-embedding-3-large",
        model_revision="pinned-openai",
        vector_dimensions=1024,
        configuration={"benchmark_dataset_version": dataset_version},
    )
    bge_profile = EmbeddingProfile(
        name=f"bge-m3-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
        model_name="BAAI/bge-m3",
        model_revision="pinned-bge",
        vector_dimensions=1024,
        configuration={"benchmark_dataset_version": dataset_version},
    )
    db.add_all([openai_profile, bge_profile])
    db.commit()

    release = CorpusRelease(version=f"draft-{uuid.uuid4().hex}")
    recorded, queries = _benchmark_dataset_for_embedding_profiles(
        db, [openai_profile, bge_profile], release
    )
    assert recorded == dataset_version
    assert [query.item_key for query in queries] == ["privacy-exact-reference"]

    bge_profile.configuration = {
        "benchmark_dataset_version": f"other-{uuid.uuid4().hex}"
    }
    db.add(bge_profile)
    db.commit()
    with pytest.raises(IngestionWorkerError, match="same benchmark dataset"):
        _benchmark_dataset_for_embedding_profiles(
            db, [openai_profile, bge_profile], release
        )


def test_embedding_benchmark_grades_each_release_instrument_with_its_own_dataset(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, _run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path, create_benchmark_dataset=False
    )
    constitution = db.get(LegalInstrument, source.legal_instrument_id)
    assert constitution
    pinned_version = str(profile.configuration["benchmark_dataset_version"])
    _create_retrieval_benchmark_dataset(
        db,
        version=pinned_version,
        canonical_path=f"{constitution.slug}.section37",
        instrument_slug=constitution.slug,
    )
    act = LegalInstrument(
        slug=f"act-{uuid.uuid4().hex[:12]}",
        title="Test Act",
        instrument_type=InstrumentType.ACT,
    )
    db.add(act)
    db.commit()
    act_provision = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SECTION,
        number="1",
        canonical_path=f"{act.slug}.section1",
        sort_key="001",
    )
    db.add(act_provision)
    db.commit()
    act_text = "This Act applies to criminal trials."
    act_version = ProvisionVersion(
        provision_id=act_provision.id,
        text=act_text,
        normalized_text=normalize_legal_text(act_text),
        valid_from=date(2015, 5, 13),
        legal_status=LegalStatus.HISTORICAL,
        source_document_id=source.id,
        text_sha256=legal_text_sha256(act_text),
    )
    db.add(act_version)
    db.commit()
    db.add(
        CorpusReleaseEntry(
            release_id=release.id,
            provision_version_id=act_version.id,
            source_document_id=source.id,
        )
    )
    db.commit()

    # An Act in the release without its own benchmark cannot be graded.
    with pytest.raises(IngestionWorkerError, match=f"{act.slug} needs exactly one"):
        _benchmark_dataset_for_embedding_profiles(db, [profile], release)

    act_version_name = f"act-golden-{uuid.uuid4().hex[:8]}"
    _create_retrieval_benchmark_dataset(
        db,
        version=act_version_name,
        canonical_path=act_provision.canonical_path,
        instrument_slug=act.slug,
    )

    recorded, queries = _benchmark_dataset_for_embedding_profiles(
        db, [profile], release
    )

    by_slug = {act.slug: act_version_name, constitution.slug: pinned_version}
    expected = [by_slug[slug] for slug in sorted(by_slug)]
    assert recorded == "+".join(expected)
    assert sorted(query.item_key for query in queries) == sorted(
        f"{version}/privacy-exact-reference" for version in expected
    )
    assert {path for query in queries for path in query.expected_canonical_paths} == {
        f"{constitution.slug}.section37",
        act_provision.canonical_path,
    }


def test_embedding_run_records_every_benchmark_of_a_composite_release(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, _run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path, create_benchmark_dataset=False
    )
    constitution = db.get(LegalInstrument, source.legal_instrument_id)
    assert constitution
    suffix = uuid.uuid4().hex[:8]
    versions = [
        f"{name}-{suffix}"
        for name in (
            "acja-2015-retrieval-v1",
            "constitution-source-edition-retrieval-2026-10-05-v1",
            "copyright-act-2022-retrieval-v1",
            "employees-compensation-act-2010-retrieval-v1",
            "nigeria-tax-act-2025-retrieval-v1",
            "police-act-2020-retrieval-v1",
        )
    ]
    for version in versions:
        _create_retrieval_benchmark_dataset(
            db, version=version, canonical_path=f"{constitution.slug}.section37"
        )
    pinned_version = str(profile.configuration["benchmark_dataset_version"])
    _create_retrieval_benchmark_dataset(
        db,
        version=pinned_version,
        canonical_path=f"{constitution.slug}.section37",
        instrument_slug=constitution.slug,
    )
    monkeypatch.setattr(
        "app.ingestion.worker._benchmark_versions_for_release",
        lambda *_args: versions,
    )

    recorded, queries = _benchmark_dataset_for_embedding_profiles(
        db, [profile], release
    )

    assert recorded == "+".join(versions)
    assert len(recorded) > 128
    assert len(queries) == len(versions)
    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        benchmark_dataset_version=recorded,
    )
    db.add(embedding_run)
    db.commit()
    db.refresh(embedding_run)
    assert embedding_run.benchmark_dataset_version == recorded

    monkeypatch.setattr(
        "app.ingestion.worker.RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH", len(recorded) - 1
    )
    with pytest.raises(IngestionWorkerError, match="too long to record"):
        _benchmark_dataset_for_embedding_profiles(db, [profile], release)


def test_worker_embeds_indexes_and_validates_pgvector_dataset(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RETRIEVAL_INDEX_BACKEND", "pgvector")
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    release.validation_report = {
        "unresolved_gates": [
            "ready_retrieval_index_build_missing",
            "unrelated_review_gate",
        ]
    }
    db.add(release)
    db.commit()

    class FakeEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            if texts == ["Section 37\nRight to private and family life"]:
                return EmbeddingBatch(
                    provider="fake",
                    model_name=profile.model_name,
                    model_revision=profile.model_revision,
                    vectors=[[1.0] + [0.0] * 1023],
                    cost_usd=0.01,
                    metrics={"batch": "documents"},
                )
            assert texts == ["Which section protects privacy?"]
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023],
                cost_usd=0.02,
                metrics={"batch": "queries"},
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: FakeEmbeddingProvider(),
    )
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    run.pipeline_config = {"auto_start_embedding": True}
    db.add(run)
    db.commit()
    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=embedding_step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:pgvector-embedding",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.EMBEDDING,
        IngestionStage.INDEXING,
        IngestionStage.VALIDATING_INDEX,
    ]
    db.refresh(run)
    db.refresh(release)
    assert run.status == IngestionRunStatus.READY_TO_PUBLISH
    assert run.current_stage == IngestionStage.PUBLISHING
    assert release.embedding_model == "fake-large"
    assert release.embedding_model_version == "pinned-test"
    assert release.validation_report

    embedding_run = db.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.profile_id == profile.id,
        )
    ).one()
    assert embedding_run.status == EmbeddingRunStatus.SUCCEEDED
    assert embedding_run.selected_for_release
    assert embedding_run.recall_at_10 == 1
    assert embedding_run.ndcg_at_10 == 1
    assert embedding_run.cost_usd == 0.03
    assert (
        embedding_run.benchmark_dataset_version
        == profile.configuration["benchmark_dataset_version"]
    )
    assert embedding_run.metrics
    assert embedding_run.metrics["benchmark_query_count"] == 1
    assert embedding_run.metrics["document_embedding_metrics"] == {"batch": "documents"}
    assert embedding_run.metrics["query_embedding_metrics"] == {"batch": "queries"}
    embedding_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).one()
    assert embedding_artifact.artifact_metadata
    assert embedding_artifact.artifact_metadata["embedding_run_id"] == str(
        embedding_run.id
    )
    artifact_payload = json.loads(
        LocalBlobStore(tmp_path).read_bytes(embedding_artifact.storage_key)
    )
    assert artifact_payload["benchmark"]["recall_at_10"] == 1
    assert artifact_payload["benchmark"]["benchmark_query_count"] == 1

    build = db.exec(
        select(RetrievalIndexBuild).where(RetrievalIndexBuild.release_id == release.id)
    ).one()
    assert build.status == VectorIndexStatus.READY
    assert build.stored_segment_count == 1
    assert build.stored_embedding_count == 1
    db.refresh(release)
    assert release.validation_report["unresolved_gates"] == ["unrelated_review_gate"]
    segment = db.exec(
        select(RetrievalSegment).where(RetrievalSegment.release_id == release.id)
    ).one()
    embedding = db.exec(
        select(RetrievalEmbedding).where(
            RetrievalEmbedding.embedding_run_id == build.embedding_run_id
        )
    ).one()
    assert embedding.vector_dimensions == 1024
    assert (
        dense_search(
            db,
            release_id=release.id,
            embedding_run_id=build.embedding_run_id,
            query_vector=[1.0] + [0.0] * 1023,
        )[0][0].id
        == segment.id
    )
    assert (
        hybrid_search(
            db,
            release_id=release.id,
            embedding_run_id=build.embedding_run_id,
            query_vector=[1.0] + [0.0] * 1023,
            query="privacy",
            top_k=1,
        )[0].segment.id
        == segment.id
    )


def test_api_upload_worker_publish_and_production_search_end_to_end(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise one source across the real API, worker, release, and search paths."""
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "RETRIEVAL_INDEX_BACKEND", "pgvector")

    for profile in db.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active == True)  # noqa: E712
    ).all():
        profile.is_active = False
        db.add(profile)
    db.commit()

    pdf = _pdf_with_pages(
        [
            "37. Right to private and family life. The privacy of citizens, their homes and correspondence is guaranteed."
        ]
    )
    slug = f"constitution-e2e-{uuid.uuid4().hex}"
    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"upload-{uuid.uuid4().hex}",
            "expected_size": len(pdf),
            "expected_sha256": _sha256(pdf),
            "original_filename": "constitution.pdf",
            "mime_type": "application/pdf",
            "instrument_slug": slug,
            "instrument_title": "Constitution of the Federal Republic of Nigeria 1999",
            "instrument_short_title": "CFRN 1999",
            "instrument_year": 1999,
            "instrument_status": InstrumentStatus.ENACTED.value,
            "enacted_at": "1999-05-29",
            "effective_at": "1999-05-29",
            "source_title": "Official Constitution PDF",
            "authority": "Official Gazette",
            "source_url": f"https://example.test/{slug}.pdf",
            "source_tier": SourceTier.OFFICIAL.value,
            "published_at": "1999-05-29",
            "retrieved_at": date.today().isoformat(),
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    upload = upload_response.json()
    upload_id = uuid.UUID(upload["id"])
    put_response = client.put(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/object",
        headers={**superuser_token_headers, "content-type": "application/pdf"},
        content=pdf,
    )
    assert put_response.status_code == 204, put_response.text
    upload_record = db.get(SourceUpload, upload_id)
    assert upload_record
    db.refresh(upload_record)
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": upload_record.lock_version,
            "actual_sha256": _sha256(pdf),
        },
    )
    assert complete_response.status_code == 200, complete_response.text
    completion = complete_response.json()
    assert completion["source_document"] is None
    run_id = uuid.UUID(completion["run"]["id"])

    first_results = run_until_idle(db, worker_id="e2e-worker", max_tasks=20)
    assert first_results
    run = db.get(IngestionRun, run_id)
    assert run
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    source = db.exec(
        select(SourceDocument).where(SourceDocument.id == run.source_document_id)
    ).one()
    pages = db.exec(
        select(SourcePage)
        .where(SourcePage.run_id == run.id)
        .order_by(SourcePage.page_number)
    ).all()
    assert pages
    page_selection = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"pages-{uuid.uuid4().hex}",
            "expected_run_version": run.lock_version,
            "pages": [
                {
                    "page_number": page.page_number,
                    "inclusion_status": PageInclusionStatus.INCLUDED.value,
                    "inclusion_reason": "Included by end-to-end acceptance test",
                    "expected_version": page.lock_version,
                }
                for page in pages
            ],
        },
    )
    assert page_selection.status_code == 200, page_selection.text

    run_until_idle(db, worker_id="e2e-worker", max_tasks=30)
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    review_response = client.get(
        f"{settings.API_V1_STR}/admin/review-items",
        headers=superuser_token_headers,
        params={"run_id": str(run.id)},
    )
    assert review_response.status_code == 200, review_response.text
    review_items = review_response.json()["data"]
    assert review_items
    for item in review_items:
        decision_response = client.post(
            f"{settings.API_V1_STR}/admin/review-items/{item['id']}/decision",
            headers=superuser_token_headers,
            json={
                "idempotency_key": f"approve-{item['id']}-{uuid.uuid4().hex}",
                "expected_version": item["lock_version"],
                "decision": ReviewDecisionType.APPROVE.value,
                "reason": "Approved by end-to-end acceptance test",
            },
        )
        assert decision_response.status_code == 200, decision_response.text

    db.refresh(source)
    verify_response = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"verify-{uuid.uuid4().hex}",
            "expected_version": source.lock_version,
            "reason": "Official source reviewed by end-to-end acceptance test",
        },
    )
    assert verify_response.status_code == 200, verify_response.text

    run_until_idle(db, worker_id="e2e-worker", max_tasks=30)
    db.refresh(run)
    assert run.status == IngestionRunStatus.READY_TO_EMBED
    release = db.exec(
        select(CorpusRelease)
        .join(CorpusReleaseEntry)
        .where(CorpusReleaseEntry.ingestion_run_id == run.id)
    ).one()
    version = db.exec(
        select(ProvisionVersion).where(ProvisionVersion.source_document_id == source.id)
    ).one()
    provision = db.get(Provision, version.provision_id)
    assert provision

    benchmark_version = f"e2e-retrieval-{uuid.uuid4().hex}"
    _create_retrieval_benchmark_dataset(
        db, version=benchmark_version, canonical_path=provision.canonical_path
    )
    profile = EmbeddingProfile(
        name=f"e2e-profile-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="fake-e2e",
        model_revision="pinned-e2e",
        vector_dimensions=1024,
        is_active=True,
        configuration={"benchmark_dataset_version": benchmark_version},
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    class FakeEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            return EmbeddingBatch(
                provider="fake",
                model_name="fake-e2e",
                model_revision="pinned-e2e",
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
                cost_usd=0.01 * len(texts),
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(
        "app.api.routes.search._query_embedding_provider",
        lambda _profile: FakeEmbeddingProvider(),
    )
    db.refresh(run)
    start_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/start-embedding",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"start-embedding-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
        },
    )
    assert start_response.status_code == 200, start_response.text
    embedding_results = run_until_idle(db, worker_id="e2e-worker", max_tasks=5)
    assert [result.stage for result in embedding_results] == [
        IngestionStage.EMBEDDING,
        IngestionStage.INDEXING,
        IngestionStage.VALIDATING_INDEX,
    ]
    db.refresh(run)
    db.refresh(release)
    assert run.status == IngestionRunStatus.READY_TO_PUBLISH
    assert release.status in {
        CorpusReleaseStatus.BUILDING,
        CorpusReleaseStatus.VALIDATING,
    }

    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert validate_response.status_code == 200, validate_response.text
    assert validate_response.json()["status"] == CorpusReleaseStatus.APPROVED.value
    db.refresh(release)
    expected_release_version = release.lock_version

    def publish_once() -> int:
        response = client.post(
            f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
            headers=superuser_token_headers,
            json={
                "idempotency_key": f"publish-{uuid.uuid4().hex}",
                "expected_version": expected_release_version,
                "superuser_override_reason": "Acceptance test actor-separation override",
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        publish_statuses = list(executor.map(lambda _index: publish_once(), range(2)))
    assert sorted(publish_statuses) == [200, 409]

    db.refresh(run)
    db.refresh(release)
    assert run.status == IngestionRunStatus.PUBLISHED
    assert release.status == CorpusReleaseStatus.PRODUCTION
    assert db.exec(
        select(ActiveRetrievalTarget).where(
            ActiveRetrievalTarget.release_id == release.id,
            ActiveRetrievalTarget.index_kind == "enacted",
        )
    ).one()
    assert (
        db.exec(
            select(ReleasePromotionAttempt).where(
                ReleasePromotionAttempt.release_id == release.id
            )
        )
        .one()
        .status
        == "succeeded"
    )

    search_response = client.post(
        f"{settings.API_V1_STR}/legal/search",
        json={"query": "Which section protects privacy?", "top_k": 1},
    )
    assert search_response.status_code == 200, search_response.text
    result = search_response.json()["data"][0]
    assert result["canonical_path"] == provision.canonical_path
    assert result["authoritative_text"] == version.text
    assert result["source_document_id"] == str(source.id)


def test_worker_requires_persisted_embedding_benchmark_dataset(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, _profile = _release_with_retrieval_documents(
        db,
        tmp_path=tmp_path,
        create_benchmark_dataset=False,
    )

    class UnexpectedEmbeddingProvider:
        def embed(self, _texts: list[str]) -> EmbeddingBatch:
            raise AssertionError("Embedding provider should not run without a dataset")

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: UnexpectedEmbeddingProvider(),
    )
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    db.add(run)
    db.commit()
    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    task = enqueue_task(
        db,
        run=run,
        step=embedding_step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:embedding-missing-benchmark-dataset",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )
    task.max_attempts = 1
    db.add(task)
    db.commit()

    result = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.EMBEDDING.value,
    )

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "benchmark dataset" in run.error_details["message"]
    embedding_artifacts = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).all()
    assert embedding_artifacts == []


def _stored_source_and_run(
    db: Session,
    *,
    tmp_path: Path,
    pdf: bytes,
    expected_sha256: str | None = None,
    max_attempts: int = 3,
    instrument: LegalInstrument | None = None,
) -> tuple[SourceDocument, IngestionRun]:
    store = LocalBlobStore(tmp_path)
    quarantine = store.put_quarantine(
        upload_id=f"worker-{uuid.uuid4()}",
        filename="constitution.pdf",
        content=pdf,
        content_type="application/pdf",
    )
    original = store.promote_quarantine_to_original(
        quarantine_key=quarantine.key,
        expected_sha256=quarantine.sha256,
        content_type="application/pdf",
        extension=".pdf",
    )
    if instrument is None:
        instrument = LegalInstrument(
            slug=f"constitution-worker-{uuid.uuid4().hex}",
            title="Constitution of the Federal Republic of Nigeria 1999",
            instrument_type=InstrumentType.CONSTITUTION,
            jurisdiction="NG",
            year=1999,
            status=InstrumentStatus.ENACTED,
        )
        db.add(instrument)
        db.commit()
        db.refresh(instrument)
    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Official Gazette",
        title="Stored worker source",
        source_url="https://example.test/constitution.pdf",
        mime_type="application/pdf",
        sha256=expected_sha256 or original.sha256,
        storage_backend="local",
        storage_key=original.key,
        original_filename="constitution.pdf",
        file_size=original.size_bytes,
        page_count=None,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
        source_tier=SourceTier.OFFICIAL,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    run = IngestionRun(
        source_document_id=source.id,
        status=IngestionRunStatus.QUEUED,
        current_stage=IngestionStage.VERIFYING_UPLOAD,
        pipeline_config={"instrument_parser": "constitution"},
        expected_page_count=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    steps = create_run_steps(db, run)
    verify_step = next(
        step for step in steps if step.stage == IngestionStage.VERIFYING_UPLOAD
    )
    enqueue_task(
        db,
        run=run,
        step=verify_step,
        task_type=IngestionStage.VERIFYING_UPLOAD.value,
        idempotency_key=f"{run.id}:verify",
        payload={"source_document_id": str(source.id)},
        priority=10,
    )
    task = db.exec(select(IngestionTask).where(IngestionTask.run_id == run.id)).one()
    task.max_attempts = max_attempts
    db.add(task)
    db.commit()
    return source, run


def _release_with_retrieval_documents(
    db: Session, *, tmp_path: Path, create_benchmark_dataset: bool = True
) -> tuple[SourceDocument, IngestionRun, CorpusRelease, EmbeddingProfile]:
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    text = "Right to private and family life"
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalize_legal_text(text),
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        source_page_start=1,
        source_page_end=1,
        text_sha256=legal_text_sha256(text),
    )
    release = CorpusRelease(
        version=f"draft-embed-{uuid.uuid4().hex}",
        status=CorpusReleaseStatus.BUILDING,
        source_manifest_hash=legal_text_sha256(text),
        parser_version=PARSER_VERSION,
    )
    benchmark_dataset_version = f"golden-{uuid.uuid4().hex}"
    for existing_profile in db.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active == True)  # noqa: E712
    ).all():
        existing_profile.is_active = False
        db.add(existing_profile)
    profile = EmbeddingProfile(
        name=f"fake-profile-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="fake-large",
        model_revision="pinned-test",
        vector_dimensions=1024,
        configuration={
            "benchmark_dataset_version": benchmark_dataset_version,
            "estimated_cost_usd": 0.01,
            "p95_latency_ms": 120,
        },
    )
    db.add_all([source, version, release, profile])
    db.commit()
    db.refresh(version)
    db.refresh(release)
    db.refresh(profile)
    entry = CorpusReleaseEntry(
        release_id=release.id,
        provision_version_id=version.id,
        source_document_id=source.id,
        ingestion_run_id=run.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    if create_benchmark_dataset:
        _create_retrieval_benchmark_dataset(
            db,
            version=benchmark_dataset_version,
            canonical_path=provision.canonical_path,
        )
    retrieval_payload = {
        "release_id": str(release.id),
        "release_version": release.version,
        "document_count": 1,
        "documents": [
            {
                "id": "retrieval-doc-1",
                "segment_id": f"{provision.canonical_path}:v1:s1",
                "citation": "Section 37",
                "retrieval_text": "Section 37\nRight to private and family life",
                "payload": {
                    "release_version": release.version,
                    "corpus_release_entry_id": str(entry.id),
                    "canonical_path": provision.canonical_path,
                    "kind": ProvisionKind.SECTION.value,
                    "provision_id": str(provision.id),
                    "provision_version_id": str(version.id),
                    "source_document_id": str(source.id),
                    "source_page_start": 1,
                    "source_page_end": 1,
                    "legal_status": LegalStatus.CURRENT.value,
                    "segment_index": 1,
                    "segment_count": 1,
                    "text_sha256": version.text_sha256,
                    "retrieval_text_sha256": legal_text_sha256(
                        "Section 37\nRight to private and family life"
                    ),
                },
            }
        ],
    }
    blob = LocalBlobStore(tmp_path).put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS.value,
        filename="retrieval-documents.json",
        content=json.dumps(retrieval_payload, sort_keys=True).encode(),
        content_type="application/json",
        metadata={"release_id": str(release.id)},
    )
    db.add(
        IngestionArtifact(
            run_id=run.id,
            artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            artifact_metadata={"release_id": str(release.id), "document_count": 1},
        )
    )
    db.commit()
    db.refresh(run)
    return source, run, release, profile


def _create_legal_grade_dataset(
    db: Session,
    *,
    version: str,
    canonical_path: str,
    section_number: str,
    text: str,
    source_page_start: int,
    source_page_end: int,
    source_spans: list[dict[str, object]],
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        version=version,
        name="Nigerian Constitution legal-grade gold provisions",
        dataset_kind=EvaluationDatasetKind.LEGAL_GRADE_EXTRACTION,
        language="en",
        jurisdiction="NG",
        content_sha256=legal_text_sha256(text),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key=section_number,
            item_kind=EvaluationItemKind.GOLD_PROVISION,
            canonical_path=canonical_path,
            provision_kind=ProvisionKind.SECTION,
            section_number=section_number,
            expected_text=text,
            source_page_start=source_page_start,
            source_page_end=source_page_end,
            source_spans=source_spans,
        )
    )
    db.commit()
    return dataset


def _create_retrieval_benchmark_dataset(
    db: Session,
    *,
    version: str,
    canonical_path: str,
    instrument_slug: str | None = None,
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        version=version,
        name="Nigerian Constitution retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        language="en",
        jurisdiction="NG",
        instrument_slug=instrument_slug,
        content_sha256=legal_text_sha256(version + canonical_path),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="privacy-exact-reference",
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            query_text="Which section protects privacy?",
            expected_canonical_paths=[canonical_path],
        )
    )
    db.commit()
    return dataset


def _approved_candidate(
    db: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    text: str,
    number: str = "37",
    canonical_path: str | None = None,
    heading: str = "Right to private and family life",
    sort_key: str = "037",
) -> ExtractionCandidate:
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number=number,
        heading=heading,
        canonical_path=canonical_path or f"{instrument.slug}.section37",
        sort_key=sort_key,
        raw_text=text,
        normalized_text=normalize_legal_text(text),
        text_sha256=legal_text_sha256(text),
        source_page_start=1,
        source_page_end=1,
        source_spans=[
            {"page": 1, "bbox": {"x0": 36.0, "y0": 440.0, "x1": 220.0, "y1": 460.0}}
        ],
        parser_confidence=0.96,
        extractor_confidence=0.96,
        status=ExtractionCandidateStatus.APPROVED,
        blocking_issue_count=0,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def _store_raw_extraction(
    db: Session,
    *,
    tmp_path: Path,
    run: IngestionRun,
    source: SourceDocument,
    page_number: int,
    text: str,
    spans: list[dict[str, object]] | None = None,
    quality_flags: dict[str, object] | None = None,
) -> None:
    page = SourcePage(
        run_id=run.id,
        source_document_id=source.id,
        page_number=page_number,
        role=PageRole.LEGAL_BODY,
        inclusion_status=PageInclusionStatus.INCLUDED,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    span_payload = spans
    if span_payload is None:
        span_payload = [
            {
                "text": line,
                "bbox": {
                    "x0": 36.0,
                    "y0": 450.0 - (index * 14),
                    "x1": 240.0,
                    "y1": 462.0 - (index * 14),
                },
                "reading_order": index + 1,
            }
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]
    payload = {
        "page_number": page_number,
        "method": "native_pdf",
        "provider_version": "pypdf-native-layout-v1",
        "confidence": 0.96,
        "text": text,
        "spans": span_payload,
        "quality_flags": quality_flags
        or {"span_count": len(span_payload), "needs_ocr": False},
    }
    store = LocalBlobStore(tmp_path)
    blob = store.put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RAW_EXTRACTION.value,
        filename=f"page-{page_number:04d}.json",
        content=json.dumps(payload, sort_keys=True).encode(),
        content_type="application/json",
        metadata={
            "source_document_id": str(source.id),
            "page_number": str(page_number),
        },
    )
    db.add(
        IngestionArtifact(
            run_id=run.id,
            source_page_id=page.id,
            artifact_type=IngestionArtifactType.RAW_EXTRACTION,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            artifact_metadata={"page_number": page_number},
        )
    )
    db.commit()


def _clear_run_tasks(db: Session, run: IngestionRun) -> None:
    db.exec(delete(IngestionTask).where(IngestionTask.run_id == run.id))
    db.commit()


def _instrument_slug(db: Session, source: SourceDocument) -> str:
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    return instrument.slug


def _pdf_with_pages(texts: list[str]) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=500)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        resources = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
            }
        )
        content = StreamObject()
        content._data = (
            f"BT /F1 12 Tf 36 450 Td ({_escape_pdf_text(text)}) Tj ET".encode()
        )
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_embedding_rejects_active_profile_without_pinned_revision(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    profile.model_revision = None
    db.add(profile)
    db.commit()

    def _unexpected_provider(_profile: EmbeddingProfile) -> EmbeddingBatch:
        raise AssertionError("Provider must not run without a pinned revision")

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        _unexpected_provider,
    )
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    run.pipeline_config = {"auto_start_embedding": True}
    db.add(run)
    db.commit()
    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=embedding_step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:embedding-unpinned",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )

    # Three attempts are exhausted (default max_attempts=3) before the
    # task and run reach FAILED.
    results = run_until_idle(db, worker_id="worker-test", max_tasks=4)

    assert results[-1].task_status == IngestionTaskStatus.FAILED
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "pinned model_revision" in run.error_details["message"]


def test_embedding_honors_configured_batch_size(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run, release, profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )
    dataset_version = profile.configuration["benchmark_dataset_version"]
    dataset = db.exec(
        select(EvaluationDataset).where(EvaluationDataset.version == dataset_version)
    ).one()
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="citizenship-query",
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            query_text="Which section protects movement?",
            expected_canonical_paths=[f"{dataset_version}"],
        )
    )
    # Point the second query at the same provision so recall stays perfect.
    provision = db.exec(
        select(Provision).where(Provision.instrument_id == source.legal_instrument_id)
    ).one()
    second_query = db.exec(
        select(EvaluationItem).where(EvaluationItem.item_key == "citizenship-query")
    ).one()
    second_query.expected_canonical_paths = [provision.canonical_path]
    profile.configuration = {
        **profile.configuration,
        "batch_size": 1,
    }
    db.add_all([profile, second_query])
    db.commit()

    calls: list[list[str]] = []

    class RecordingEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            calls.append(list(texts))
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: RecordingEmbeddingProvider(),
    )
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    run.pipeline_config = {"auto_start_embedding": True}
    db.add(run)
    db.commit()
    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=embedding_step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:embedding-batched",
        payload={"source_document_id": str(source.id), "release_id": str(release.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=1)

    assert results[0].task_status == IngestionTaskStatus.SUCCEEDED
    # One document call plus one call per benchmark query.
    assert calls[0] == ["Section 37\nRight to private and family life"]
    assert sorted(calls[1:]) == [
        ["Which section protects movement?"],
        ["Which section protects privacy?"],
    ]
    embedding_run = db.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.profile_id == profile.id,
        )
    ).one()
    assert embedding_run.status == EmbeddingRunStatus.SUCCEEDED
    assert embedding_run.recall_at_10 == 1


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


def test_embedding_can_be_started_again_after_documents_are_rebuilt(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, _profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)
    actor = create_random_user(db)
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.current_stage = IngestionStage.EMBEDDING
    db.add(run)
    db.commit()
    db.refresh(run)
    start_embedding(
        db,
        run.id,
        expected_version=run.lock_version,
        idempotency_key=f"start-{uuid.uuid4().hex}",
        current_user=actor,
    )
    first = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.EMBEDDING.value,
        )
    ).one()
    first.status = IngestionTaskStatus.FAILED
    # The run fails, its documents are rebuilt and it is ready to embed again.
    db.refresh(run)
    run.status = IngestionRunStatus.READY_TO_EMBED
    run.lock_version += 1
    db.add_all([first, run])
    db.commit()
    db.refresh(run)

    start_embedding(
        db,
        run.id,
        expected_version=run.lock_version,
        idempotency_key=f"start-{uuid.uuid4().hex}",
        current_user=actor,
    )

    pending = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.EMBEDDING.value,
            IngestionTask.status == IngestionTaskStatus.PENDING,
        )
    ).one()
    assert pending.id != first.id
    assert pending.payload["release_id"] == str(release.id)


def test_retrieval_documents_can_be_rebuilt_after_retrieval_text_changes(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, _profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)
    task = IngestionTask(
        run_id=run.id,
        task_type=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS.value,
        idempotency_key=f"{run.id}:building:rebuild",
        payload={"release_id": str(release.id)},
    )
    handle_building_retrieval_documents(db, run, task)
    monkeypatch.setattr(
        "app.ingestion.retrieval.retrieval_phrasing",
        lambda _path: "In plain words: privacy at home.",
    )

    # Changed search text produces a new artifact beside the first instead of
    # colliding with it in the immutable store.
    handle_building_retrieval_documents(db, run, task)

    artifacts = db.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type
            == IngestionArtifactType.RETRIEVAL_DOCUMENTS,
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).all()
    newest = json.loads(LocalBlobStore(tmp_path).read_bytes(artifacts[0].storage_key))
    assert (
        "In plain words: privacy at home." in (newest["documents"][0]["retrieval_text"])
    )
    assert len({artifact.storage_key for artifact in artifacts}) >= 2


def test_embedding_can_be_rescored_after_its_benchmark_result_changes(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)

    class FakeEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: FakeEmbeddingProvider(),
    )
    item = db.exec(
        select(EvaluationItem)
        .join(EvaluationDataset)
        .where(
            EvaluationDataset.version
            == profile.configuration["benchmark_dataset_version"]
        )
    ).one()
    expected_paths = item.expected_canonical_paths
    item.expected_canonical_paths = [f"{expected_paths[0]}-elsewhere"]
    db.add(item)
    db.commit()
    task = IngestionTask(
        run_id=run.id,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:embedding:rescore",
        payload={"release_id": str(release.id)},
    )

    with pytest.raises(IngestionWorkerError, match="Recall@10"):
        handle_embedding(db, run, task)

    # The same vectors now score differently; the new artifact sits beside
    # the first instead of colliding with it in the immutable store.
    item.expected_canonical_paths = expected_paths
    db.add(item)
    db.commit()
    handle_embedding(db, run, task)

    embedding_run = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    assert embedding_run.status == EmbeddingRunStatus.SUCCEEDED
    assert embedding_run.recall_at_10 == 1.0
    assert embedding_run.selected_for_release is True
    artifacts = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).all()
    assert len({artifact.storage_key for artifact in artifacts}) == 2


def test_embedding_retry_reuses_completed_batches_and_invalidates_changed_inputs(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _, run, release, profile = _release_with_retrieval_documents(db, tmp_path=tmp_path)
    embedding_run = EmbeddingRun(release_id=release.id, profile_id=profile.id)
    db.add(embedding_run)
    db.commit()
    calls: list[list[str]] = []

    class InterruptedProvider:
        failed = False

        def embed(self, texts: list[str]) -> EmbeddingBatch:
            calls.append(texts)
            if texts == ["second"] and not self.failed:
                self.failed = True
                raise RuntimeError("provider timeout")
            return EmbeddingBatch(
                provider="fake",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    provider = InterruptedProvider()
    arguments = {
        "run": run,
        "profile": profile,
        "embedding_run": embedding_run,
        "provider": provider,
        "batch_size": 1,
        "kind": "documents",
    }
    with pytest.raises(RuntimeError, match="provider timeout"):
        _embed_with_checkpoints(db, texts=["first", "second", "third"], **arguments)
    batch = _embed_with_checkpoints(db, texts=["first", "second", "third"], **arguments)
    assert calls == [["first"], ["second"], ["second"], ["third"]]
    assert len(batch.vectors) == 3
    _embed_with_checkpoints(db, texts=["changed", "second", "third"], **arguments)
    assert calls[-1] == ["changed"]
    assert len(calls) == 5
    assert embedding_run.metrics["documents_progress"]["completed"] == 3
