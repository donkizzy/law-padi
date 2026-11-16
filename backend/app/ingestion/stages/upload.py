import hashlib
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import BinaryIO

from sqlmodel import Session

from app.core.config import settings
from app.ingestion.common import get_datetime_utc
from app.ingestion.contracts import BlobStore
from app.ingestion.malware import malware_scanner_from_settings
from app.ingestion.pdf import (
    PdfInspectionError,
    inspect_pdf_bytes,
    inspect_pdf_file,
)
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.types import StageOutcome
from app.ingestion.service import (
    MAX_SOURCE_PAGES,
    MAX_UPLOAD_BYTES,
    finalize_verified_upload,
)
from app.ingestion.stages.artifacts import ensure_artifact
from app.ingestion.stages.sources import (
    get_source_for_run,
    get_upload_for_run,
    read_source_bytes,
    require_storage_key,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionArtifactType,
    IngestionStage,
    VerificationStatus,
)
from app.legal.models import (
    IngestionRun,
    IngestionTask,
    SourceUpload,
)


def handle_verifying_upload(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    if run.source_document_id or task.payload.get("source_document_id"):
        source = get_source_for_run(session, run, task)
        inspection = inspect_pdf_bytes(
            read_source_bytes(source),
            expected_sha256=source.sha256,
            expected_size=source.file_size,
            max_pages=MAX_SOURCE_PAGES,
        )
        source.page_count = inspection.page_count
        source.verification_status = VerificationStatus.NEEDS_REVIEW
        session.add(source)
        ensure_artifact(
            session,
            run_id=run.id,
            artifact_type=IngestionArtifactType.ORIGINAL_SOURCE,
            storage_key=require_storage_key(source),
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

    upload = get_upload_for_run(session, run, task)
    store = get_blob_store()
    try:
        with quarantine_snapshot(store, upload) as (temporary, _):
            inspection = inspect_pdf_file(
                temporary,
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
    ensure_artifact(
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
        source = get_source_for_run(session, run, task)
        store = get_blob_store()
        try:
            with store.open_read(require_storage_key(source)) as stream:
                scan_report = malware_scanner_from_settings(settings).scan_stream(
                    stream
                )
        except FileNotFoundError as exc:
            raise IngestionWorkerError(
                "Stored source document file was not found"
            ) from exc
        if task.payload.get("source_upload_id"):
            upload = get_upload_for_run(session, run, task)
            store.delete_quarantine(upload.quarantine_key)
        return StageOutcome(
            metrics=scan_report.to_metrics(),
            next_stage=IngestionStage.PROFILING,
            next_task_payload={"source_document_id": str(source.id)},
        )

    upload = get_upload_for_run(session, run, task)
    page_count = run.expected_page_count
    sha256 = str(run.pipeline_config.get("source_sha256") or upload.actual_sha256 or "")
    if page_count is None or not sha256:
        raise IngestionWorkerError(
            "Upload verification did not record a digest and page count"
        )
    store = get_blob_store()
    try:
        with quarantine_snapshot(store, upload) as (stream, snapshot_sha256):
            if snapshot_sha256 != sha256:
                raise IngestionWorkerError(
                    "Quarantined upload changed after verification"
                )
            scan_report = malware_scanner_from_settings(settings).scan_stream(stream)
            stream.seek(0)
            source = finalize_verified_upload(
                session,
                run=run,
                upload=upload,
                store=store,
                verified_stream=stream,
                sha256=sha256,
                page_count=page_count,
            )
    except FileNotFoundError as exc:
        raise IngestionWorkerError("Quarantined upload file was not found") from exc
    return StageOutcome(
        metrics=scan_report.to_metrics(),
        next_stage=IngestionStage.PROFILING,
        next_task_payload={"source_document_id": str(source.id)},
    )


@contextmanager
def quarantine_snapshot(
    store: BlobStore, upload: SourceUpload
) -> Iterator[tuple[BinaryIO, str]]:
    if not 0 < upload.expected_size <= MAX_UPLOAD_BYTES:
        raise IngestionWorkerError("Invalid quarantined upload size")
    digest = hashlib.sha256()
    size = 0
    with tempfile.TemporaryFile(mode="w+b") as stream:
        with closing(store.iter_read(upload.quarantine_key)) as chunks:
            for chunk in chunks:
                size += len(chunk)
                if size > upload.expected_size:
                    raise IngestionWorkerError(
                        "Quarantined upload exceeds its expected size"
                    )
                digest.update(chunk)
                stream.write(chunk)
        if size != upload.expected_size:
            raise IngestionWorkerError("Quarantined upload size does not match")
        stream.seek(0)
        yield stream, digest.hexdigest()
