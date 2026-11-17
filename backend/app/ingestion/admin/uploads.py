import uuid
from datetime import timedelta
from typing import BinaryIO, cast

from sqlmodel import Session, select

from app.core.config import settings
from app.core.errors import DomainError, ErrorCode
from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_payload_hash,
    idempotency_record_for_request,
    idempotency_request_hash,
    idempotency_result_payload,
    idempotency_scope,
)
from app.ingestion.admin.queries import check_expected_version
from app.ingestion.blob_store import (
    BlobStoreError,
    LocalBlobStore,
)
from app.ingestion.common import get_datetime_utc
from app.ingestion.contracts import (
    CompletedMultipartUploadPart,
    ManagedUploadBlobStore,
    MultipartUpload,
    MultipartUploadPartUrl,
)
from app.ingestion.pdf import PdfInspectionError, inspect_pdf_bytes
from app.ingestion.runtime.queue import (
    append_run_event,
    create_run_steps,
    enqueue_task,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    InstrumentType,
    SourceUploadStatus,
)
from app.legal.models import (
    IdempotencyRecord,
    IngestionRun,
    LegalInstrument,
    SourceDocument,
    SourceUpload,
)
from app.legal.schemas import (
    SourceUploadComplete,
    SourceUploadCreate,
)
from app.models import User

MAX_UPLOAD_BYTES = 500 * 1024 * 1024


MAX_SOURCE_PAGES = 1000


MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024


UPLOAD_URL_TTL_SECONDS = 15 * 60


def upload_url_for_upload(upload: SourceUpload) -> str:
    if upload.status not in (SourceUploadStatus.CREATED, SourceUploadStatus.UPLOADING):
        return ""
    if upload.upload_backend == "local":
        return local_upload_url(upload)
    if upload.upload_backend == "r2":
        if multipart_required(upload):
            return ""
        return managed_upload_store().create_presigned_put_url(
            key=upload.quarantine_key,
            content_type=upload.mime_type,
            metadata=upload_object_metadata(upload),
            expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
        )
    raise BlobStoreError(
        f"Unsupported ingestion upload backend: {upload.upload_backend}"
    )


def upload_headers_for_upload(upload: SourceUpload) -> dict[str, str]:
    headers = {"content-type": upload.mime_type}
    if upload.upload_backend == "r2":
        headers.update(metadata_headers(upload_object_metadata(upload)))
    return headers


def local_upload_url(upload: SourceUpload) -> str:
    return f"{settings.API_V1_STR}/admin/source-uploads/{upload.id}/object"


def managed_upload_store() -> ManagedUploadBlobStore:
    store = get_blob_store()
    for method_name in (
        "create_presigned_put_url",
        "create_multipart_upload",
        "complete_multipart_upload",
        "abort_multipart_upload",
    ):
        if not hasattr(store, method_name):
            raise BlobStoreError(
                "Configured blob store does not support managed browser uploads"
            )
    return cast(ManagedUploadBlobStore, store)


def multipart_required(upload: SourceUpload) -> bool:
    return upload.expected_size > MULTIPART_THRESHOLD_BYTES


def upload_object_metadata(upload: SourceUpload) -> dict[str, str]:
    metadata = {"source-upload-id": str(upload.id)}
    if upload.expected_sha256:
        metadata["sha256"] = upload.expected_sha256
    return metadata


def metadata_headers(metadata: dict[str, str]) -> dict[str, str]:
    return {f"x-amz-meta-{key}": value for key, value in metadata.items()}


def create_source_upload_multipart_parts(
    session: Session,
    upload_id: uuid.UUID,
    *,
    part_count: int,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> MultipartUpload:
    upload = get_source_upload_for_user(
        session, upload_id, current_user, for_update=True
    )
    scope = idempotency_scope("source_upload.multipart_parts", upload_id)
    request_hash = idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "part_count": part_count,
            "upload_id": str(upload_id),
        }
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return multipart_upload_from_idempotency_record(record)
    require_upload_open(upload)
    check_expected_version(upload.lock_version, expected_version)
    if upload.upload_backend != "r2":
        raise DomainError(
            ErrorCode.CONFLICT,
            "Multipart upload URLs are available only for R2 upload sessions",
        )
    if not multipart_required(upload):
        raise DomainError(
            ErrorCode.CONFLICT, "Multipart upload is required only above 100 MB"
        )
    multipart = managed_upload_store().create_multipart_upload(
        key=upload.quarantine_key,
        content_type=upload.mime_type,
        part_count=part_count,
        metadata=upload_object_metadata(upload),
        expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
    )
    upload.multipart_upload_id = multipart.upload_id
    upload.status = SourceUploadStatus.UPLOADING
    upload.expires_at = get_datetime_utc() + timedelta(seconds=UPLOAD_URL_TTL_SECONDS)
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    session.add(upload)
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="multipart_upload",
        result_id=upload.id,
        created_by=upload.created_by,
        result_payload={
            "upload_id": str(upload.id),
            "multipart_upload_id": multipart.upload_id,
            "parts": [
                {"part_number": part.part_number, "upload_url": part.upload_url}
                for part in multipart.parts
            ],
        },
    )
    session.commit()
    return multipart


def create_source_upload_session(
    session: Session, body: SourceUploadCreate, current_user: User
) -> SourceUpload:
    ensure_allowed_instrument_type(body.instrument_type)
    scope = "source_upload.create"
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        if record.result_id is None:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Idempotent source upload result is no longer available",
            )
        return get_source_upload_for_user(session, record.result_id, current_user)
    if body.expected_size > MAX_UPLOAD_BYTES:
        raise DomainError(
            ErrorCode.PAYLOAD_TOO_LARGE, "Source files must be 500 MB or smaller"
        )
    if body.mime_type != "application/pdf":
        raise DomainError(
            ErrorCode.UNSUPPORTED_MEDIA_TYPE, "Ingestion accepts PDF sources only"
        )

    upload_id = uuid.uuid4()
    store = get_blob_store()
    upload = SourceUpload(
        id=upload_id,
        idempotency_key=body.idempotency_key,
        created_by=current_user.id,
        instrument_slug=body.instrument_slug,
        instrument_title=body.instrument_title,
        instrument_type=body.instrument_type,
        instrument_short_title=body.instrument_short_title,
        instrument_year=body.instrument_year,
        instrument_status=body.instrument_status,
        enacted_at=body.enacted_at,
        effective_at=body.effective_at,
        ceased_at=body.ceased_at,
        is_legal_revision=body.is_legal_revision,
        legal_revision_effective_at=body.legal_revision_effective_at,
        source_title=body.source_title,
        authority=body.authority,
        source_url=body.source_url,
        source_tier=body.source_tier,
        published_at=body.published_at,
        retrieved_at=body.retrieved_at,
        original_filename=body.original_filename,
        mime_type=body.mime_type,
        expected_size=body.expected_size,
        expected_sha256=body.expected_sha256,
        upload_backend=settings.INGESTION_STORAGE_BACKEND,
        quarantine_key=store.quarantine_key(
            upload_id=str(upload_id), filename=body.original_filename
        ),
        status=SourceUploadStatus.CREATED,
        expires_at=get_datetime_utc() + timedelta(seconds=UPLOAD_URL_TTL_SECONDS),
    )
    session.add(upload)
    session.flush()
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="source_upload",
        result_id=upload.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(upload)
    return upload


def put_local_upload_object(
    session: Session,
    upload_id: uuid.UUID,
    content: BinaryIO,
    content_type: str,
    current_user: User,
) -> SourceUpload:
    upload = get_source_upload_for_user(
        session, upload_id, current_user, for_update=True
    )
    require_upload_open(upload)
    if upload.upload_backend != "local":
        raise DomainError(
            ErrorCode.BAD_REQUEST,
            "Local upload endpoint can only be used with local upload sessions",
        )
    if content_type.split(";", 1)[0].strip().lower() != upload.mime_type:
        raise DomainError(
            ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            "Uploaded object content type does not match the upload session",
        )
    try:
        store = get_blob_store()
        if not isinstance(store, LocalBlobStore):
            raise BlobStoreError("Local upload endpoint requires local storage")
        blob = store.put_quarantine_stream(
            upload_id=str(upload.id),
            filename=upload.original_filename,
            stream=content,
            content_type=upload.mime_type,
            metadata={"source_upload_id": str(upload.id)},
        )
    except BlobStoreError as exc:
        raise DomainError(ErrorCode.BAD_REQUEST, str(exc))

    upload.quarantine_key = blob.key
    upload.actual_sha256 = blob.sha256
    upload.status = SourceUploadStatus.UPLOADING
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def complete_source_upload(
    session: Session,
    upload_id: uuid.UUID,
    body: SourceUploadComplete,
    current_user: User,
) -> tuple[SourceUpload, SourceDocument | None, IngestionRun | None, bool]:
    upload = get_source_upload_for_user(
        session, upload_id, current_user, for_update=True
    )
    scope = idempotency_scope("source_upload.complete", upload_id)
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return completed_upload_from_idempotency_record(session, record)
    require_upload_open(upload)
    check_expected_version(upload.lock_version, body.expected_version)

    try:
        store = get_blob_store()
        if upload.multipart_upload_id:
            if not body.completed_parts:
                raise BlobStoreError(
                    "Multipart completion requires completed part ETags"
                )
            if upload.upload_backend != "r2":
                raise BlobStoreError("Multipart uploads are only supported by R2")
            managed_upload_store().complete_multipart_upload(
                key=upload.quarantine_key,
                upload_id=upload.multipart_upload_id,
                parts=[
                    CompletedMultipartUploadPart(
                        part_number=part.part_number,
                        etag=part.etag,
                    )
                    for part in body.completed_parts
                ],
            )
        head = store.head(upload.quarantine_key)
    except (BlobStoreError, FileNotFoundError) as exc:
        mark_upload_failed(session, upload, str(exc))
        raise DomainError(
            ErrorCode.BAD_REQUEST, "Uploaded object was not found in quarantine"
        )

    if head.size_bytes != upload.expected_size:
        mark_upload_failed(session, upload, "Uploaded object size does not match")
        raise DomainError(
            ErrorCode.BAD_REQUEST,
            "Uploaded object size does not match the upload session",
        )
    if upload.expected_sha256 and head.sha256 and head.sha256 != upload.expected_sha256:
        mark_upload_failed(
            session, upload, "Uploaded object metadata hash does not match"
        )
        raise DomainError(
            ErrorCode.BAD_REQUEST,
            "Uploaded object SHA-256 does not match the upload session",
        )

    # Completion is deliberately a control-plane operation. The object remains
    # under quarantine until the worker has streamed it, validated the PDF, and
    # completed malware scanning.
    upload.actual_sha256 = None
    upload.status = SourceUploadStatus.UPLOADED_PENDING_VERIFICATION
    upload.completed_at = get_datetime_utc()
    upload.lock_version += 1
    upload.updated_at = upload.completed_at
    session.add(upload)

    run = IngestionRun(
        source_upload_id=upload.id,
        source_document_id=None,
        created_by=current_user.id,
        status=IngestionRunStatus.QUEUED,
        current_stage=IngestionStage.VERIFYING_UPLOAD,
        pipeline_config={
            "instrument_parser": str(upload.instrument_type),
            **(
                {
                    "corpus_legal_status": "historical",
                    "source_edition_review": {
                        "edition": f"As enacted, {upload.instrument_year}",
                        "notice": "As enacted, may have been amended.",
                        "instrument_slug": upload.instrument_slug,
                    },
                }
                if upload.instrument_type == InstrumentType.ACT
                else {}
            ),
            "max_pages": MAX_SOURCE_PAGES,
            "expected_sha256": upload.expected_sha256,
            "expected_size": upload.expected_size,
            "claimed_sha256": body.actual_sha256,
            "storage_backend": upload.upload_backend,
            "is_legal_revision": upload.is_legal_revision,
            "legal_revision_effective_at": (
                upload.legal_revision_effective_at.isoformat()
                if upload.legal_revision_effective_at
                else None
            ),
        },
        expected_page_count=None,
    )
    session.add(run)
    session.flush()
    steps = create_run_steps(session, run, commit=False)
    uploading_step = next(
        step for step in steps if step.stage == IngestionStage.UPLOADING
    )
    uploading_step.status = IngestionStepStatus.SUCCEEDED
    uploading_step.completed_units = 1
    uploading_step.metrics = {
        "expected_sha256": upload.expected_sha256,
        "size_bytes": upload.expected_size,
    }
    uploading_step.completed_at = get_datetime_utc()
    uploading_step.updated_at = uploading_step.completed_at
    session.add(uploading_step)
    first_step = next(
        step for step in steps if step.stage == IngestionStage.VERIFYING_UPLOAD
    )
    enqueue_task(
        session,
        run=run,
        step=first_step,
        task_type=IngestionStage.VERIFYING_UPLOAD.value,
        idempotency_key=f"{run.id}:verify-upload",
        payload={"source_upload_id": str(upload.id)},
        priority=10,
        commit=False,
    )
    append_run_event(
        session,
        run,
        event_type="upload_completed",
        message="Upload completion recorded; verification queued",
        stage=IngestionStage.VERIFYING_UPLOAD,
        payload={"source_upload_id": str(upload.id)},
        commit=False,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="source_upload_complete",
        result_id=upload.id,
        created_by=current_user.id,
        result_payload={
            "upload_id": str(upload.id),
            "source_document_id": None,
            "run_id": str(run.id),
            "duplicate": False,
        },
    )
    session.commit()
    return upload, None, run, False


def multipart_upload_from_idempotency_record(
    record: IdempotencyRecord,
) -> MultipartUpload:
    payload = idempotency_result_payload(record)
    parts_payload = payload.get("parts")
    if not isinstance(parts_payload, list):
        raise DomainError(
            ErrorCode.CONFLICT, "Idempotent multipart result is no longer available"
        )
    parts: list[MultipartUploadPartUrl] = []
    for item in parts_payload:
        if not isinstance(item, dict):
            raise DomainError(
                ErrorCode.CONFLICT, "Idempotent multipart result is no longer available"
            )
        part_number = item.get("part_number")
        upload_url = item.get("upload_url")
        if not isinstance(part_number, int) or not isinstance(upload_url, str):
            raise DomainError(
                ErrorCode.CONFLICT, "Idempotent multipart result is no longer available"
            )
        parts.append(
            MultipartUploadPartUrl(part_number=part_number, upload_url=upload_url)
        )
    upload_id = payload.get("multipart_upload_id")
    if not isinstance(upload_id, str):
        raise DomainError(
            ErrorCode.CONFLICT, "Idempotent multipart result is no longer available"
        )
    return MultipartUpload(upload_id=upload_id, parts=tuple(parts))


def completed_upload_from_idempotency_record(
    session: Session, record: IdempotencyRecord
) -> tuple[SourceUpload, SourceDocument | None, IngestionRun | None, bool]:
    payload = idempotency_result_payload(record)
    upload_id = payload.get("upload_id")
    if not isinstance(upload_id, str):
        raise DomainError(
            ErrorCode.CONFLICT,
            "Idempotent upload completion result is no longer available",
        )
    upload = session.get(SourceUpload, uuid.UUID(upload_id))
    if not upload:
        raise DomainError(
            ErrorCode.CONFLICT,
            "Idempotent upload completion result is no longer available",
        )
    source = None
    source_id = payload.get("source_document_id")
    if isinstance(source_id, str):
        source = session.get(SourceDocument, uuid.UUID(source_id))
        if not source:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Idempotent upload completion result is no longer available",
            )
    run = None
    run_id = payload.get("run_id")
    if isinstance(run_id, str):
        run = session.get(IngestionRun, uuid.UUID(run_id))
        if not run:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Idempotent upload completion result is no longer available",
            )
    return upload, source, run, bool(payload.get("duplicate"))


def get_source_upload_for_user(
    session: Session, upload_id: uuid.UUID, user: User, *, for_update: bool = False
) -> SourceUpload:
    upload = session.get(
        SourceUpload,
        upload_id,
        with_for_update=for_update,
        populate_existing=for_update,
    )
    if upload is None or (upload.created_by != user.id and not user.is_superuser):
        raise DomainError(ErrorCode.NOT_FOUND, "Source upload not found")
    return upload


def require_upload_open(upload: SourceUpload) -> None:
    if upload.status not in (SourceUploadStatus.CREATED, SourceUploadStatus.UPLOADING):
        raise DomainError(ErrorCode.CONFLICT, "Source upload is no longer open")


def mark_upload_failed(
    session: Session, upload: SourceUpload, error_message: str
) -> None:
    upload.status = SourceUploadStatus.FAILED
    upload.error_message = error_message
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    session.add(upload)
    session.commit()


def validate_pdf(content: bytes) -> int:
    try:
        return inspect_pdf_bytes(content, max_pages=MAX_SOURCE_PAGES).page_count
    except PdfInspectionError as exc:
        raise DomainError(ErrorCode.BAD_REQUEST, str(exc))


def ensure_allowed_instrument_type(instrument_type: InstrumentType) -> None:
    if str(instrument_type) not in settings.INGESTION_ALLOWED_INSTRUMENT_TYPES:
        raise DomainError(
            ErrorCode.VALIDATION_ERROR,
            f"Ingestion is disabled for instrument type: {instrument_type}",
        )


def get_or_create_instrument(session: Session, upload: SourceUpload) -> LegalInstrument:
    ensure_allowed_instrument_type(upload.instrument_type)
    instrument = session.exec(
        select(LegalInstrument).where(LegalInstrument.slug == upload.instrument_slug)
    ).first()
    if instrument:
        if instrument.instrument_type != upload.instrument_type:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Instrument slug already belongs to a different instrument type",
            )
        return instrument
    instrument = LegalInstrument(
        slug=upload.instrument_slug,
        title=upload.instrument_title,
        short_title=upload.instrument_short_title,
        instrument_type=upload.instrument_type,
        jurisdiction="NG",
        year=upload.instrument_year,
        status=upload.instrument_status,
        enacted_at=upload.enacted_at,
        effective_at=upload.effective_at,
        ceased_at=upload.ceased_at,
    )
    session.add(instrument)
    session.commit()
    session.refresh(instrument)
    return instrument
