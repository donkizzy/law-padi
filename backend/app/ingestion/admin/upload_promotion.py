from datetime import UTC, datetime, time
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.admin.uploads import (
    ensure_allowed_instrument_type,
    get_or_create_instrument,
)
from app.ingestion.blob_store import (
    BlobStoreError,
    verify_blob_contents,
)
from app.ingestion.common import get_datetime_utc
from app.ingestion.contracts import (
    BlobStore,
)
from app.legal.enums import (
    IngestionArtifactType,
    InstrumentType,
    SourceUploadStatus,
    VerificationStatus,
)
from app.legal.models import (
    IngestionArtifact,
    IngestionRun,
    LegalInstrument,
    SourceDocument,
    SourceUpload,
)


def finalize_verified_upload(
    session: Session,
    *,
    run: IngestionRun,
    upload: SourceUpload,
    store: BlobStore,
    verified_stream: BinaryIO,
    sha256: str,
    page_count: int,
) -> SourceDocument:
    """Promote a quarantined upload only after worker verification and malware scan."""
    existing_source = session.exec(
        select(SourceDocument).where(SourceDocument.sha256 == sha256)
    ).first()
    if existing_source is not None:
        instrument = session.get(LegalInstrument, existing_source.legal_instrument_id)
        if (
            not instrument
            or (
                upload.instrument_type == InstrumentType.ACT
                and instrument.slug != upload.instrument_slug
            )
            or instrument.instrument_type != upload.instrument_type
        ):
            raise HTTPException(
                status_code=409,
                detail="Source hash already belongs to a different legal instrument",
            )
        ensure_allowed_instrument_type(upload.instrument_type)
        if not existing_source.storage_key:
            raise BlobStoreError("Existing source has no stored original")
        verify_blob_contents(
            store,
            existing_source.storage_key,
            expected_sha256=sha256,
            size_bytes=upload.expected_size,
        )
        source = existing_source
        upload.status = SourceUploadStatus.DUPLICATE
        upload.canonical_key = source.storage_key
    else:
        original = store.put_verified_original(
            stream=verified_stream,
            expected_sha256=sha256,
            size_bytes=upload.expected_size,
            content_type=upload.mime_type,
            extension=Path(upload.original_filename).suffix or ".pdf",
            metadata={
                "source_upload_id": str(upload.id),
                "source_url": upload.source_url,
            },
        )
        instrument = get_or_create_instrument(session, upload)
        source = SourceDocument(
            legal_instrument_id=instrument.id,
            authority=upload.authority,
            title=upload.source_title,
            source_url=upload.source_url,
            mime_type=upload.mime_type,
            sha256=original.sha256,
            storage_backend=upload.upload_backend,
            storage_bucket=settings.R2_BUCKET_NAME
            if upload.upload_backend == "r2"
            else None,
            storage_key=original.key,
            original_filename=upload.original_filename,
            file_size=original.size_bytes,
            page_count=page_count,
            published_at=upload.published_at,
            retrieved_at=datetime.combine(upload.retrieved_at, time.min, tzinfo=UTC),
            is_legal_revision=upload.is_legal_revision,
            legal_revision_effective_at=upload.legal_revision_effective_at,
            source_tier=upload.source_tier,
            verification_status=VerificationStatus.NEEDS_REVIEW,
            created_by=run.created_by,
        )
        session.add(source)
        session.flush()
        upload.legal_instrument_id = instrument.id
        upload.status = SourceUploadStatus.COMPLETED
        upload.canonical_key = original.key

    upload.source_document_id = source.id
    upload.actual_sha256 = sha256
    upload.completed_at = upload.completed_at or get_datetime_utc()
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    run.source_document_id = source.id
    run.expected_page_count = page_count
    run.pipeline_config = {
        **run.pipeline_config,
        "source_sha256": sha256,
        "page_count": page_count,
    }
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    verification_artifact = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.ORIGINAL_SOURCE,
            IngestionArtifact.sha256 == sha256,
        )
    ).first()
    if verification_artifact:
        verification_artifact.storage_key = source.storage_key
        verification_artifact.artifact_metadata = {
            **(verification_artifact.artifact_metadata or {}),
            "quarantine": False,
            "canonical_source_document_id": str(source.id),
        }
        session.add(verification_artifact)
    session.add_all([upload, run])
    session.commit()
    store.delete_quarantine(upload.quarantine_key)
    session.refresh(source)
    return source
