import uuid
from typing import Any

from sqlmodel import Session, col, select

from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    PageInclusionStatus,
)
from app.legal.models import (
    IngestionRun,
    IngestionTask,
    SourceDocument,
    SourcePage,
    SourceUpload,
)


def get_source_for_run(
    session: Session, run: IngestionRun, task: IngestionTask
) -> SourceDocument:
    source_id = task.payload.get("source_document_id") or run.source_document_id
    if not source_id:
        raise IngestionWorkerError("Task does not identify a source document")
    source = session.get(SourceDocument, uuid.UUID(str(source_id)))
    if not source:
        raise IngestionWorkerError("Source document was not found")
    return source


def get_upload_for_run(
    session: Session, run: IngestionRun, task: IngestionTask
) -> SourceUpload:
    upload_id = task.payload.get("source_upload_id") or run.source_upload_id
    if not upload_id:
        raise IngestionWorkerError("Task does not identify a source upload")
    upload = session.get(SourceUpload, uuid.UUID(str(upload_id)))
    if not upload:
        raise IngestionWorkerError("Source upload was not found")
    return upload


def read_upload_bytes(upload: SourceUpload) -> bytes:
    try:
        return get_blob_store().read_bytes(upload.quarantine_key)
    except FileNotFoundError:
        raise IngestionWorkerError("Quarantined upload file was not found")


def read_source_bytes(source: SourceDocument) -> bytes:
    try:
        return get_blob_store().read_bytes(require_storage_key(source))
    except FileNotFoundError:
        raise IngestionWorkerError("Stored source document file was not found")


def require_storage_key(source: SourceDocument) -> str:
    if not source.storage_key:
        raise IngestionWorkerError("Source document does not have a stored file")
    return source.storage_key


def upsert_source_page(
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


def pages_for_run(session: Session, run: IngestionRun) -> list[SourcePage]:
    return list(
        session.exec(
            select(SourcePage)
            .where(SourcePage.run_id == run.id)
            .order_by(col(SourcePage.page_number))
        ).all()
    )
