import json
from typing import Any

from sqlmodel import Session

from app.ingestion.admin.uploads import MAX_SOURCE_PAGES
from app.ingestion.extraction import NativePdfExtractor
from app.ingestion.normalization import NORMALIZER_VERSION, normalize_page_text
from app.ingestion.ocr import (
    OcrPageInput,
    OcrPageResult,
    TesseractOcrProvider,
    managed_ocr_provider_from_settings,
)
from app.ingestion.pdf import (
    profile_pdf_pages,
)
from app.ingestion.rendering import render_page_thumbnail
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.types import StageOutcome
from app.ingestion.stages.artifacts import ensure_artifact
from app.ingestion.stages.page_payloads import (
    best_extraction_payloads,
    ocr_output_payloads,
    raw_extraction_payloads,
)
from app.ingestion.stages.sources import (
    get_source_for_run,
    pages_for_run,
    read_source_bytes,
    upsert_source_page,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    InstrumentType,
    PageInclusionStatus,
)
from app.legal.models import (
    IngestionRun,
    IngestionTask,
    LegalInstrument,
)


def handle_profiling(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = get_source_for_run(session, run, task)
    profiles = profile_pdf_pages(read_source_bytes(source), max_pages=MAX_SOURCE_PAGES)
    included_pages = 0
    requires_ocr = 0
    for profile in profiles:
        if profile.inclusion_status == PageInclusionStatus.SUGGESTED_INCLUDE:
            included_pages += 1
        if profile.quality_signals.get("requires_ocr"):
            requires_ocr += 1
        upsert_source_page(session, run=run, source=source, profile=profile)
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
    source = get_source_for_run(session, run, task)
    content = read_source_bytes(source)
    pages = pages_for_run(session, run)
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
        ensure_artifact(
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
    source = get_source_for_run(session, run, task)
    included_pages = {
        page.page_number
        for page in pages_for_run(session, run)
        if page.inclusion_status == PageInclusionStatus.INCLUDED
    }
    if not included_pages:
        raise IngestionWorkerError("Run does not have confirmed included pages")

    extractor = NativePdfExtractor()
    extractions = extractor.extract(
        read_source_bytes(source), included_pages=included_pages
    )
    pages_by_number = {page.page_number: page for page in pages_for_run(session, run)}
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
        ensure_artifact(
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
    source = get_source_for_run(session, run, task)
    page_numbers = ocr_page_numbers(session, run, task)
    if not page_numbers:
        return StageOutcome(
            metrics={"ocr_page_count": 0, "managed_ocr_required_pages": 0},
            next_stage=IngestionStage.NORMALIZING,
            next_task_payload={"source_document_id": str(source.id)},
            skipped_stages=(IngestionStage.MANAGED_OCR,),
        )

    source_content = read_source_bytes(source)
    pages_by_number = {page.page_number: page for page in pages_for_run(session, run)}
    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    provider = (
        TesseractOcrProvider(preserve_lines=True)
        if instrument and instrument.instrument_type == InstrumentType.ACT
        else TesseractOcrProvider()
    )
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
        ensure_artifact(
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
    source = get_source_for_run(session, run, task)
    page_numbers = managed_ocr_page_numbers(session, run, task)
    if not page_numbers:
        return StageOutcome(
            metrics={"managed_ocr_page_count": 0},
            next_stage=IngestionStage.NORMALIZING,
            next_task_payload={"source_document_id": str(source.id)},
        )

    source_content = read_source_bytes(source)
    pages_by_number = {page.page_number: page for page in pages_for_run(session, run)}
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
        payload = ocr_result_payload(result)
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
        ensure_artifact(
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
    source = get_source_for_run(session, run, task)
    raw_payloads = best_extraction_payloads(session, run)
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
    ensure_artifact(
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


def ocr_page_numbers(
    session: Session, run: IngestionRun, task: IngestionTask
) -> list[int]:
    included_pages = {
        int(page_number)
        for page_number in task.payload.get("included_pages", [])
        if isinstance(page_number, int | str)
    }
    page_numbers: list[int] = []
    for payload in raw_extraction_payloads(session, run):
        page_number = int(payload["page_number"])
        if included_pages and page_number not in included_pages:
            continue
        flags = payload.get("quality_flags")
        quality_flags = flags if isinstance(flags, dict) else {}
        if quality_flags.get("needs_ocr") or not str(payload.get("text") or "").strip():
            page_numbers.append(page_number)
    return sorted(set(page_numbers))


def managed_ocr_page_numbers(
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
    for payload in ocr_output_payloads(session, run):
        flags = payload.get("quality_flags")
        quality_flags = flags if isinstance(flags, dict) else {}
        if quality_flags.get("requires_managed_ocr"):
            page_numbers.append(int(payload["page_number"]))
    return sorted(set(page_numbers))


def ocr_result_payload(result: OcrPageResult) -> dict[str, Any]:
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
