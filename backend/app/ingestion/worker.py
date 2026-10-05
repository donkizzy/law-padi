import hashlib
import json
import re
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, BinaryIO, cast

from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.embedding import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DenseEmbeddingProvider,
    EmbeddingBatch,
    EmbeddingBenchmarkQuery,
    HuggingFaceTeiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SparseLegalEncoder,
    evaluate_embedding_benchmark,
    select_best_embedding_run,
)
from app.ingestion.evaluation import (
    active_evaluation_item_count,
    load_gold_provisions_for_dataset,
    load_retrieval_evaluation_queries,
)
from app.ingestion.extraction import NativePdfExtractor
from app.ingestion.malware import malware_scanner_from_settings
from app.ingestion.normalization import NORMALIZER_VERSION, normalize_page_text
from app.ingestion.ocr import (
    OcrPageInput,
    OcrPageResult,
    TesseractOcrProvider,
    managed_ocr_provider_from_settings,
)
from app.ingestion.pdf import (
    PdfInspectionError,
    inspect_pdf_bytes,
    inspect_pdf_file,
    profile_pdf_pages,
)
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
    validate_index_build,
    write_embeddings,
    write_segments,
)
from app.ingestion.qdrant import (
    QdrantHttpIndexAdapter,
    QdrantPoint,
    QdrantSparseVector,
    alias_for_index_kind,
    collection_name_for_release,
    validate_qdrant_points,
)
from app.ingestion.quality import (
    LEGAL_GRADE_MIN_CHARACTER_ACCURACY,
    ExtractedProvision,
    LegalGradeQualityReport,
    evaluate_legal_grade_quality,
)
from app.ingestion.rendering import render_page_thumbnail
from app.ingestion.retrieval import RetrievalDocument, build_retrieval_documents
from app.ingestion.service import (
    MAX_SOURCE_PAGES,
    finalize_verified_upload,
    get_blob_store,
    get_datetime_utc,
)
from app.ingestion.structure_validators import validate_document_graph
from app.ingestion.text_alignment import aligned_source_spans, compact_text
from app.ingestion.validation import has_unbalanced_punctuation
from app.ingestion.workflow import (
    append_run_event,
    complete_task,
    enqueue_task,
    fail_task,
    lease_next_task,
    mark_task_running,
    renew_task_lease,
)
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
    LegalStatus,
    PageInclusionStatus,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    SourceUploadStatus,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.instrument_parser import (
    parse_instrument_pages,
    parsed_provisions_from_graph,
)
from app.legal.models import (
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    VectorIndex,
)
from app.legal.parser import (
    PARSER_VERSION,
    legal_text_sha256,
    normalize_legal_text,
)
from app.legal.parser import (
    SourcePage as ParserSourcePage,
)

AUTO_APPROVAL_MIN_CONFIDENCE = 0.9


class IngestionWorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class StageOutcome:
    metrics: dict[str, Any]
    next_stage: IngestionStage | None = None
    next_status: IngestionRunStatus = IngestionRunStatus.RUNNING
    next_task_payload: dict[str, Any] | None = None
    block_next_stage: bool = False
    skipped_stages: tuple[IngestionStage, ...] = ()


@dataclass(frozen=True)
class WorkerResult:
    task_id: uuid.UUID
    run_id: uuid.UUID
    stage: IngestionStage
    task_status: IngestionTaskStatus
    run_status: IngestionRunStatus


StageHandler = Callable[[Session, IngestionRun, IngestionTask], StageOutcome]


def run_once(
    session: Session,
    *,
    worker_id: str,
    task_type: str | None = None,
    lease_seconds: int = 900,
    stage_concurrency_limits: dict[str, int] | None = None,
) -> WorkerResult | None:
    task = lease_next_task(
        session,
        worker_id=worker_id,
        task_type=task_type,
        lease_seconds=lease_seconds,
        stage_concurrency_limits=(
            stage_concurrency_limits
            if stage_concurrency_limits is not None
            else settings.INGESTION_STAGE_CONCURRENCY_LIMITS
        ),
    )
    if not task:
        return None
    return run_leased_task(session, task, worker_id=worker_id)


def run_until_idle(
    session: Session,
    *,
    worker_id: str,
    max_tasks: int = 100,
) -> list[WorkerResult]:
    results: list[WorkerResult] = []
    for _ in range(max_tasks):
        result = run_once(session, worker_id=worker_id)
        if result is None:
            break
        results.append(result)
    return results


def run_leased_task(
    session: Session, task: IngestionTask, *, worker_id: str
) -> WorkerResult:
    run = _get_run(session, task.run_id)
    stage = _stage_for_task(task)
    step = _get_step(session, run.id, stage, task.step_id)
    started_at = get_datetime_utc()
    task = mark_task_running(session, task)
    _mark_step_running(session, step, worker_id=worker_id, started_at=started_at)
    _mark_run_running(session, run, stage=stage)
    append_run_event(
        session,
        run,
        event_type="stage_started",
        message=f"{stage.value} started",
        step=step,
        payload={"worker_id": worker_id, "task_id": str(task.id)},
    )

    stop_heartbeat = threading.Event()
    lease_lost = threading.Event()

    def heartbeat() -> None:
        interval = max(1.0, settings.INGESTION_WORKER_LEASE_SECONDS / 3)
        while not stop_heartbeat.wait(interval):
            try:
                from app.core.db import engine

                with Session(engine) as heartbeat_session:
                    if not renew_task_lease(
                        heartbeat_session,
                        task_id=task.id,
                        worker_id=worker_id,
                        lease_seconds=settings.INGESTION_WORKER_LEASE_SECONDS,
                    ):
                        lease_lost.set()
                        return
            except Exception:
                lease_lost.set()
                return

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    try:
        outcome = _handler_for(stage)(session, run, task)
        if lease_lost.is_set():
            raise IngestionWorkerError("Task lease was lost during stage execution")
    except Exception as exc:
        return _handle_stage_failure(
            session,
            run=run,
            step=step,
            task=task,
            stage=stage,
            exc=exc,
        )
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)

    completed_task = complete_task(session, task, commit=False)
    _mark_step_succeeded(session, step, metrics=outcome.metrics, commit=False)
    append_run_event(
        session,
        run,
        event_type="stage_succeeded",
        message=f"{stage.value} completed",
        step=step,
        payload=outcome.metrics,
        commit=False,
    )
    _advance_run_after_success(session, run, outcome=outcome, commit=False)
    session.commit()
    session.refresh(run)
    return WorkerResult(
        task_id=completed_task.id,
        run_id=run.id,
        stage=stage,
        task_status=completed_task.status,
        run_status=run.status,
    )


def handle_verifying_upload(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    if run.source_document_id or task.payload.get("source_document_id"):
        source = _get_source_for_run(session, run, task)
        inspection = inspect_pdf_bytes(
            _read_source_bytes(source),
            expected_sha256=source.sha256,
            expected_size=source.file_size,
            max_pages=MAX_SOURCE_PAGES,
        )
        source.page_count = inspection.page_count
        source.verification_status = VerificationStatus.NEEDS_REVIEW
        session.add(source)
        _ensure_artifact(
            session,
            run_id=run.id,
            artifact_type=IngestionArtifactType.ORIGINAL_SOURCE,
            storage_key=_require_storage_key(source),
            sha256=inspection.sha256,
            mime_type=source.mime_type,
            metadata={
                "source_document_id": str(source.id),
                "verification": "sha256_size_page_count",
            },
        )
        session.commit()
        return StageOutcome(
            metrics={
                "sha256": inspection.sha256,
                "size_bytes": inspection.size_bytes,
                "page_count": inspection.page_count,
            },
            next_stage=IngestionStage.MALWARE_SCAN,
            next_task_payload={"source_document_id": str(source.id)},
        )

    upload = _get_upload_for_run(session, run, task)
    store = get_blob_store()
    try:
        with tempfile.NamedTemporaryFile(mode="w+b") as temporary:
            with store.open_read(upload.quarantine_key) as source_stream:
                shutil.copyfileobj(source_stream, temporary, length=1024 * 1024)
            temporary.flush()
            inspection = inspect_pdf_file(
                cast(BinaryIO, temporary),
                expected_sha256=upload.expected_sha256,
                expected_size=upload.expected_size,
                max_pages=MAX_SOURCE_PAGES,
            )
    except (FileNotFoundError, OSError, PdfInspectionError) as exc:
        raise IngestionWorkerError(str(exc)) from exc

    claimed_sha256 = str(run.pipeline_config.get("claimed_sha256") or "")
    if claimed_sha256 and claimed_sha256 != inspection.sha256:
        raise IngestionWorkerError(
            "Completion SHA-256 does not match the uploaded object"
        )
    upload.actual_sha256 = inspection.sha256
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    session.add(upload)
    session.flush()
    _ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.ORIGINAL_SOURCE,
        storage_key=upload.quarantine_key,
        sha256=inspection.sha256,
        mime_type=upload.mime_type,
        metadata={
            "source_upload_id": str(upload.id),
            "verification": "sha256_size_page_count",
            "quarantine": True,
        },
    )
    run.expected_page_count = inspection.page_count
    run.pipeline_config = {
        **run.pipeline_config,
        "source_sha256": inspection.sha256,
        "page_count": inspection.page_count,
    }
    session.add(run)
    session.commit()
    return StageOutcome(
        metrics={
            "sha256": inspection.sha256,
            "size_bytes": inspection.size_bytes,
            "page_count": inspection.page_count,
        },
        next_stage=IngestionStage.MALWARE_SCAN,
        next_task_payload={"source_upload_id": str(upload.id)},
    )


def handle_malware_scan(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    if run.source_document_id or task.payload.get("source_document_id"):
        source = _get_source_for_run(session, run, task)
        try:
            with get_blob_store().open_read(_require_storage_key(source)) as stream:
                scan_report = malware_scanner_from_settings(settings).scan_stream(
                    stream
                )
        except FileNotFoundError as exc:
            raise IngestionWorkerError(
                "Stored source document file was not found"
            ) from exc
        return StageOutcome(
            metrics=scan_report.to_metrics(),
            next_stage=IngestionStage.PROFILING,
            next_task_payload={"source_document_id": str(source.id)},
        )

    upload = _get_upload_for_run(session, run, task)
    try:
        with get_blob_store().open_read(upload.quarantine_key) as stream:
            scan_report = malware_scanner_from_settings(settings).scan_stream(stream)
    except FileNotFoundError as exc:
        raise IngestionWorkerError("Quarantined upload file was not found") from exc
    if run.expected_page_count is None:
        raise IngestionWorkerError("Upload verification did not record a page count")
    source = finalize_verified_upload(
        session,
        run=run,
        upload=upload,
        sha256=upload.actual_sha256
        or str(run.pipeline_config.get("source_sha256") or ""),
        page_count=run.expected_page_count,
    )
    return StageOutcome(
        metrics=scan_report.to_metrics(),
        next_stage=IngestionStage.PROFILING,
        next_task_payload={"source_document_id": str(source.id)},
    )


def handle_profiling(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    profiles = profile_pdf_pages(_read_source_bytes(source), max_pages=MAX_SOURCE_PAGES)
    included_pages = 0
    requires_ocr = 0
    for profile in profiles:
        if profile.inclusion_status == PageInclusionStatus.SUGGESTED_INCLUDE:
            included_pages += 1
        if profile.quality_signals.get("requires_ocr"):
            requires_ocr += 1
        _upsert_source_page(session, run=run, source=source, profile=profile)
    session.commit()
    return StageOutcome(
        metrics={
            "page_count": len(profiles),
            "suggested_included_pages": included_pages,
            "requires_ocr_pages": requires_ocr,
        },
        next_stage=IngestionStage.RENDERING,
        next_task_payload={"source_document_id": str(source.id)},
    )


def handle_rendering(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    content = _read_source_bytes(source)
    pages = _pages_for_run(session, run)
    if not pages:
        raise IngestionWorkerError("Run does not have profiled pages to render")

    rendered_count = 0
    for page in pages:
        thumbnail = render_page_thumbnail(content, page_number=page.page_number)
        blob = get_blob_store().put_artifact(
            run_id=str(run.id),
            artifact_type=IngestionArtifactType.PAGE_THUMBNAIL.value,
            filename=f"page-{page.page_number:04d}.png",
            content=thumbnail.content,
            content_type=thumbnail.content_type,
            metadata={
                "source_document_id": str(source.id),
                "page_number": str(page.page_number),
            },
        )
        _ensure_artifact(
            session,
            run_id=run.id,
            source_page_id=page.id,
            artifact_type=IngestionArtifactType.PAGE_THUMBNAIL,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            retention_policy="expire_after_90_days",
            metadata={"page_number": page.page_number},
        )
        page.thumbnail_key = blob.key
        session.add(page)
        rendered_count += 1
    session.commit()
    confirmed = all(
        page.inclusion_status
        in {PageInclusionStatus.INCLUDED, PageInclusionStatus.EXCLUDED}
        for page in pages
    )
    if confirmed:
        return StageOutcome(
            metrics={"thumbnail_count": rendered_count},
            next_stage=IngestionStage.NATIVE_EXTRACTION,
            next_task_payload={"source_document_id": str(source.id)},
        )
    return StageOutcome(
        metrics={"thumbnail_count": rendered_count},
        next_stage=IngestionStage.AWAITING_PAGE_CONFIRMATION,
        next_status=IngestionRunStatus.WAITING_FOR_INPUT,
        block_next_stage=True,
    )


def handle_native_extraction(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    included_pages = {
        page.page_number
        for page in _pages_for_run(session, run)
        if page.inclusion_status == PageInclusionStatus.INCLUDED
    }
    if not included_pages:
        raise IngestionWorkerError("Run does not have confirmed included pages")

    extractor = NativePdfExtractor()
    extractions = extractor.extract(
        _read_source_bytes(source), included_pages=included_pages
    )
    pages_by_number = {page.page_number: page for page in _pages_for_run(session, run)}
    needs_ocr = 0
    for extraction in extractions:
        page = pages_by_number[extraction.page_number]
        raw_payload = {
            "page_number": extraction.page_number,
            "method": extraction.method,
            "provider_version": extraction.provider_version,
            "confidence": extraction.confidence,
            "text": extraction.text,
            "plain_text": extraction.plain_text,
            "spans": [
                {
                    "text": span.text,
                    "bbox": span.bbox,
                    "reading_order": span.reading_order,
                }
                for span in extraction.spans
            ],
            "quality_flags": extraction.quality_flags,
        }
        blob = get_blob_store().put_artifact(
            run_id=str(run.id),
            artifact_type=IngestionArtifactType.RAW_EXTRACTION.value,
            filename=f"page-{extraction.page_number:04d}.json",
            content=json.dumps(raw_payload, sort_keys=True).encode(),
            content_type="application/json",
            metadata={
                "source_document_id": str(source.id),
                "page_number": str(extraction.page_number),
            },
        )
        _ensure_artifact(
            session,
            run_id=run.id,
            source_page_id=page.id,
            artifact_type=IngestionArtifactType.RAW_EXTRACTION,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            metadata={
                "page_number": extraction.page_number,
                "method": extraction.method,
                "provider_version": extraction.provider_version,
                "confidence": extraction.confidence,
                "timing_ms": extraction.timing_ms,
            },
        )
        page.quality_signals = {
            **(page.quality_signals or {}),
            "native_extraction": {
                "provider_version": extraction.provider_version,
                "confidence": extraction.confidence,
                "span_count": len(extraction.spans),
                "timing_ms": extraction.timing_ms,
            },
        }
        session.add(page)
        if extraction.quality_flags.get("needs_ocr"):
            needs_ocr += 1
    session.commit()
    next_stage = IngestionStage.LOCAL_OCR if needs_ocr else IngestionStage.NORMALIZING
    skipped_stages = (
        () if needs_ocr else (IngestionStage.LOCAL_OCR, IngestionStage.MANAGED_OCR)
    )
    return StageOutcome(
        metrics={
            "page_count": len(extractions),
            "needs_ocr_pages": needs_ocr,
        },
        next_stage=next_stage,
        next_task_payload={
            "source_document_id": str(source.id),
            "included_pages": sorted(included_pages),
        },
        skipped_stages=skipped_stages,
    )


def handle_local_ocr(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    page_numbers = _ocr_page_numbers(session, run, task)
    if not page_numbers:
        return StageOutcome(
            metrics={"ocr_page_count": 0, "managed_ocr_required_pages": 0},
            next_stage=IngestionStage.NORMALIZING,
            next_task_payload={"source_document_id": str(source.id)},
            skipped_stages=(IngestionStage.MANAGED_OCR,),
        )

    source_content = _read_source_bytes(source)
    pages_by_number = {page.page_number: page for page in _pages_for_run(session, run)}
    provider = TesseractOcrProvider()
    managed_required_pages: list[int] = []
    for page_number in page_numbers:
        thumbnail = render_page_thumbnail(
            source_content, page_number=page_number, scale_to=1600
        )
        result = provider.extract_page(
            OcrPageInput(
                page_number=page_number,
                image=thumbnail.content,
                content_type=thumbnail.content_type,
            )
        )
        page = pages_by_number.get(page_number)
        payload = {
            "page_number": result.page_number,
            "method": result.method,
            "provider": result.provider,
            "provider_version": result.provider_version,
            "confidence": result.confidence,
            "cost_usd": result.cost_usd,
            "text": result.text,
            "spans": [
                {
                    "text": word.text,
                    "bbox": word.bbox,
                    "confidence": word.confidence,
                    "reading_order": word.reading_order,
                }
                for word in result.words
            ],
            "quality_flags": result.quality_flags,
        }
        blob = get_blob_store().put_artifact(
            run_id=str(run.id),
            artifact_type=IngestionArtifactType.OCR_OUTPUT.value,
            filename=f"page-{page_number:04d}-local-ocr.json",
            content=json.dumps(payload, sort_keys=True).encode(),
            content_type="application/json",
            metadata={
                "source_document_id": str(source.id),
                "page_number": str(page_number),
                "provider": result.provider,
            },
        )
        _ensure_artifact(
            session,
            run_id=run.id,
            source_page_id=page.id if page else None,
            artifact_type=IngestionArtifactType.OCR_OUTPUT,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            retention_policy="expire_after_90_days",
            metadata={
                "page_number": page_number,
                "method": result.method,
                "provider": result.provider,
                "provider_version": result.provider_version,
                "confidence": result.confidence,
                "timing_ms": result.timing_ms,
                "cost_usd": result.cost_usd,
            },
        )
        if page:
            page.quality_signals = {
                **(page.quality_signals or {}),
                "local_ocr": {
                    "provider": result.provider,
                    "provider_version": result.provider_version,
                    "confidence": result.confidence,
                    "word_count": len(result.words),
                    "timing_ms": result.timing_ms,
                },
            }
            session.add(page)
        if result.quality_flags.get("requires_managed_ocr"):
            managed_required_pages.append(page_number)
    session.commit()
    if managed_required_pages:
        return StageOutcome(
            metrics={
                "ocr_page_count": len(page_numbers),
                "managed_ocr_required_pages": len(managed_required_pages),
            },
            next_stage=IngestionStage.MANAGED_OCR,
            next_task_payload={
                "source_document_id": str(source.id),
                "page_numbers": managed_required_pages,
            },
            next_status=IngestionRunStatus.RUNNING,
        )
    return StageOutcome(
        metrics={
            "ocr_page_count": len(page_numbers),
            "managed_ocr_required_pages": 0,
        },
        next_stage=IngestionStage.NORMALIZING,
        next_task_payload={"source_document_id": str(source.id)},
        skipped_stages=(IngestionStage.MANAGED_OCR,),
    )


def handle_managed_ocr(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    page_numbers = _managed_ocr_page_numbers(session, run, task)
    if not page_numbers:
        return StageOutcome(
            metrics={"managed_ocr_page_count": 0},
            next_stage=IngestionStage.NORMALIZING,
            next_task_payload={"source_document_id": str(source.id)},
        )

    source_content = _read_source_bytes(source)
    pages_by_number = {page.page_number: page for page in _pages_for_run(session, run)}
    provider = managed_ocr_provider_from_settings()
    for page_number in page_numbers:
        thumbnail = render_page_thumbnail(
            source_content, page_number=page_number, scale_to=1600
        )
        result = provider.extract_page(
            OcrPageInput(
                page_number=page_number,
                image=thumbnail.content,
                content_type=thumbnail.content_type,
            )
        )
        page = pages_by_number.get(page_number)
        payload = _ocr_result_payload(result)
        blob = get_blob_store().put_artifact(
            run_id=str(run.id),
            artifact_type=IngestionArtifactType.OCR_OUTPUT.value,
            filename=f"page-{page_number:04d}-managed-ocr.json",
            content=json.dumps(payload, sort_keys=True).encode(),
            content_type="application/json",
            metadata={
                "source_document_id": str(source.id),
                "page_number": str(page_number),
                "provider": result.provider,
            },
        )
        _ensure_artifact(
            session,
            run_id=run.id,
            source_page_id=page.id if page else None,
            artifact_type=IngestionArtifactType.OCR_OUTPUT,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            retention_policy="expire_after_90_days",
            metadata={
                "page_number": page_number,
                "method": result.method,
                "provider": result.provider,
                "provider_version": result.provider_version,
                "confidence": result.confidence,
                "timing_ms": result.timing_ms,
                "cost_usd": result.cost_usd,
            },
        )
        if page:
            page.quality_signals = {
                **(page.quality_signals or {}),
                "managed_ocr": {
                    "provider": result.provider,
                    "provider_version": result.provider_version,
                    "confidence": result.confidence,
                    "word_count": len(result.words),
                    "timing_ms": result.timing_ms,
                },
            }
            session.add(page)
    session.commit()
    return StageOutcome(
        metrics={"managed_ocr_page_count": len(page_numbers)},
        next_stage=IngestionStage.NORMALIZING,
        next_task_payload={"source_document_id": str(source.id)},
    )


def handle_normalizing(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    raw_payloads = _best_extraction_payloads(session, run)
    if not raw_payloads:
        raise IngestionWorkerError("Run does not have raw extraction artifacts")

    normalized_pages = []
    empty_pages = 0
    for payload in raw_payloads:
        normalization = normalize_page_text(str(payload.get("text") or ""))
        text = normalization.text
        if not text:
            empty_pages += 1
        normalized_pages.append(
            {
                "page_number": int(payload["page_number"]),
                "text": text,
                "spans": payload.get("spans") or [],
                "method": payload.get("method"),
                "provider_version": payload.get("provider_version"),
                "confidence": payload.get("confidence"),
                "normalization_changes": normalization.changes,
            }
        )

    normalized_payload = {
        "normalizer_version": NORMALIZER_VERSION,
        "source_document_id": str(source.id),
        "pages": normalized_pages,
    }
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.NORMALIZED_PAGES.value,
        filename="normalized-pages.json",
        content=json.dumps(normalized_payload, sort_keys=True).encode(),
        content_type="application/json",
        metadata={"source_document_id": str(source.id)},
    )
    _ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.NORMALIZED_PAGES,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={
            "normalizer_version": NORMALIZER_VERSION,
            "page_count": len(normalized_pages),
        },
    )
    session.commit()
    return StageOutcome(
        metrics={
            "page_count": len(normalized_pages),
            "empty_pages": empty_pages,
            "normalizer_version": NORMALIZER_VERSION,
        },
        next_stage=IngestionStage.PARSING_STRUCTURE,
        next_task_payload={"source_document_id": str(source.id)},
    )


def handle_parsing_structure(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    if not instrument:
        raise IngestionWorkerError(
            "Source document is not linked to a legal instrument"
        )
    normalized_payload = _normalized_pages_payload(session, run)
    page_payloads = list(normalized_payload["pages"])
    parser_pages = [
        ParserSourcePage(
            page_number=int(page["page_number"]),
            text=str(page["text"]),
        )
        for page in page_payloads
    ]
    instrument_type = getattr(instrument, "instrument_type", "constitution")
    instrument_type_value = str(getattr(instrument_type, "value", instrument_type))
    graph = parse_instrument_pages(
        instrument_type=instrument_type_value,
        instrument_slug=instrument.slug,
        pages=parser_pages,
    )
    parsed_nodes = parsed_provisions_from_graph(graph)
    page_roles = [
        {"page_number": page.page_number, "role": _enum_value(page.role)}
        for page in session.exec(
            select(SourcePage).where(SourcePage.run_id == run.id)
        ).all()
    ]
    graph_issues = validate_document_graph(graph, page_roles=page_roles)
    node_by_path = {node.canonical_path: node for node in parsed_nodes}
    candidates_by_path: dict[str, ExtractionCandidate] = {}
    issues_by_candidate_id: dict[uuid.UUID, list[ReviewIssue]] = {}
    issue_count = 0
    blocking_issue_count = 0

    for node in parsed_nodes:
        candidate = _upsert_candidate(
            session,
            run=run,
            source=source,
            node=node,
            parent_candidate=candidates_by_path.get(node.parent_path or ""),
            ancestor_headings=_ancestor_headings(node.parent_path, node_by_path),
            source_spans=_source_spans_for_node(
                node, page_payloads, nodes_by_path=node_by_path
            ),
        )
        candidates_by_path[node.canonical_path] = candidate
        missing_parent_issue = None
        if node.parent_path and not candidate.parent_candidate_id:
            missing_parent_issue = _ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="missing_parent",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate parent path was not materialized before this node.",
                evidence={"parent_path": node.parent_path},
            )
        issues = _validate_candidate_for_review(session, candidate)
        if missing_parent_issue:
            issues.append(missing_parent_issue)
        candidate.blocking_issue_count = sum(1 for issue in issues if issue.blocking)
        session.add(candidate)
        issues_by_candidate_id[candidate.id] = issues
        issue_count += len(issues)
        blocking_issue_count += sum(1 for issue in issues if issue.blocking)
    for graph_issue in graph_issues:
        # Per-candidate validators already cover parents, punctuation, and
        # source spans; only emit document-level findings here to avoid
        # double-reporting the same defect.
        if graph_issue.issue_type in {
            "missing_parent",
            "unbalanced_punctuation",
            "source_span_coverage",
            "duplicate_canonical_path",
        }:
            continue
        target_candidate: ExtractionCandidate | None = (
            candidates_by_path.get(graph_issue.canonical_path or "")
            if graph_issue.canonical_path
            else None
        )
        if target_candidate is None and candidates_by_path:
            target_candidate = next(iter(candidates_by_path.values()))
        if target_candidate is None:
            continue
        issue = _ensure_review_issue(
            session,
            candidate=target_candidate,
            issue_type=f"graph_{graph_issue.issue_type}",
            severity=ReviewIssueSeverity.BLOCKING
            if graph_issue.blocking
            else ReviewIssueSeverity.HIGH,
            blocking=graph_issue.blocking,
            message=graph_issue.message,
            evidence=graph_issue.evidence,
        )
        issues_by_candidate_id.setdefault(target_candidate.id, []).append(issue)
        target_candidate.blocking_issue_count = sum(
            1 for item in issues_by_candidate_id[target_candidate.id] if item.blocking
        )
        session.add(target_candidate)
        issue_count += 1
        blocking_issue_count += 1 if issue.blocking else 0
    quality_report = _maybe_compute_gold_quality_report(
        session, run, list(candidates_by_path.values())
    )
    for candidate in candidates_by_path.values():
        candidate.status = _validated_candidate_status(
            run, candidate, issues_by_candidate_id.get(candidate.id, [])
        )
        session.add(candidate)
    session.commit()
    auto_approved_count = sum(
        1
        for candidate in candidates_by_path.values()
        if candidate.status == ExtractionCandidateStatus.AUTO_APPROVED
    )
    return StageOutcome(
        metrics={
            "candidate_count": len(parsed_nodes),
            "issue_count": issue_count,
            "blocking_issue_count": blocking_issue_count,
            "auto_approved_count": auto_approved_count,
            "parser_version": PARSER_VERSION,
            "legal_grade_quality": (
                quality_report.to_policy_metrics() if quality_report else None
            ),
        },
        next_stage=IngestionStage.VALIDATING_DOCUMENT,
        next_task_payload={"source_document_id": str(source.id)},
    )


def handle_validating_document(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    candidates = session.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    if not candidates:
        raise IngestionWorkerError("Run does not have parsed extraction candidates")
    blocking_count = sum(candidate.blocking_issue_count for candidate in candidates)
    review_count = sum(
        1
        for candidate in candidates
        if candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    )
    text_candidate_count = sum(1 for candidate in candidates if candidate.raw_text)
    metrics = {
        "candidate_count": len(candidates),
        "text_candidate_count": text_candidate_count,
        "review_count": review_count,
        "blocking_issue_count": blocking_count,
        "source_verification_required": (
            source.verification_status != VerificationStatus.VERIFIED
        ),
    }
    if blocking_count or review_count or metrics["source_verification_required"]:
        return StageOutcome(
            metrics=metrics,
            next_stage=IngestionStage.REVIEW,
            next_status=IngestionRunStatus.WAITING_FOR_REVIEW,
            block_next_stage=True,
        )
    return StageOutcome(
        metrics=metrics,
        next_stage=IngestionStage.MATERIALIZING,
        next_task_payload={"candidate_count": len(candidates)},
    )


def handle_materializing(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = _get_source_for_run(session, run, task)
    if source.verification_status != VerificationStatus.VERIFIED:
        raise IngestionWorkerError(
            "Source document must be verified before materialization"
        )
    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    if not instrument:
        raise IngestionWorkerError(
            "Source document is not linked to a legal instrument"
        )
    candidates = _approved_candidates_for_run(session, run)
    if not candidates:
        raise IngestionWorkerError(
            "Run does not have reviewed candidates to materialize"
        )
    _ensure_no_open_blocking_issues(session, candidates)

    corpus_legal_status = _corpus_legal_status(run)
    provision_ids_by_candidate_id: dict[uuid.UUID, uuid.UUID] = {}
    materialized_version_ids: set[uuid.UUID] = set()
    created_provisions = 0
    created_versions = 0
    reused_versions = 0
    superseded_versions = 0
    changed_current_law_text_count = (
        _block_unclassified_current_law_changes(
            session, source=source, candidates=candidates
        )
        if corpus_legal_status == LegalStatus.CURRENT
        else 0
    )
    if changed_current_law_text_count:
        session.commit()
        return StageOutcome(
            metrics={
                "candidate_count": len(candidates),
                "changed_current_law_text_count": changed_current_law_text_count,
                "blocking_issue_count": changed_current_law_text_count,
            },
            next_stage=IngestionStage.REVIEW,
            next_status=IngestionRunStatus.WAITING_FOR_REVIEW,
            block_next_stage=True,
        )

    for candidate in candidates:
        parent_id = _parent_provision_id_for_candidate(
            session,
            candidate,
            provision_ids_by_candidate_id=provision_ids_by_candidate_id,
        )
        provision, provision_created = _upsert_provision_from_candidate(
            session, instrument=instrument, candidate=candidate, parent_id=parent_id
        )
        provision_ids_by_candidate_id[candidate.id] = provision.id
        if provision_created:
            created_provisions += 1

        candidate.materialized_provision_id = provision.id
        text = _candidate_text_for_materialization(session, candidate)
        if text:
            upsert_version = (
                _upsert_historical_version_from_candidate
                if corpus_legal_status == LegalStatus.HISTORICAL
                else _upsert_current_version_from_candidate
            )
            version, version_action = upsert_version(
                session,
                source=source,
                instrument=instrument,
                provision=provision,
                candidate=candidate,
                text=text,
            )
            candidate.materialized_version_id = version.id
            materialized_version_ids.add(version.id)
            if version_action == "created":
                created_versions += 1
            elif version_action == "reused":
                reused_versions += 1
            else:
                superseded_versions += 1
        candidate.status = ExtractionCandidateStatus.MATERIALIZED
        candidate.lock_version += 1
        candidate.updated_at = get_datetime_utc()
        session.add(candidate)

    release = _run_release(session, run=run, instrument=instrument)
    entries = _sync_release_entries(
        session,
        release=release,
        run=run,
        instrument=instrument,
        materialized_version_ids=materialized_version_ids,
    )
    manifest = _release_manifest(
        session,
        release=release,
        run=run,
        source=source,
        entries=entries,
    )
    release.source_manifest_hash = _sha256_json(manifest["entries"])
    release.parser_version = PARSER_VERSION
    release.validation_report = {
        "entry_count": len(entries),
        "corpus_legal_status": corpus_legal_status.value,
        "source_edition_review": (run.pipeline_config or {}).get(
            "source_edition_review"
        ),
        "materialized_run_id": str(run.id),
        "ingestion_run_ids": manifest["ingestion_run_ids"],
        "source_document_ids": manifest["source_document_ids"],
        "source_document_count": len(manifest["source_document_ids"]),
        "unresolved_gates": [
            "retrieval_documents_pending",
            "selected_embedding_run_missing",
            (
                "ready_retrieval_index_build_missing"
                if settings.RETRIEVAL_INDEX_BACKEND == "pgvector"
                else "ready_vector_index_missing"
            ),
        ],
    }
    session.add(release)
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST.value,
        filename=f"release-{release.version}.json",
        content=json.dumps(manifest, sort_keys=True).encode(),
        content_type="application/json",
        metadata={
            "release_id": str(release.id),
            "source_manifest_hash": release.source_manifest_hash,
        },
    )
    _ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={
            "release_id": str(release.id),
            "source_manifest_hash": release.source_manifest_hash,
            "entry_count": len(entries),
        },
    )
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "release_version": release.version,
            "candidate_count": len(candidates),
            "created_provisions": created_provisions,
            "created_versions": created_versions,
            "reused_versions": reused_versions,
            "superseded_versions": superseded_versions,
            "release_entry_count": len(entries),
            "source_manifest_hash": release.source_manifest_hash,
        },
        next_stage=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
        next_task_payload={
            "source_document_id": str(source.id),
            "release_id": str(release.id),
        },
    )


def handle_building_retrieval_documents(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    release = _get_release_for_task(session, task)
    entries = _release_entries(session, release.id)
    if not entries:
        raise IngestionWorkerError("Release does not have entries to index")
    versions_by_id = _versions_by_release_entry(entries, session)
    provisions_by_id = _provisions_by_versions(versions_by_id, session)
    retrieval_documents = build_retrieval_documents(
        release_version=release.version,
        entries=entries,
        versions_by_id=versions_by_id,
        provisions_by_id=provisions_by_id,
    )
    if not retrieval_documents:
        raise IngestionWorkerError("Release did not produce retrieval documents")
    payload = {
        "release_id": str(release.id),
        "release_version": release.version,
        "document_count": len(retrieval_documents),
        "documents": [document.to_json() for document in retrieval_documents],
    }
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS.value,
        filename=f"retrieval-documents-{release.version}.json",
        content=json.dumps(payload, sort_keys=True).encode(),
        content_type="application/json",
        metadata={"release_id": str(release.id)},
    )
    _ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={
            "release_id": str(release.id),
            "document_count": len(retrieval_documents),
        },
    )
    release.validation_report = {
        **(release.validation_report or {}),
        "retrieval_document_count": len(retrieval_documents),
        "unresolved_gates": [
            "selected_embedding_run_missing",
            (
                "ready_retrieval_index_build_missing"
                if settings.RETRIEVAL_INDEX_BACKEND == "pgvector"
                else "ready_vector_index_missing"
            ),
        ],
    }
    release.lock_version += 1
    session.add(release)
    session.commit()
    metrics = {
        "release_id": str(release.id),
        "release_version": release.version,
        "retrieval_document_count": len(retrieval_documents),
    }
    if _auto_start_embedding(run) and _active_embedding_profiles(session):
        return StageOutcome(
            metrics=metrics,
            next_stage=IngestionStage.EMBEDDING,
            next_task_payload={
                "source_document_id": str(run.source_document_id),
                "release_id": str(release.id),
            },
        )
    return StageOutcome(
        metrics=metrics,
        next_stage=IngestionStage.EMBEDDING,
        next_status=IngestionRunStatus.READY_TO_EMBED,
        block_next_stage=True,
    )


def handle_embedding(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    release = _get_release_for_task(session, task)
    documents_payload = _retrieval_documents_payload(session, run, release.id)
    documents = _payload_list(documents_payload, "documents")
    texts = [str(document["retrieval_text"]) for document in documents]
    if not texts:
        raise IngestionWorkerError("Release does not have retrieval text to embed")
    profiles = _active_embedding_profiles(session)
    if not profiles:
        raise IngestionWorkerError("No active embedding profiles are configured")
    benchmark_dataset_version, benchmark_query_count = (
        _benchmark_dataset_for_embedding_profiles(session, profiles)
    )
    benchmark_queries = load_retrieval_evaluation_queries(
        session, benchmark_dataset_version
    )
    if len(benchmark_queries) != benchmark_query_count:
        raise IngestionWorkerError("Embedding benchmark query count changed during run")

    sparse_vectors = (
        SparseLegalEncoder().encode(texts)
        if settings.RETRIEVAL_INDEX_BACKEND == "qdrant"
        else []
    )
    embedding_runs: list[EmbeddingRun] = []
    for profile in profiles:
        if profile.is_active and not profile.model_revision:
            raise IngestionWorkerError(
                f"Embedding profile {profile.name} is active but has no pinned model_revision"
            )
        embedding_run = _embedding_run_for_profile(session, release, profile)
        embedding_run.status = EmbeddingRunStatus.RUNNING
        embedding_run.started_at = embedding_run.started_at or get_datetime_utc()
        embedding_run.error_details = None
        session.add(embedding_run)
        session.commit()
        try:
            provider = _embedding_provider_for_profile(profile)
            batch_size = _profile_int(
                profile, "batch_size", default=DEFAULT_EMBEDDING_BATCH_SIZE
            )
            batch = _embed_with_checkpoints(
                session,
                run=run,
                profile=profile,
                embedding_run=embedding_run,
                provider=provider,
                texts=texts,
                batch_size=batch_size,
                kind="documents",
            )
            if batch.dimensions != profile.vector_dimensions:
                raise IngestionWorkerError(
                    "Embedding vector dimensions do not match the profile"
                )
            query_batch = _embed_with_checkpoints(
                session,
                run=run,
                profile=profile,
                embedding_run=embedding_run,
                provider=provider,
                texts=[query.query_text for query in benchmark_queries],
                batch_size=batch_size,
                kind="queries",
            )
            if query_batch.dimensions != profile.vector_dimensions:
                raise IngestionWorkerError(
                    "Benchmark query vector dimensions do not match the profile"
                )
            benchmark = evaluate_embedding_benchmark(
                documents=documents,
                document_vectors=batch.vectors,
                queries=[
                    EmbeddingBenchmarkQuery(
                        item_key=query.item_key,
                        query_text=query.query_text,
                        expected_canonical_paths=query.expected_canonical_paths,
                    )
                    for query in benchmark_queries
                ],
                query_vectors=query_batch.vectors,
            )
            artifact_payload: dict[str, Any] = {
                "release_id": str(release.id),
                "release_version": release.version,
                "embedding_run_id": str(embedding_run.id),
                "profile_id": str(profile.id),
                "provider": profile.provider,
                "model_name": profile.model_name,
                "model_revision": profile.model_revision,
                "benchmark": benchmark.to_metrics(),
                "documents": documents,
                "dense_vectors": batch.vectors,
            }
            if settings.RETRIEVAL_INDEX_BACKEND == "qdrant":
                artifact_payload["sparse_vectors"] = [
                    {"indices": vector.indices, "values": vector.values}
                    for vector in sparse_vectors
                ]
            blob = get_blob_store().put_artifact(
                run_id=str(run.id),
                artifact_type=IngestionArtifactType.EMBEDDINGS.value,
                filename=f"embeddings-{profile.name}.json",
                content=json.dumps(artifact_payload, sort_keys=True).encode(),
                content_type="application/json",
                metadata={
                    "release_id": str(release.id),
                    "embedding_run_id": str(embedding_run.id),
                    "profile_id": str(profile.id),
                },
            )
            _ensure_artifact(
                session,
                run_id=run.id,
                artifact_type=IngestionArtifactType.EMBEDDINGS,
                storage_key=blob.key,
                sha256=blob.sha256,
                mime_type=blob.content_type,
                metadata={
                    "release_id": str(release.id),
                    "embedding_run_id": str(embedding_run.id),
                    "profile_id": str(profile.id),
                    "document_count": len(documents),
                    "vector_dimensions": batch.dimensions,
                },
            )
            embedding_run.status = EmbeddingRunStatus.SUCCEEDED
            embedding_run.completed_at = get_datetime_utc()
            embedding_run.benchmark_dataset_version = benchmark_dataset_version
            embedding_run.recall_at_10 = benchmark.recall_at_10
            embedding_run.ndcg_at_10 = benchmark.ndcg_at_10
            reported_cost = _sum_optional_costs(batch.cost_usd, query_batch.cost_usd)
            embedding_run.cost_usd = (
                reported_cost
                if reported_cost is not None
                else _profile_float(profile, "estimated_cost_usd")
            )
            embedding_run.p95_latency_ms = _profile_float(profile, "p95_latency_ms")
            embedding_run.metrics = {
                "document_embedding_metrics": batch.metrics or {},
                "query_embedding_metrics": query_batch.metrics or {},
                "benchmark_dataset_version": benchmark_dataset_version,
                **benchmark.to_metrics(),
                "document_count": len(documents),
                "vector_dimensions": batch.dimensions,
                "sparse_vector_count": len(sparse_vectors),
            }
        except Exception as exc:
            embedding_run.status = EmbeddingRunStatus.FAILED
            embedding_run.completed_at = get_datetime_utc()
            embedding_run.error_details = {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
        session.add(embedding_run)
        session.commit()
        session.refresh(embedding_run)
        embedding_runs.append(embedding_run)

    selected_run = select_best_embedding_run(embedding_runs)
    if not selected_run:
        failures = [item.error_details for item in embedding_runs if item.error_details]
        if failures:
            raise IngestionWorkerError(
                f"Embedding provider failures: {json.dumps(failures)}"
            )
        raise IngestionWorkerError(
            "No embedding run reached the Recall@10 publication threshold"
        )
    selected_run.selected_for_release = True
    selected_profile = session.get(EmbeddingProfile, selected_run.profile_id)
    if not selected_profile:
        raise IngestionWorkerError("Selected embedding profile was not found")
    release.embedding_model = selected_profile.model_name
    release.embedding_model_version = selected_profile.model_revision
    release.validation_report = {
        **(release.validation_report or {}),
        "selected_embedding_run_id": str(selected_run.id),
        "embedding_profile_id": str(selected_profile.id),
        "unresolved_gates": [
            *[
                gate
                for gate in (release.validation_report or {}).get(
                    "unresolved_gates", []
                )
                if gate
                not in {
                    "selected_embedding_run_missing",
                    "retrieval_documents_pending",
                    "ready_retrieval_index_build_missing",
                    "ready_vector_index_missing",
                }
            ],
            (
                "ready_retrieval_index_build_missing"
                if settings.RETRIEVAL_INDEX_BACKEND == "pgvector"
                else "ready_vector_index_missing"
            ),
        ],
    }
    release.lock_version += 1
    session.add(selected_run)
    session.add(release)
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "embedding_run_count": len(embedding_runs),
            "selected_embedding_run_id": str(selected_run.id),
            "selected_model": selected_profile.model_name,
        },
        next_stage=IngestionStage.INDEXING,
        next_status=IngestionRunStatus.INDEXING,
        next_task_payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release.id),
            "embedding_run_id": str(selected_run.id),
        },
    )


def _embed_with_checkpoints(
    session: Session,
    *,
    run: IngestionRun,
    profile: EmbeddingProfile,
    embedding_run: EmbeddingRun,
    provider: DenseEmbeddingProvider,
    texts: list[str],
    batch_size: int,
    kind: str,
) -> EmbeddingBatch:
    size = max(1, batch_size)
    if len(texts) <= size:
        return provider.embed(texts)
    artifacts = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).all()
    checkpoints = {
        item.artifact_metadata.get("checkpoint_key"): item
        for item in artifacts
        if item.artifact_metadata and item.artifact_metadata.get("checkpoint_key")
    }
    vectors: list[list[float]] = []
    first: EmbeddingBatch | None = None
    costs: list[float | None] = []
    for offset in range(0, len(texts), size):
        inputs = texts[offset : offset + size]
        key = _sha256_json(
            {
                "profile_id": str(profile.id),
                "model_name": profile.model_name,
                "model_revision": profile.model_revision,
                "provider": str(profile.provider),
                "vector_dimensions": profile.vector_dimensions,
                "configuration": profile.configuration,
                "kind": kind,
                "offset": offset,
                "inputs": inputs,
            }
        )
        cached = checkpoints.get(key)
        if cached:
            content = get_blob_store().read_bytes(cached.storage_key)
            if hashlib.sha256(content).hexdigest() != cached.sha256:
                raise IngestionWorkerError("Embedding checkpoint hash mismatch")
            payload = _json_object(content)
            raw_vectors = payload["vectors"]
            batch = EmbeddingBatch(
                provider=str(payload["provider"]),
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[_float_vector(value) for value in raw_vectors],
                cost_usd=payload.get("cost_usd"),
                metrics=payload.get("metrics"),
            )
        else:
            batch = provider.embed(inputs)
            if len(batch.vectors) != len(inputs) or any(
                len(vector) != profile.vector_dimensions for vector in batch.vectors
            ):
                raise IngestionWorkerError(
                    "Embedding batch count or dimensions mismatch"
                )
            content = json.dumps(
                {
                    "provider": batch.provider,
                    "vectors": batch.vectors,
                    "cost_usd": batch.cost_usd,
                    "metrics": batch.metrics,
                },
                sort_keys=True,
            ).encode()
            content_hash = hashlib.sha256(content).hexdigest()
            blob = get_blob_store().put_artifact(
                run_id=str(run.id),
                artifact_type=IngestionArtifactType.EMBEDDINGS.value,
                filename=f"batch-{key}-{content_hash}.json",
                content=content,
                content_type="application/json",
            )
            _ensure_artifact(
                session,
                run_id=run.id,
                artifact_type=IngestionArtifactType.EMBEDDINGS,
                storage_key=blob.key,
                sha256=blob.sha256,
                mime_type=blob.content_type,
                metadata={
                    "checkpoint_key": key,
                    "profile_id": str(profile.id),
                    "kind": kind,
                    "offset": offset,
                    "input_count": len(inputs),
                },
            )
        if len(batch.vectors) != len(inputs) or any(
            len(vector) != profile.vector_dimensions for vector in batch.vectors
        ):
            raise IngestionWorkerError(
                "Embedding checkpoint count or dimensions mismatch"
            )
        first = first or batch
        vectors.extend(batch.vectors)
        costs.append(batch.cost_usd)
        embedding_run.metrics = {
            **(embedding_run.metrics or {}),
            f"{kind}_progress": {
                "completed": len(vectors),
                "total": len(texts),
                "batch_size": size,
            },
        }
        session.add(embedding_run)
        session.commit()
    assert first is not None
    return EmbeddingBatch(
        provider=first.provider,
        model_name=first.model_name,
        model_revision=first.model_revision,
        vectors=vectors,
        cost_usd=(
            sum(cast(list[float], costs))
            if all(cost is not None for cost in costs)
            else None
        ),
        metrics={**(first.metrics or {}), "batched_batches": len(costs)},
    )


def handle_indexing(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    release = _get_release_for_task(session, task)
    embedding_run = _get_embedding_run_for_task(session, task)
    profile = session.get(EmbeddingProfile, embedding_run.profile_id)
    if not profile:
        raise IngestionWorkerError("Embedding run is missing its profile")
    if settings.RETRIEVAL_INDEX_BACKEND == "pgvector":
        return _handle_pgvector_indexing(
            session,
            run=run,
            release=release,
            embedding_run=embedding_run,
            profile=profile,
        )
    payload = _embedding_payload(session, run, embedding_run.id)
    points = _qdrant_points_from_embedding_payload(payload)
    report = validate_qdrant_points(points, vector_dimensions=profile.vector_dimensions)
    validation_report: dict[str, Any] = {
        "is_valid": report.is_valid,
        "duplicate_ids": report.duplicate_ids,
        "dimension_errors": report.dimension_errors,
        "payload_errors": report.payload_errors,
        "sparse_errors": report.sparse_errors,
    }
    index_kind = _index_kind_for_points(points)
    profile_hash = _sha256_json(profile.configuration)
    collection_name = collection_name_for_release(
        release_version=release.version,
        embedding_profile_name=profile.name,
        profile_hash=profile_hash,
        index_kind=index_kind,
    )
    vector_index = _vector_index_for_collection(
        session,
        release=release,
        embedding_run=embedding_run,
        profile=profile,
        collection_name=collection_name,
        index_kind=index_kind,
        profile_hash=profile_hash,
    )
    vector_index.point_count = report.point_count
    vector_index.payload_schema_hash = report.payload_schema_hash
    vector_index.checksum = report.checksum
    vector_index.validation_report = validation_report
    if not report.is_valid:
        vector_index.status = VectorIndexStatus.FAILED
        session.add(vector_index)
        session.commit()
        raise IngestionWorkerError("Qdrant point validation failed")
    adapter = _qdrant_adapter()
    adapter.create_collection(
        collection_name=collection_name,
        vector_dimensions=profile.vector_dimensions,
    )
    adapter.upsert_points(collection_name=collection_name, points=points)
    remote_count = adapter.read_point_count(collection_name=collection_name)
    if remote_count != len(points):
        vector_index.status = VectorIndexStatus.FAILED
        vector_index.validation_report = {
            **(vector_index.validation_report or {}),
            "remote_point_count": remote_count,
        }
        session.add(vector_index)
        session.commit()
        raise IngestionWorkerError("Qdrant point count validation failed")
    smoke_queries = _run_qdrant_smoke_queries(
        adapter,
        collection_name=collection_name,
        points=points,
    )
    validation_report = {
        **validation_report,
        "remote_point_count": remote_count,
        "smoke_queries": smoke_queries,
    }
    vector_index.validation_report = validation_report
    if any(not query["passed"] for query in smoke_queries):
        vector_index.status = VectorIndexStatus.FAILED
        vector_index.updated_at = get_datetime_utc()
        session.add(vector_index)
        session.commit()
        raise IngestionWorkerError("Qdrant smoke-query validation failed")
    vector_index.status = VectorIndexStatus.VALIDATING
    vector_index.point_count = remote_count
    vector_index.updated_at = get_datetime_utc()
    session.add(vector_index)
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "vector_index_id": str(vector_index.id),
            "collection_name": collection_name,
            "point_count": remote_count,
        },
        next_stage=IngestionStage.VALIDATING_INDEX,
        next_status=IngestionRunStatus.INDEXING,
        next_task_payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release.id),
            "vector_index_id": str(vector_index.id),
        },
    )


def _handle_pgvector_indexing(
    session: Session,
    *,
    run: IngestionRun,
    release: CorpusRelease,
    embedding_run: EmbeddingRun,
    profile: EmbeddingProfile,
) -> StageOutcome:
    if embedding_run.status != EmbeddingRunStatus.SUCCEEDED:
        raise IngestionWorkerError(
            "Only a succeeded embedding run may be loaded into pgvector"
        )
    if profile.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        raise IngestionWorkerError(
            "The active embedding profile dimensions do not match the retrieval schema"
        )
    payload = _embedding_payload(session, run, embedding_run.id)
    documents_payload = _payload_list(payload, "documents")
    vectors = payload.get("dense_vectors")
    if not isinstance(vectors, list):
        raise IngestionWorkerError("Embedding artifact did not contain dense vectors")
    documents: list[RetrievalDocument] = []
    for item in documents_payload:
        raw_payload = item.get("payload")
        if not isinstance(raw_payload, dict):
            raise IngestionWorkerError("Retrieval document payload was invalid")
        documents.append(
            RetrievalDocument(
                document_id=str(item.get("id", "")),
                segment_id=str(item.get("segment_id", "")),
                release_version=str(item.get("release_version", release.version)),
                citation=str(item.get("citation", "")),
                ancestor_headings=[
                    str(value) for value in item.get("ancestor_headings", [])
                ],
                heading=(
                    str(item["heading"]) if item.get("heading") is not None else None
                ),
                authoritative_text=str(item.get("authoritative_text", "")),
                retrieval_text=str(item.get("retrieval_text", "")),
                payload=cast(dict[str, object], raw_payload),
            )
        )
    index_kind = _index_kind_for_documents(documents)
    try:
        segments = write_segments(
            session,
            release_id=release.id,
            documents=documents,
            index_kind=index_kind,
        )
        vector_values = [
            _float_vector(value) if isinstance(value, list) else [] for value in vectors
        ]
        embeddings = write_embeddings(
            session,
            release_id=release.id,
            embedding_run=embedding_run,
            profile=profile,
            segments=segments,
            vectors=vector_values,
        )
    except PgVectorRetrievalError as exc:
        raise IngestionWorkerError(str(exc)) from exc
    profile_hash = _sha256_json(
        {
            "name": profile.name,
            "model_name": profile.model_name,
            "model_revision": profile.model_revision,
            "configuration": profile.configuration,
        }
    )
    build = session.exec(
        select(RetrievalIndexBuild).where(
            RetrievalIndexBuild.release_id == release.id,
            RetrievalIndexBuild.embedding_run_id == embedding_run.id,
            RetrievalIndexBuild.index_kind == index_kind,
        )
    ).first()
    if build is None:
        build = RetrievalIndexBuild(
            release_id=release.id,
            embedding_run_id=embedding_run.id,
            profile_id=profile.id,
            backend="pgvector",
            index_kind=index_kind,
            expected_segment_count=len(documents),
            vector_dimensions=profile.vector_dimensions,
            profile_hash=profile_hash,
        )
    elif build.status in {VectorIndexStatus.READY, VectorIndexStatus.PROMOTED}:
        raise IngestionWorkerError("A ready pgvector build is immutable")
    build.expected_segment_count = len(documents)
    build.stored_segment_count = len(segments)
    build.stored_embedding_count = len(embeddings)
    build.profile_hash = profile_hash
    build.vector_dimensions = profile.vector_dimensions
    build.status = VectorIndexStatus.VALIDATING
    build.updated_at = get_datetime_utc()
    build.validation_report = {
        "backend": "pgvector",
        "index_kind": index_kind,
        "exact_search": True,
        "candidate_limits": {
            "dense": settings.RETRIEVAL_DENSE_CANDIDATE_LIMIT,
            "lexical": settings.RETRIEVAL_LEXICAL_CANDIDATE_LIMIT,
        },
    }
    session.add(build)
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "retrieval_index_build_id": str(build.id),
            "backend": "pgvector",
            "index_kind": index_kind,
            "segment_count": len(segments),
            "embedding_count": len(embeddings),
        },
        next_stage=IngestionStage.VALIDATING_INDEX,
        next_status=IngestionRunStatus.INDEXING,
        next_task_payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release.id),
            "retrieval_index_build_id": str(build.id),
        },
    )


def handle_validating_index(
    session: Session, _run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    retrieval_index_build_id = task.payload.get("retrieval_index_build_id")
    if retrieval_index_build_id:
        build = session.get(
            RetrievalIndexBuild, uuid.UUID(str(retrieval_index_build_id))
        )
        if not build:
            raise IngestionWorkerError("Retrieval index build was not found")
        report = validate_index_build(
            session,
            build=build,
            expected_segment_count=build.expected_segment_count,
        )
        build.validation_report = report
        build.stored_segment_count = int(report["stored_segment_count"])
        build.stored_embedding_count = int(report["stored_embedding_count"])
        build.checksum = _sha256_json(
            {
                "segment_checksum": report["segment_checksum"],
                "embedding_checksum": report["embedding_checksum"],
            }
        )
        if not report["is_valid"]:
            build.status = VectorIndexStatus.FAILED
            session.add(build)
            session.commit()
            raise IngestionWorkerError("pgvector validation did not pass")
        build.status = VectorIndexStatus.READY
        build.updated_at = get_datetime_utc()
        session.add(build)
        release = session.get(CorpusRelease, build.release_id)
        if release:
            release.validation_report = {
                **(release.validation_report or {}),
                "ready_retrieval_index_build_id": str(build.id),
                "unresolved_gates": [
                    gate
                    for gate in (release.validation_report or {}).get(
                        "unresolved_gates", []
                    )
                    if gate != "ready_retrieval_index_build_missing"
                ],
            }
            release.lock_version += 1
            session.add(release)
        session.commit()
        return StageOutcome(
            metrics={
                "retrieval_index_build_id": str(build.id),
                "segment_count": build.stored_segment_count,
                "embedding_count": build.stored_embedding_count,
                "checksum": build.checksum,
            },
            next_stage=IngestionStage.PUBLISHING,
            next_status=IngestionRunStatus.READY_TO_PUBLISH,
            block_next_stage=True,
        )
    vector_index_id = task.payload.get("vector_index_id")
    if not vector_index_id:
        raise IngestionWorkerError("Task does not identify a vector index")
    vector_index = session.get(VectorIndex, uuid.UUID(str(vector_index_id)))
    if not vector_index:
        raise IngestionWorkerError("Vector index was not found")
    report = vector_index.validation_report or {}
    if vector_index.point_count <= 0 or report.get("is_valid") is False:
        raise IngestionWorkerError("Vector index validation did not pass")
    vector_index.status = VectorIndexStatus.READY
    vector_index.updated_at = get_datetime_utc()
    session.add(vector_index)
    release = session.get(CorpusRelease, vector_index.release_id)
    if release:
        release.validation_report = {
            **(release.validation_report or {}),
            "ready_vector_index_id": str(vector_index.id),
            "unresolved_gates": [],
        }
        release.lock_version += 1
        session.add(release)
    session.commit()
    return StageOutcome(
        metrics={
            "vector_index_id": str(vector_index.id),
            "point_count": vector_index.point_count,
            "checksum": vector_index.checksum,
        },
        next_stage=IngestionStage.PUBLISHING,
        next_status=IngestionRunStatus.READY_TO_PUBLISH,
        block_next_stage=True,
    )


def _handler_for(stage: IngestionStage) -> StageHandler:
    handlers: dict[IngestionStage, StageHandler] = {
        IngestionStage.VERIFYING_UPLOAD: handle_verifying_upload,
        IngestionStage.MALWARE_SCAN: handle_malware_scan,
        IngestionStage.PROFILING: handle_profiling,
        IngestionStage.RENDERING: handle_rendering,
        IngestionStage.NATIVE_EXTRACTION: handle_native_extraction,
        IngestionStage.LOCAL_OCR: handle_local_ocr,
        IngestionStage.MANAGED_OCR: handle_managed_ocr,
        IngestionStage.NORMALIZING: handle_normalizing,
        IngestionStage.PARSING_STRUCTURE: handle_parsing_structure,
        IngestionStage.VALIDATING_DOCUMENT: handle_validating_document,
        IngestionStage.MATERIALIZING: handle_materializing,
        IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS: handle_building_retrieval_documents,
        IngestionStage.EMBEDDING: handle_embedding,
        IngestionStage.INDEXING: handle_indexing,
        IngestionStage.VALIDATING_INDEX: handle_validating_index,
    }
    try:
        return handlers[stage]
    except KeyError:
        raise IngestionWorkerError(f"No worker handler is registered for {stage.value}")


def _advance_run_after_success(
    session: Session,
    run: IngestionRun,
    *,
    outcome: StageOutcome,
    commit: bool = True,
) -> None:
    now = get_datetime_utc()
    run.status = outcome.next_status
    if outcome.next_stage:
        run.current_stage = outcome.next_stage
    run.completed_units += 1
    run.lock_version += 1
    run.updated_at = now
    session.add(run)
    for skipped_stage in outcome.skipped_stages:
        skipped_step = _get_step(session, run.id, skipped_stage, None)
        skipped_step.status = IngestionStepStatus.SKIPPED
        skipped_step.completed_at = now
        skipped_step.updated_at = now
        skipped_step.lock_version += 1
        session.add(skipped_step)
    if outcome.next_stage and outcome.block_next_stage:
        next_step = _get_step(session, run.id, outcome.next_stage, None)
        next_step.status = IngestionStepStatus.BLOCKED
        next_step.metrics = outcome.metrics
        next_step.updated_at = now
        session.add(next_step)
        append_run_event(
            session,
            run,
            event_type="stage_blocked",
            message=f"{outcome.next_stage.value} requires admin input",
            step=next_step,
            payload=outcome.metrics,
            commit=False,
        )
    elif outcome.next_stage:
        next_step = _get_step(session, run.id, outcome.next_stage, None)
        enqueue_task(
            session,
            run=run,
            step=next_step,
            task_type=outcome.next_stage.value,
            idempotency_key=f"{run.id}:{outcome.next_stage.value}",
            payload=outcome.next_task_payload or {},
            priority=_priority_for_stage(outcome.next_stage),
            commit=False,
        )
    if commit:
        session.commit()
    else:
        session.flush()


def _handle_stage_failure(
    session: Session,
    *,
    run: IngestionRun,
    step: IngestionStep,
    task: IngestionTask,
    stage: IngestionStage,
    exc: Exception,
) -> WorkerResult:
    error_details = {
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }
    failed_or_retryable_task = fail_task(session, task, error_details)
    now = get_datetime_utc()
    step.error_details = error_details
    step.heartbeat_at = now
    step.updated_at = now
    if failed_or_retryable_task.status == IngestionTaskStatus.FAILED:
        step.status = IngestionStepStatus.FAILED
        step.completed_at = now
        run.status = IngestionRunStatus.FAILED
        if stage == IngestionStage.VERIFYING_UPLOAD:
            upload_id = task.payload.get("source_upload_id") or run.source_upload_id
            if upload_id:
                upload = session.get(SourceUpload, uuid.UUID(str(upload_id)))
                if upload:
                    upload.status = SourceUploadStatus.FAILED
                    upload.error_message = str(exc)[:2000]
                    upload.updated_at = now
                    upload.lock_version += 1
                    session.add(upload)
        run.failed_units += 1
        run.error_details = error_details
        run.updated_at = now
        session.add(run)
    else:
        step.status = IngestionStepStatus.PENDING
    session.add(step)
    session.commit()
    append_run_event(
        session,
        run,
        event_type="stage_failed",
        message=str(exc),
        step=step,
        payload=error_details,
    )
    session.refresh(run)
    return WorkerResult(
        task_id=failed_or_retryable_task.id,
        run_id=run.id,
        stage=stage,
        task_status=failed_or_retryable_task.status,
        run_status=run.status,
    )


def _mark_step_running(
    session: Session,
    step: IngestionStep,
    *,
    worker_id: str,
    started_at: datetime,
) -> None:
    now = get_datetime_utc()
    step.status = IngestionStepStatus.RUNNING
    step.lease_owner = worker_id
    step.heartbeat_at = now
    step.started_at = step.started_at or started_at
    step.attempt_count += 1
    step.lock_version += 1
    step.updated_at = now
    session.add(step)
    session.commit()


def _mark_step_succeeded(
    session: Session,
    step: IngestionStep,
    *,
    metrics: dict[str, Any],
    commit: bool = True,
) -> None:
    now = get_datetime_utc()
    step.status = IngestionStepStatus.SUCCEEDED
    step.lease_owner = None
    step.leased_until = None
    step.heartbeat_at = now
    step.metrics = metrics
    step.completed_units = step.total_units or 1
    step.completed_at = now
    step.lock_version += 1
    step.updated_at = now
    session.add(step)
    if commit:
        session.commit()
    else:
        session.flush()


def _mark_run_running(
    session: Session, run: IngestionRun, *, stage: IngestionStage
) -> None:
    run.status = IngestionRunStatus.RUNNING
    run.current_stage = stage
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add(run)
    session.commit()


def _get_run(session: Session, run_id: uuid.UUID) -> IngestionRun:
    run = session.get(IngestionRun, run_id)
    if not run:
        raise IngestionWorkerError("Ingestion run was not found")
    return run


def _get_step(
    session: Session,
    run_id: uuid.UUID,
    stage: IngestionStage,
    task_step_id: uuid.UUID | None,
) -> IngestionStep:
    if task_step_id:
        step = session.get(IngestionStep, task_step_id)
        if step:
            return step
    step = session.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run_id,
            IngestionStep.stage == stage,
        )
    ).first()
    if not step:
        raise IngestionWorkerError(f"Ingestion step {stage.value} was not found")
    return step


def _get_source_for_run(
    session: Session, run: IngestionRun, task: IngestionTask
) -> SourceDocument:
    source_id = task.payload.get("source_document_id") or run.source_document_id
    if not source_id:
        raise IngestionWorkerError("Task does not identify a source document")
    source = session.get(SourceDocument, uuid.UUID(str(source_id)))
    if not source:
        raise IngestionWorkerError("Source document was not found")
    return source


def _get_upload_for_run(
    session: Session, run: IngestionRun, task: IngestionTask
) -> SourceUpload:
    upload_id = task.payload.get("source_upload_id") or run.source_upload_id
    if not upload_id:
        raise IngestionWorkerError("Task does not identify a source upload")
    upload = session.get(SourceUpload, uuid.UUID(str(upload_id)))
    if not upload:
        raise IngestionWorkerError("Source upload was not found")
    return upload


def _read_upload_bytes(upload: SourceUpload) -> bytes:
    try:
        return get_blob_store().read_bytes(upload.quarantine_key)
    except FileNotFoundError:
        raise IngestionWorkerError("Quarantined upload file was not found")


def _read_source_bytes(source: SourceDocument) -> bytes:
    try:
        return get_blob_store().read_bytes(_require_storage_key(source))
    except FileNotFoundError:
        raise IngestionWorkerError("Stored source document file was not found")


def _require_storage_key(source: SourceDocument) -> str:
    if not source.storage_key:
        raise IngestionWorkerError("Source document does not have a stored file")
    return source.storage_key


def _ensure_artifact(
    session: Session,
    *,
    run_id: uuid.UUID,
    source_page_id: uuid.UUID | None = None,
    artifact_type: IngestionArtifactType,
    storage_key: str,
    sha256: str | None,
    mime_type: str | None,
    retention_policy: str = "retain_indefinitely",
    metadata: dict[str, Any],
) -> IngestionArtifact:
    existing = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run_id,
            IngestionArtifact.artifact_type == artifact_type,
            IngestionArtifact.storage_key == storage_key,
        )
    ).first()
    if existing:
        return existing
    artifact = IngestionArtifact(
        run_id=run_id,
        source_page_id=source_page_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        sha256=sha256,
        mime_type=mime_type,
        retention_policy=retention_policy,
        artifact_metadata=metadata,
    )
    session.add(artifact)
    return artifact


def _upsert_source_page(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    profile: Any,
) -> SourcePage:
    page = session.exec(
        select(SourcePage).where(
            SourcePage.run_id == run.id,
            SourcePage.page_number == profile.page_number,
        )
    ).first()
    if not page:
        page = SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=profile.page_number,
        )
    page.role = profile.role
    if page.inclusion_status in {
        PageInclusionStatus.SUGGESTED_INCLUDE,
        PageInclusionStatus.SUGGESTED_EXCLUDE,
    }:
        page.inclusion_status = profile.inclusion_status
        page.inclusion_reason = profile.inclusion_reason
    page.text_density = profile.text_density
    page.orientation = profile.orientation
    page.column_count = profile.column_count
    page.image_coverage = profile.image_coverage
    page.width = profile.width
    page.height = profile.height
    page.quality_signals = {
        **profile.quality_signals,
        "preview_text": profile.extracted_text[:4000],
        "preview_provisional": True,
    }
    page.lock_version += 1
    session.add(page)
    return page


def _pages_for_run(session: Session, run: IngestionRun) -> list[SourcePage]:
    return list(
        session.exec(
            select(SourcePage)
            .where(SourcePage.run_id == run.id)
            .order_by(col(SourcePage.page_number))
        ).all()
    )


def _approved_candidates_for_run(
    session: Session, run: IngestionRun
) -> list[ExtractionCandidate]:
    candidates = list(
        session.exec(
            select(ExtractionCandidate)
            .where(ExtractionCandidate.run_id == run.id)
            .order_by(col(ExtractionCandidate.sort_key), col(ExtractionCandidate.id))
        ).all()
    )
    unapproved = [
        candidate
        for candidate in candidates
        if candidate.status
        not in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.AUTO_APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }
    ]
    if unapproved:
        raise IngestionWorkerError(
            "All extraction candidates must be approved before materialization"
        )
    return candidates


def _ensure_no_open_blocking_issues(
    session: Session, candidates: list[ExtractionCandidate]
) -> None:
    candidate_ids = [candidate.id for candidate in candidates]
    if not candidate_ids:
        return
    issue = session.exec(
        select(ReviewIssue).where(
            col(ReviewIssue.candidate_id).in_(candidate_ids),
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    if issue:
        raise IngestionWorkerError(
            "Blocking review issues must be resolved before materialization"
        )


def _parent_provision_id_for_candidate(
    session: Session,
    candidate: ExtractionCandidate,
    *,
    provision_ids_by_candidate_id: dict[uuid.UUID, uuid.UUID],
) -> uuid.UUID | None:
    if not candidate.parent_candidate_id:
        return None
    parent_id = provision_ids_by_candidate_id.get(candidate.parent_candidate_id)
    if parent_id:
        return parent_id
    parent_candidate = session.get(ExtractionCandidate, candidate.parent_candidate_id)
    if parent_candidate and parent_candidate.materialized_provision_id:
        return parent_candidate.materialized_provision_id
    raise IngestionWorkerError(
        f"Parent candidate for {candidate.canonical_path} is not materialized"
    )


def _upsert_provision_from_candidate(
    session: Session,
    *,
    instrument: LegalInstrument,
    candidate: ExtractionCandidate,
    parent_id: uuid.UUID | None,
) -> tuple[Provision, bool]:
    provision = session.exec(
        select(Provision).where(Provision.canonical_path == candidate.canonical_path)
    ).first()
    created = False
    if not provision:
        provision = Provision(
            instrument_id=instrument.id,
            parent_id=parent_id,
            kind=candidate.kind,
            number=candidate.number,
            heading=candidate.heading,
            canonical_path=candidate.canonical_path,
            sort_key=candidate.sort_key,
        )
        created = True
    else:
        provision.instrument_id = instrument.id
        provision.parent_id = parent_id
        provision.kind = candidate.kind
        provision.number = candidate.number
        provision.heading = candidate.heading
        provision.sort_key = candidate.sort_key
    session.add(provision)
    session.flush()
    return provision, created


def _candidate_text_for_materialization(
    session: Session, candidate: ExtractionCandidate
) -> str | None:
    revision = session.exec(
        select(CandidateRevision)
        .where(CandidateRevision.candidate_id == candidate.id)
        .order_by(col(CandidateRevision.revision_number).desc())
    ).first()
    text = revision.revised_text if revision else candidate.raw_text
    if not text or not text.strip():
        return None
    return text.strip()


def _corpus_legal_status(run: IngestionRun) -> LegalStatus:
    value = (run.pipeline_config or {}).get("corpus_legal_status", "current")
    if value not in {LegalStatus.CURRENT.value, LegalStatus.HISTORICAL.value}:
        raise IngestionWorkerError("Corpus legal status must be current or historical")
    return LegalStatus(value)


def _upsert_historical_version_from_candidate(
    session: Session,
    *,
    source: SourceDocument,
    instrument: LegalInstrument,
    provision: Provision,
    candidate: ExtractionCandidate,
    text: str,
) -> tuple[ProvisionVersion, str]:
    """Store a source edition without changing or reusing current-law versions."""
    text_sha256 = legal_text_sha256(text)
    versions = session.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == provision.id)
    ).all()
    for version in versions:
        if (
            version.legal_status == LegalStatus.HISTORICAL
            and version.source_document_id == source.id
            and version.text_sha256 == text_sha256
        ):
            return version, "reused"
    if versions:
        raise IngestionWorkerError(
            "Historical source editions need a separate provision identity or "
            "reviewed validity dates when versions already exist"
        )
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalize_legal_text(text),
        valid_from=_version_valid_from(instrument, source),
        legal_status=LegalStatus.HISTORICAL,
        source_document_id=source.id,
        source_page_start=candidate.source_page_start,
        source_page_end=candidate.source_page_end,
        text_sha256=text_sha256,
    )
    session.add(version)
    session.flush()
    return version, "created"


def _upsert_current_version_from_candidate(
    session: Session,
    *,
    source: SourceDocument,
    instrument: LegalInstrument,
    provision: Provision,
    candidate: ExtractionCandidate,
    text: str,
) -> tuple[ProvisionVersion, str]:
    normalized_text = normalize_legal_text(text)
    text_sha256 = legal_text_sha256(text)
    current_version = _current_version_for_provision(session, provision.id)
    if current_version and current_version.text_sha256 == text_sha256:
        return current_version, "reused"
    if current_version:
        if not source.is_legal_revision or not source.legal_revision_effective_at:
            raise IngestionWorkerError(
                "Changed current-law text requires legal revision metadata"
            )
        if source.legal_revision_effective_at <= current_version.valid_from:
            raise IngestionWorkerError(
                "Legal revision effective date must be after the current version start"
            )
        current_version.legal_status = LegalStatus.SUPERSEDED
        current_version.valid_until = source.legal_revision_effective_at
        session.add(current_version)
        version = ProvisionVersion(
            provision_id=provision.id,
            text=text,
            normalized_text=normalized_text,
            valid_from=source.legal_revision_effective_at,
            legal_status=LegalStatus.CURRENT,
            revision_number=_next_version_number(session, provision.id),
            source_document_id=source.id,
            source_page_start=candidate.source_page_start,
            source_page_end=candidate.source_page_end,
            text_sha256=text_sha256,
            supersedes_id=current_version.id,
        )
        session.add(version)
        session.flush()
        candidate.normalized_text = normalized_text
        candidate.text_sha256 = text_sha256
        return version, "superseded"

    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalized_text,
        valid_from=_version_valid_from(instrument, source),
        legal_status=LegalStatus.CURRENT,
        revision_number=_next_version_number(session, provision.id),
        source_document_id=source.id,
        source_page_start=candidate.source_page_start,
        source_page_end=candidate.source_page_end,
        text_sha256=text_sha256,
    )
    session.add(version)
    session.flush()
    candidate.normalized_text = normalized_text
    candidate.text_sha256 = text_sha256
    return version, "created"


def _block_unclassified_current_law_changes(
    session: Session,
    *,
    source: SourceDocument,
    candidates: list[ExtractionCandidate],
) -> int:
    if source.is_legal_revision and source.legal_revision_effective_at:
        return 0
    blocked = 0
    for candidate in candidates:
        text = _candidate_text_for_materialization(session, candidate)
        if not text:
            continue
        provision = session.exec(
            select(Provision).where(
                Provision.canonical_path == candidate.canonical_path
            )
        ).first()
        if not provision:
            continue
        current_version = _current_version_for_provision(session, provision.id)
        if not current_version:
            continue
        candidate_text_sha256 = legal_text_sha256(text)
        if current_version.text_sha256 == candidate_text_sha256:
            continue
        _ensure_review_issue(
            session,
            candidate=candidate,
            issue_type="changed_current_law_text",
            severity=ReviewIssueSeverity.BLOCKING,
            blocking=True,
            message=(
                "Candidate text differs from the current law. Mark the source as a "
                "legal revision and provide its effective date before materializing."
            ),
            evidence={
                "canonical_path": candidate.canonical_path,
                "current_version_id": str(current_version.id),
                "current_text_sha256": current_version.text_sha256,
                "candidate_text_sha256": candidate_text_sha256,
            },
        )
        candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
        candidate.blocking_issue_count = max(candidate.blocking_issue_count, 1)
        candidate.updated_at = get_datetime_utc()
        session.add(candidate)
        blocked += 1
    return blocked


def _current_version_for_provision(
    session: Session, provision_id: uuid.UUID
) -> ProvisionVersion | None:
    return session.exec(
        select(ProvisionVersion)
        .where(
            ProvisionVersion.provision_id == provision_id,
            ProvisionVersion.legal_status == LegalStatus.CURRENT,
            col(ProvisionVersion.valid_until).is_(None),
        )
        .order_by(col(ProvisionVersion.revision_number).desc())
    ).first()


def _next_version_number(session: Session, provision_id: uuid.UUID) -> int:
    latest = session.exec(
        select(ProvisionVersion)
        .where(ProvisionVersion.provision_id == provision_id)
        .order_by(col(ProvisionVersion.revision_number).desc())
    ).first()
    return (latest.revision_number if latest else 0) + 1


def _version_valid_from(instrument: LegalInstrument, source: SourceDocument) -> date:
    return (
        instrument.effective_at
        or instrument.enacted_at
        or source.published_at
        or get_datetime_utc().date()
    )


def _run_release(
    session: Session, *, run: IngestionRun, instrument: LegalInstrument
) -> CorpusRelease:
    version = f"draft-{run.id.hex[:12]}"
    release = session.exec(
        select(CorpusRelease).where(CorpusRelease.version == version)
    ).first()
    if release:
        return release
    release = CorpusRelease(
        version=version,
        status=CorpusReleaseStatus.BUILDING,
        parser_version=PARSER_VERSION,
        validation_report={
            "instrument_slug": instrument.slug,
            "materialized_run_id": str(run.id),
        },
    )
    session.add(release)
    session.flush()
    return release


def _sync_release_entries(
    session: Session,
    *,
    release: CorpusRelease,
    run: IngestionRun,
    instrument: LegalInstrument,
    materialized_version_ids: set[uuid.UUID],
) -> list[CorpusReleaseEntry]:
    versions = (
        list(
            session.exec(
                select(ProvisionVersion)
                .where(col(ProvisionVersion.id).in_(materialized_version_ids))
                .order_by(col(ProvisionVersion.id))
            ).all()
        )
        if _corpus_legal_status(run) == LegalStatus.HISTORICAL
        else _current_versions_for_instrument(session, instrument.id)
    )
    run_ids_by_version = _materialized_run_ids_by_version(
        session, [version.id for version in versions]
    )
    existing = {
        entry.provision_version_id: entry
        for entry in session.exec(
            select(CorpusReleaseEntry).where(
                CorpusReleaseEntry.release_id == release.id
            )
        ).all()
    }
    entries: list[CorpusReleaseEntry] = []
    for version in versions:
        ingestion_run_id = (
            run.id
            if version.id in materialized_version_ids
            else run_ids_by_version.get(version.id)
        )
        entry = existing.get(version.id)
        if not entry:
            entry = CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=version.source_document_id,
                ingestion_run_id=ingestion_run_id,
            )
        else:
            entry.source_document_id = version.source_document_id
            if ingestion_run_id:
                entry.ingestion_run_id = ingestion_run_id
        session.add(entry)
        entries.append(entry)
    session.flush()
    return entries


def _current_versions_for_instrument(
    session: Session, instrument_id: uuid.UUID
) -> list[ProvisionVersion]:
    return list(
        session.exec(
            select(ProvisionVersion)
            .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
            .where(
                Provision.instrument_id == instrument_id,
                ProvisionVersion.legal_status == LegalStatus.CURRENT,
                col(ProvisionVersion.valid_until).is_(None),
            )
            .order_by(col(Provision.sort_key), col(Provision.canonical_path))
        ).all()
    )


def _materialized_run_ids_by_version(
    session: Session, version_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    if not version_ids:
        return {}
    candidates = session.exec(
        select(ExtractionCandidate)
        .where(col(ExtractionCandidate.materialized_version_id).in_(version_ids))
        .order_by(col(ExtractionCandidate.updated_at))
    ).all()
    run_ids_by_version: dict[uuid.UUID, uuid.UUID] = {}
    for candidate in candidates:
        if candidate.materialized_version_id:
            run_ids_by_version[candidate.materialized_version_id] = candidate.run_id
    return run_ids_by_version


def _release_manifest(
    session: Session,
    *,
    release: CorpusRelease,
    run: IngestionRun,
    source: SourceDocument,
    entries: list[CorpusReleaseEntry],
) -> dict[str, Any]:
    manifest_entries = []
    source_document_ids: set[uuid.UUID] = {source.id}
    ingestion_run_ids: set[uuid.UUID] = {run.id}
    for entry in entries:
        version = session.get(ProvisionVersion, entry.provision_version_id)
        if not version:
            continue
        provision = session.get(Provision, version.provision_id)
        if not provision:
            continue
        if entry.source_document_id:
            source_document_ids.add(entry.source_document_id)
        if entry.ingestion_run_id:
            ingestion_run_ids.add(entry.ingestion_run_id)
        manifest_entries.append(
            {
                "canonical_path": provision.canonical_path,
                "provision_id": str(provision.id),
                "provision_version_id": str(version.id),
                "text_sha256": version.text_sha256,
                "source_document_id": str(version.source_document_id),
                "source_page_start": version.source_page_start,
                "source_page_end": version.source_page_end,
            }
        )
    source_documents = _manifest_source_documents(session, source_document_ids)
    return {
        "manifest_version": 1,
        "release_id": str(release.id),
        "release_version": release.version,
        "materialized_run_id": str(run.id),
        "ingestion_run_ids": sorted(str(run_id) for run_id in ingestion_run_ids),
        "source_document_ids": sorted(
            str(source_document_id) for source_document_id in source_document_ids
        ),
        "source_documents": source_documents,
        "entries": sorted(
            manifest_entries, key=lambda item: str(item["canonical_path"])
        ),
    }


def _manifest_source_documents(
    session: Session, source_document_ids: set[uuid.UUID]
) -> list[dict[str, object]]:
    if not source_document_ids:
        return []
    sources = session.exec(
        select(SourceDocument)
        .where(col(SourceDocument.id).in_(source_document_ids))
        .order_by(col(SourceDocument.created_at), col(SourceDocument.id))
    ).all()
    return [
        {
            "source_document_id": str(source.id),
            "title": source.title,
            "authority": source.authority,
            "source_url": source.source_url,
            "sha256": source.sha256,
            "storage_key": source.storage_key,
            "published_at": source.published_at.isoformat(),
            "retrieved_at": source.retrieved_at.isoformat(),
            "verification_status": str(source.verification_status),
            "is_legal_revision": source.is_legal_revision,
            "legal_revision_effective_at": source.legal_revision_effective_at.isoformat()
            if source.legal_revision_effective_at
            else None,
        }
        for source in sources
    ]


def _get_release_for_task(session: Session, task: IngestionTask) -> CorpusRelease:
    release_id = task.payload.get("release_id")
    if not release_id:
        raise IngestionWorkerError("Task does not identify a corpus release")
    release = session.get(CorpusRelease, uuid.UUID(str(release_id)))
    if not release:
        raise IngestionWorkerError("Corpus release was not found")
    return release


def _release_entries(
    session: Session, release_id: uuid.UUID
) -> list[CorpusReleaseEntry]:
    return list(
        session.exec(
            select(CorpusReleaseEntry)
            .where(CorpusReleaseEntry.release_id == release_id)
            .order_by(col(CorpusReleaseEntry.created_at))
        ).all()
    )


def _versions_by_release_entry(
    entries: list[CorpusReleaseEntry], session: Session
) -> dict[uuid.UUID, ProvisionVersion]:
    versions: dict[uuid.UUID, ProvisionVersion] = {}
    for entry in entries:
        version = session.get(ProvisionVersion, entry.provision_version_id)
        if version:
            versions[version.id] = version
    return versions


def _provisions_by_versions(
    versions_by_id: dict[uuid.UUID, ProvisionVersion], session: Session
) -> dict[uuid.UUID, Provision]:
    provisions: dict[uuid.UUID, Provision] = {}
    for version in versions_by_id.values():
        provision = session.get(Provision, version.provision_id)
        if not provision:
            continue
        provisions[provision.id] = provision
        parent_id = provision.parent_id
        while parent_id and parent_id not in provisions:
            parent = session.get(Provision, parent_id)
            if not parent:
                break
            provisions[parent.id] = parent
            parent_id = parent.parent_id
    return provisions


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _auto_start_embedding(run: IngestionRun) -> bool:
    return bool((run.pipeline_config or {}).get("auto_start_embedding"))


def _active_embedding_profiles(session: Session) -> list[EmbeddingProfile]:
    return list(
        session.exec(
            select(EmbeddingProfile)
            .where(EmbeddingProfile.is_active == True)  # noqa: E712
            .order_by(col(EmbeddingProfile.created_at))
        ).all()
    )


def _benchmark_dataset_for_embedding_profiles(
    session: Session, profiles: list[EmbeddingProfile]
) -> tuple[str, int]:
    profile_versions = [
        _profile_string(profile, "benchmark_dataset_version") for profile in profiles
    ]
    if any(version is None for version in profile_versions):
        raise IngestionWorkerError(
            "Every active embedding profile must identify a benchmark dataset version"
        )
    versions = {str(version) for version in profile_versions}
    if len(versions) != 1:
        raise IngestionWorkerError(
            "Active embedding profiles must use the same benchmark dataset version"
        )
    dataset_version = next(iter(versions))
    query_count = active_evaluation_item_count(
        session,
        dataset_version,
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
    )
    if query_count <= 0:
        raise IngestionWorkerError(
            f"Embedding benchmark dataset {dataset_version} is not active or has no retrieval queries"
        )
    return dataset_version, query_count


def _retrieval_documents_payload(
    session: Session, run: IngestionRun, release_id: uuid.UUID
) -> dict[str, Any]:
    artifact = _latest_artifact_with_metadata(
        session,
        run=run,
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS,
        key="release_id",
        value=str(release_id),
    )
    if not artifact:
        raise IngestionWorkerError("Run does not have retrieval document artifacts")
    return _json_object(get_blob_store().read_bytes(artifact.storage_key))


def _embedding_payload(
    session: Session, run: IngestionRun, embedding_run_id: uuid.UUID
) -> dict[str, Any]:
    artifact = _latest_artifact_with_metadata(
        session,
        run=run,
        artifact_type=IngestionArtifactType.EMBEDDINGS,
        key="embedding_run_id",
        value=str(embedding_run_id),
    )
    if not artifact:
        raise IngestionWorkerError("Run does not have embedding artifacts")
    return _json_object(get_blob_store().read_bytes(artifact.storage_key))


def _latest_artifact_with_metadata(
    session: Session,
    *,
    run: IngestionRun,
    artifact_type: IngestionArtifactType,
    key: str,
    value: str,
) -> IngestionArtifact | None:
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == artifact_type,
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).all()
    for artifact in artifacts:
        metadata = artifact.artifact_metadata or {}
        if str(metadata.get(key)) == value:
            return artifact
    return None


def _payload_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise IngestionWorkerError(f"Ingestion artifact did not contain {key}")
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise IngestionWorkerError(f"Ingestion artifact {key} item was invalid")
        items.append(cast(dict[str, Any], item))
    return items


def _embedding_run_for_profile(
    session: Session, release: CorpusRelease, profile: EmbeddingProfile
) -> EmbeddingRun:
    embedding_run = session.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.profile_id == profile.id,
        )
    ).first()
    if embedding_run:
        return embedding_run
    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        status=EmbeddingRunStatus.PENDING,
    )
    session.add(embedding_run)
    session.flush()
    return embedding_run


def _embedding_provider_for_profile(
    profile: EmbeddingProfile,
) -> DenseEmbeddingProvider:
    provider = _enum_value(profile.provider)
    if provider == EmbeddingProviderKind.OPENAI.value:
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model_name=profile.model_name,
            model_revision=profile.model_revision,
        )
    if provider == EmbeddingProviderKind.HUGGINGFACE_TEI.value:
        return HuggingFaceTeiEmbeddingProvider(
            endpoint_url=(
                _profile_string(profile, "endpoint_url")
                or settings.HUGGINGFACE_TEI_ENDPOINT_URL
            ),
            api_token=settings.HUGGINGFACE_API_TOKEN,
            model_name=profile.model_name,
            model_revision=profile.model_revision,
            timeout_seconds=_profile_float(profile, "timeout_seconds") or 120,
        )
    raise IngestionWorkerError(f"Unsupported embedding provider: {provider}")


def _profile_string(profile: EmbeddingProfile, key: str) -> str | None:
    value = (profile.configuration or {}).get(key)
    return value if isinstance(value, str) else None


def _profile_float(profile: EmbeddingProfile, key: str) -> float | None:
    value = (profile.configuration or {}).get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _profile_int(profile: EmbeddingProfile, key: str, *, default: int) -> int:
    value = (profile.configuration or {}).get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return default


def _sum_optional_costs(*costs: float | None) -> float | None:
    present = [cost for cost in costs if cost is not None]
    if not present:
        return None
    return round(sum(present), 6)


def _get_embedding_run_for_task(session: Session, task: IngestionTask) -> EmbeddingRun:
    embedding_run_id = task.payload.get("embedding_run_id")
    if not embedding_run_id:
        raise IngestionWorkerError("Task does not identify an embedding run")
    embedding_run = session.get(EmbeddingRun, uuid.UUID(str(embedding_run_id)))
    if not embedding_run:
        raise IngestionWorkerError("Embedding run was not found")
    return embedding_run


def _qdrant_points_from_embedding_payload(payload: dict[str, Any]) -> list[QdrantPoint]:

    documents = _payload_list(payload, "documents")
    dense_vectors = payload.get("dense_vectors")
    sparse_vectors = payload.get("sparse_vectors")
    if not isinstance(dense_vectors, list):
        raise IngestionWorkerError("Embedding artifact did not contain dense vectors")
    if not isinstance(sparse_vectors, list):
        raise IngestionWorkerError("Embedding artifact did not contain sparse vectors")
    if len(documents) != len(dense_vectors) or len(documents) != len(sparse_vectors):
        raise IngestionWorkerError("Document and embedding vector counts do not match")
    points: list[QdrantPoint] = []
    for document, vector, sparse in zip(
        documents, dense_vectors, sparse_vectors, strict=True
    ):
        document_payload = document.get("payload")
        if not isinstance(document_payload, dict):
            raise IngestionWorkerError("Retrieval document payload was invalid")
        point_id = str(document.get("id") or document.get("segment_id"))
        sparse_vector = _coerce_sparse_vector(sparse)
        points.append(
            QdrantPoint(
                point_id=point_id,
                vector=_float_vector(vector),
                payload={
                    **cast(dict[str, Any], document_payload),
                    "segment_id": document.get("segment_id"),
                    "citation": document.get("citation"),
                },
                sparse=sparse_vector,
            )
        )
    return points


def _coerce_sparse_vector(value: object) -> QdrantSparseVector:
    if not isinstance(value, dict):
        raise IngestionWorkerError("Sparse vector payload was invalid")
    indices = value.get("indices")
    values = value.get("values")
    if not isinstance(indices, list) or not isinstance(values, list):
        raise IngestionWorkerError("Sparse vector payload was invalid")
    clean_indices: list[int] = []
    for index in indices:
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise IngestionWorkerError("Sparse vector index was invalid")
        clean_indices.append(index)
    clean_values: list[float] = []
    for item in values:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise IngestionWorkerError("Sparse vector value was invalid")
        clean_values.append(float(item))
    if len(clean_indices) != len(clean_values):
        raise IngestionWorkerError("Sparse vector indices/values length mismatch")
    return QdrantSparseVector(indices=clean_indices, values=clean_values)


def _index_kind_for_points(points: list[QdrantPoint]) -> str:
    kinds = {str(point.payload.get("legal_status", "")).lower() for point in points}
    if kinds and kinds <= {"proposed"}:
        return "proposals"
    return "enacted"


def _index_kind_for_documents(documents: list[RetrievalDocument]) -> str:
    kinds = {
        str(document.payload.get("legal_status", "")).lower() for document in documents
    }
    if kinds and kinds <= {"proposed"}:
        return "proposals"
    return "enacted"


def _float_vector(value: object) -> list[float]:
    if not isinstance(value, list):
        raise IngestionWorkerError("Dense vector was not a list")
    vector: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise IngestionWorkerError("Dense vector contained a non-number")
        vector.append(float(item))
    return vector


def _vector_index_for_collection(
    session: Session,
    *,
    release: CorpusRelease,
    embedding_run: EmbeddingRun,
    profile: EmbeddingProfile,
    collection_name: str,
    index_kind: str = "enacted",
    profile_hash: str | None = None,
) -> VectorIndex:
    vector_index = session.exec(
        select(VectorIndex).where(VectorIndex.collection_name == collection_name)
    ).first()
    if vector_index:
        if (
            vector_index.release_id != release.id
            or vector_index.embedding_run_id != embedding_run.id
            or vector_index.profile_id != profile.id
        ):
            raise IngestionWorkerError(
                f"Collection {collection_name} already exists for a different release/profile; "
                "collections are immutable"
            )
        if vector_index.status in {
            VectorIndexStatus.READY,
            VectorIndexStatus.PROMOTED,
            VectorIndexStatus.VALIDATING,
        }:
            raise IngestionWorkerError(
                f"Collection {collection_name} is already "
                f"{_enum_value(vector_index.status)}; "
                "refusing to rebuild an immutable collection"
            )
        vector_index.status = VectorIndexStatus.BUILDING
        if profile_hash is not None:
            vector_index.profile_hash = profile_hash
        vector_index.index_kind = index_kind
        return vector_index
    vector_index = VectorIndex(
        release_id=release.id,
        embedding_run_id=embedding_run.id,
        profile_id=profile.id,
        collection_name=collection_name,
        alias_name=alias_for_index_kind(index_kind),
        index_kind=index_kind,
        profile_hash=profile_hash,
        status=VectorIndexStatus.BUILDING,
        vector_dimensions=profile.vector_dimensions,
    )
    session.add(vector_index)
    session.flush()
    return vector_index


def _run_qdrant_smoke_queries(
    adapter: QdrantHttpIndexAdapter,
    *,
    collection_name: str,
    points: list[QdrantPoint],
) -> list[dict[str, Any]]:
    if not points:
        return []
    probe_points = points[: min(3, len(points))]
    smoke_results: list[dict[str, Any]] = []
    for point in probe_points:
        hits = adapter.search_points(
            collection_name=collection_name,
            vector=point.vector,
            limit=min(5, len(points)),
        )
        hit_ids = [hit.point_id for hit in hits]
        matched_payload = False
        for hit in hits:
            if hit.point_id != point.point_id:
                continue
            matched_payload = hit.payload.get(
                "provision_version_id"
            ) == point.payload.get("provision_version_id")
            break
        smoke_results.append(
            {
                "expected_point_id": point.point_id,
                "hit_ids": hit_ids,
                "matched_payload": matched_payload,
                "passed": point.point_id in hit_ids and matched_payload,
            }
        )
    return smoke_results


def _qdrant_adapter() -> QdrantHttpIndexAdapter:
    if not settings.QDRANT_URL:
        raise IngestionWorkerError("Qdrant URL is not configured")
    return QdrantHttpIndexAdapter(
        base_url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _raw_extraction_payloads(
    session: Session, run: IngestionRun
) -> list[dict[str, Any]]:
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.RAW_EXTRACTION,
        )
        .order_by(col(IngestionArtifact.storage_key))
    ).all()
    payloads = [
        _json_object(get_blob_store().read_bytes(artifact.storage_key))
        for artifact in artifacts
    ]
    return sorted(payloads, key=lambda payload: int(payload["page_number"]))


def _ocr_output_payloads(session: Session, run: IngestionRun) -> list[dict[str, Any]]:
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.OCR_OUTPUT,
        )
        .order_by(col(IngestionArtifact.storage_key))
    ).all()
    payloads = [
        _json_object(get_blob_store().read_bytes(artifact.storage_key))
        for artifact in artifacts
    ]
    return sorted(payloads, key=lambda payload: int(payload["page_number"]))


def _ocr_page_numbers(
    session: Session, run: IngestionRun, task: IngestionTask
) -> list[int]:
    included_pages = {
        int(page_number)
        for page_number in task.payload.get("included_pages", [])
        if isinstance(page_number, int | str)
    }
    page_numbers: list[int] = []
    for payload in _raw_extraction_payloads(session, run):
        page_number = int(payload["page_number"])
        if included_pages and page_number not in included_pages:
            continue
        flags = payload.get("quality_flags")
        quality_flags = flags if isinstance(flags, dict) else {}
        if quality_flags.get("needs_ocr") or not str(payload.get("text") or "").strip():
            page_numbers.append(page_number)
    return sorted(set(page_numbers))


def _managed_ocr_page_numbers(
    session: Session, run: IngestionRun, task: IngestionTask
) -> list[int]:
    explicit_page_numbers = {
        int(page_number)
        for page_number in task.payload.get("page_numbers", [])
        if isinstance(page_number, int | str)
    }
    if explicit_page_numbers:
        return sorted(explicit_page_numbers)
    page_numbers: list[int] = []
    for payload in _ocr_output_payloads(session, run):
        flags = payload.get("quality_flags")
        quality_flags = flags if isinstance(flags, dict) else {}
        if quality_flags.get("requires_managed_ocr"):
            page_numbers.append(int(payload["page_number"]))
    return sorted(set(page_numbers))


def _ocr_result_payload(result: OcrPageResult) -> dict[str, Any]:
    words = list(result.words)
    return {
        "page_number": result.page_number,
        "method": result.method,
        "provider": result.provider,
        "provider_version": result.provider_version,
        "confidence": result.confidence,
        "cost_usd": result.cost_usd,
        "text": result.text,
        "spans": [
            {
                "text": word.text,
                "bbox": word.bbox,
                "confidence": word.confidence,
                "reading_order": word.reading_order,
            }
            for word in words
        ],
        "quality_flags": result.quality_flags,
    }


def _best_extraction_payloads(
    session: Session, run: IngestionRun
) -> list[dict[str, Any]]:
    ocr_by_page = {
        int(payload["page_number"]): payload
        for payload in _ocr_output_payloads(session, run)
    }
    selected_payloads: list[dict[str, Any]] = []
    for raw_payload in _raw_extraction_payloads(session, run):
        page_number = int(raw_payload["page_number"])
        flags = raw_payload.get("quality_flags")
        quality_flags = flags if isinstance(flags, dict) else {}
        should_use_ocr = (
            quality_flags.get("needs_ocr")
            or not str(raw_payload.get("text") or "").strip()
        )
        selected_payloads.append(
            ocr_by_page[page_number]
            if should_use_ocr and page_number in ocr_by_page
            else raw_payload
        )
    return sorted(selected_payloads, key=lambda payload: int(payload["page_number"]))


def _normalized_pages_payload(session: Session, run: IngestionRun) -> dict[str, Any]:
    artifact = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.NORMALIZED_PAGES,
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).first()
    if not artifact:
        raise IngestionWorkerError("Run does not have normalized page artifacts")
    return _json_object(get_blob_store().read_bytes(artifact.storage_key))


def _json_object(content: bytes) -> dict[str, Any]:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise IngestionWorkerError("Ingestion artifact did not contain a JSON object")
    return cast(dict[str, Any], payload)


def _normalize_page_text(text: str) -> str:
    return normalize_page_text(text).text


def _upsert_candidate(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    node: Any,
    parent_candidate: ExtractionCandidate | None,
    ancestor_headings: list[str],
    source_spans: list[dict[str, Any]],
) -> ExtractionCandidate:
    existing = session.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == run.id,
            ExtractionCandidate.canonical_path == node.canonical_path,
            ExtractionCandidate.revision_number == 1,
        )
    ).first()
    candidate = existing or ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=node.kind,
        canonical_path=node.canonical_path,
        sort_key=node.sort_key,
    )
    candidate.parent_candidate_id = parent_candidate.id if parent_candidate else None
    candidate.kind = node.kind
    candidate.number = node.number
    candidate.heading = node.heading
    candidate.sort_key = node.sort_key
    candidate.raw_text = node.text
    candidate.normalized_text = normalize_legal_text(node.text) if node.text else None
    candidate.text_sha256 = legal_text_sha256(node.text) if node.text else None
    candidate.source_page_start = node.page_start
    candidate.source_page_end = node.page_end
    candidate.source_spans = source_spans
    candidate.ancestor_headings = ancestor_headings
    candidate.parser_version = PARSER_VERSION
    candidate.extractor_version = _extractor_version(source_spans)
    candidate.parser_confidence = node.parser_confidence
    candidate.extractor_confidence = _extractor_confidence(source_spans)
    candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
    candidate.lock_version += 1
    candidate.updated_at = get_datetime_utc()
    session.add(candidate)
    session.flush()
    return candidate


def _ancestor_headings(
    parent_path: str | None, nodes_by_path: dict[str, Any]
) -> list[str]:
    headings: list[str] = []
    current_path = parent_path
    while current_path:
        node = nodes_by_path.get(current_path)
        if not node:
            break
        if node.heading:
            headings.append(str(node.heading))
        current_path = node.parent_path
    headings.reverse()
    return headings


def _source_spans_for_node(
    node: Any,
    page_payloads: list[dict[str, Any]],
    *,
    nodes_by_path: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if node.page_start is None or node.page_end is None:
        return []
    page_range = range(int(node.page_start), int(node.page_end) + 1)
    spans: list[dict[str, Any]] = []
    matched_spans: list[dict[str, Any]] = []
    node_text = str(getattr(node, "text", "") or "")
    for page in page_payloads:
        page_number = int(page["page_number"])
        if page_number not in page_range:
            continue
        for span in page.get("spans") or []:
            span_text = str(span.get("text") or "")
            if not span_text:
                continue
            spans.append(
                {
                    "page_number": page_number,
                    "text": span_text,
                    "bbox": span.get("bbox") or {},
                    "reading_order": span.get("reading_order"),
                    "method": page.get("method"),
                    "provider_version": page.get("provider_version"),
                    "confidence": page.get("confidence"),
                }
            )
            if _span_text_matches_node(span_text, node_text):
                matched_spans.append(spans[-1])
    aligned = aligned_source_spans(node_text, spans)
    parent_path = getattr(node, "parent_path", None)
    while aligned is None and parent_path and nodes_by_path:
        parent = nodes_by_path.get(parent_path)
        if parent is None:
            break
        if parent.text:
            aligned = aligned_source_spans(node_text, spans, context=parent.text)
        parent_path = parent.parent_path
    return aligned or matched_spans or spans


def _validate_candidate_for_review(
    session: Session, candidate: ExtractionCandidate
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if candidate.raw_text and not candidate.source_spans:
        issues.append(
            _ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="missing_source_spans",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate text does not have source-coordinate spans.",
                evidence={"canonical_path": candidate.canonical_path},
            )
        )
    elif candidate.raw_text and candidate.source_spans:
        coverage, precision = _source_span_text_metrics(
            candidate.raw_text, candidate.source_spans
        )
        if coverage < 0.8 or precision < 0.5:
            issues.append(
                _ensure_review_issue(
                    session,
                    candidate=candidate,
                    issue_type="source_span_coverage",
                    severity=ReviewIssueSeverity.BLOCKING,
                    blocking=True,
                    message="Candidate text is not sufficiently covered by source-coordinate spans.",
                    evidence={
                        "canonical_path": candidate.canonical_path,
                        "coverage": coverage,
                        "precision": precision,
                    },
                )
            )
    if (
        candidate.raw_text
        and candidate.parser_confidence is not None
        and candidate.parser_confidence < 0.8
    ):
        issues.append(
            _ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="low_parser_confidence",
                severity=ReviewIssueSeverity.HIGH,
                blocking=False,
                message="Parser confidence fell below the auto-approval threshold.",
                evidence={"parser_confidence": candidate.parser_confidence},
            )
        )
    if candidate.raw_text and has_unbalanced_punctuation(candidate.raw_text):
        issues.append(
            _ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="unbalanced_punctuation",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate text has unbalanced punctuation.",
                evidence={"canonical_path": candidate.canonical_path},
            )
        )
    candidate.blocking_issue_count = sum(1 for issue in issues if issue.blocking)
    session.add(candidate)
    return issues


def _maybe_compute_gold_quality_report(
    session: Session,
    run: IngestionRun,
    candidates: list[ExtractionCandidate],
) -> LegalGradeQualityReport | None:
    policy = (run.pipeline_config or {}).get("auto_approval_policy")
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return None
    dataset_version = policy.get("gold_dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        return None
    gold_provisions = load_gold_provisions_for_dataset(session, dataset_version)
    if not gold_provisions:
        return None

    report = evaluate_legal_grade_quality(
        gold_dataset_version=dataset_version,
        gold_provisions=gold_provisions,
        extracted_provisions=[
            ExtractedProvision(
                canonical_path=candidate.canonical_path,
                text=candidate.raw_text,
                kind=candidate.kind,
                number=candidate.number,
                source_page_start=candidate.source_page_start,
                source_page_end=candidate.source_page_end,
                source_spans=candidate.source_spans,
            )
            for candidate in candidates
        ],
    )
    run.pipeline_config = {
        **(run.pipeline_config or {}),
        "auto_approval_policy": {
            **policy,
            **report.to_policy_metrics(),
        },
    }
    session.add(run)
    return report


def _validated_candidate_status(
    run: IngestionRun,
    candidate: ExtractionCandidate,
    issues: list[ReviewIssue],
) -> ExtractionCandidateStatus:
    if issues or not _auto_approval_policy_passes(run):
        return ExtractionCandidateStatus.NEEDS_REVIEW
    if candidate.raw_text and not _candidate_confidence_passes(candidate):
        return ExtractionCandidateStatus.NEEDS_REVIEW
    return ExtractionCandidateStatus.AUTO_APPROVED


def _auto_approval_policy_passes(run: IngestionRun) -> bool:
    policy = (run.pipeline_config or {}).get("auto_approval_policy")
    if not isinstance(policy, dict):
        return False
    if policy.get("enabled") is not True:
        return False
    if policy.get("metrics_source") != "computed_gold_evaluation":
        return False
    if policy.get("passed_legal_grade_gate") is not True:
        return False
    if not policy.get("gold_dataset_version"):
        return False
    if policy.get("complete_section_number_coverage") is not True:
        return False
    if int(policy.get("meaning_changing_token_errors") or 0) != 0:
        return False
    accuracy = policy.get("character_accuracy")
    if not isinstance(accuracy, int | float):
        return False
    return float(accuracy) >= LEGAL_GRADE_MIN_CHARACTER_ACCURACY


def _candidate_confidence_passes(candidate: ExtractionCandidate) -> bool:
    confidence_values = [
        value
        for value in (candidate.parser_confidence, candidate.extractor_confidence)
        if value is not None
    ]
    if not confidence_values:
        return False
    return all(value >= AUTO_APPROVAL_MIN_CONFIDENCE for value in confidence_values)


def _ensure_review_issue(
    session: Session,
    *,
    candidate: ExtractionCandidate,
    issue_type: str,
    severity: ReviewIssueSeverity,
    blocking: bool,
    message: str,
    evidence: dict[str, Any],
) -> ReviewIssue:
    existing = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == issue_type,
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    if existing:
        return existing
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type=issue_type,
        severity=severity,
        status=ReviewIssueStatus.OPEN,
        blocking=blocking,
        message=message,
        evidence=evidence,
    )
    session.add(issue)
    return issue


def _extractor_version(source_spans: list[dict[str, Any]]) -> str | None:
    for span in source_spans:
        provider_version = span.get("provider_version")
        if provider_version:
            return str(provider_version)
    return None


def _extractor_confidence(source_spans: list[dict[str, Any]]) -> float | None:
    confidences = [
        float(span["confidence"])
        for span in source_spans
        if span.get("confidence") is not None
    ]
    if not confidences:
        return None
    return round(min(confidences), 4)


def _span_text_matches_node(span_text: str, node_text: str) -> bool:
    span_tokens = _coverage_tokens(span_text)
    node_tokens = _coverage_tokens(node_text)
    if not span_tokens or not node_tokens:
        return False
    span_phrase = " ".join(span_tokens)
    node_phrase = " ".join(node_tokens)
    if span_phrase in node_phrase or node_phrase in span_phrase:
        return True
    span_set = set(span_tokens)
    node_set = set(node_tokens)
    return len(span_set & node_set) / max(len(span_set), 1) >= 0.6


def _source_span_text_metrics(
    raw_text: str, source_spans: list[dict[str, Any]]
) -> tuple[float, float]:
    # Fragment boundaries can split words. Exact character agreement is a
    # stronger coverage check than token counts in that case.
    span_text = "\n".join(str(span.get("text") or "") for span in source_spans)
    compact_raw, _ = compact_text(raw_text)
    if compact_raw and compact_raw == compact_text(span_text)[0]:
        return 1.0, 1.0
    raw_tokens = _coverage_tokens(raw_text)
    span_tokens = _coverage_tokens(
        " ".join(str(span.get("text") or "") for span in source_spans)
    )
    if not raw_tokens or not span_tokens:
        return 0.0, 0.0
    raw_counts = _token_counts(raw_tokens)
    span_counts = _token_counts(span_tokens)
    covered = sum(
        min(count, span_counts.get(token, 0)) for token, count in raw_counts.items()
    )
    extra = sum(
        max(count - raw_counts.get(token, 0), 0) for token, count in span_counts.items()
    )
    coverage = covered / sum(raw_counts.values())
    precision = covered / (covered + extra) if covered + extra else 0.0
    return round(coverage, 4), round(precision, 4)


def _coverage_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _token_counts(tokens: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _stage_for_task(task: IngestionTask) -> IngestionStage:
    try:
        return IngestionStage(task.task_type)
    except ValueError:
        raise IngestionWorkerError(f"Unknown ingestion task type: {task.task_type}")


def _priority_for_stage(stage: IngestionStage) -> int:
    return {
        IngestionStage.VERIFYING_UPLOAD: 10,
        IngestionStage.MALWARE_SCAN: 15,
        IngestionStage.PROFILING: 20,
        IngestionStage.RENDERING: 30,
        IngestionStage.NATIVE_EXTRACTION: 40,
        IngestionStage.LOCAL_OCR: 45,
        IngestionStage.MANAGED_OCR: 50,
        IngestionStage.NORMALIZING: 60,
        IngestionStage.PARSING_STRUCTURE: 70,
        IngestionStage.VALIDATING_DOCUMENT: 80,
    }.get(stage, 100)


__all__ = [
    "IngestionWorkerError",
    "StageOutcome",
    "WorkerResult",
    "handle_malware_scan",
    "handle_native_extraction",
    "handle_normalizing",
    "handle_parsing_structure",
    "handle_profiling",
    "handle_rendering",
    "handle_validating_document",
    "handle_verifying_upload",
    "run_leased_task",
    "run_once",
    "run_until_idle",
]
