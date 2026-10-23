import difflib
import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import BinaryIO, cast

from fastapi import HTTPException, status
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.ingestion.blob_store import BlobStoreError, LocalBlobStore
from app.ingestion.composition import (
    act_review_gates,
    composition_gates,
    entry_snapshot,
    manifest_hash,
    member_snapshot,
    release_entries,
)
from app.ingestion.contracts import (
    BlobStore,
    CompletedMultipartUploadPart,
    ManagedUploadBlobStore,
    MultipartUpload,
    MultipartUploadPartUrl,
)
from app.ingestion.evaluation import active_evaluation_item_count
from app.ingestion.pdf import PdfInspectionError, inspect_pdf_bytes
from app.ingestion.pgvector_repository import validate_index_build
from app.ingestion.qdrant import QdrantHttpIndexAdapter, QdrantIndexError
from app.ingestion.r2_blob_store import R2BlobStore
from app.ingestion.text_alignment import compact_text
from app.ingestion.validation import has_unbalanced_punctuation
from app.ingestion.workflow import (
    append_run_event,
    create_run_steps,
    enqueue_task,
    mark_run_cancelled,
)
from app.legal.enums import (
    AdminRole,
    AuditSeverity,
    CorpusReleaseStatus,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    InstrumentType,
    PageInclusionStatus,
    ReleasePromotionStatus,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    SourceUploadStatus,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    AdminRoleAssignment,
    AuditEvent,
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    ExtractionCandidate,
    IdempotencyRecord,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    ProvisionVersion,
    ReleasePromotionAttempt,
    RetrievalIndexBuild,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    VectorIndex,
)
from app.legal.schemas import (
    AdminOperationalAlertPublic,
    CompositeReleaseCreate,
    PageSelectionUpdate,
    ReviewDecisionCreate,
    ReviewIssueUpdate,
    ReviewItemDerive,
    ReviewItemUpdate,
    SourceUploadComplete,
    SourceUploadCreate,
)
from app.models import User

MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_SOURCE_PAGES = 1000
MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024
UPLOAD_URL_TTL_SECONDS = 15 * 60
MIN_PUBLICATION_RECALL_AT_10 = 0.95
OPERATIONAL_ALERT_LIMIT = 100


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


def read_admin_operational_alerts(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int = OPERATIONAL_ALERT_LIMIT,
) -> list[AdminOperationalAlertPublic]:
    detected_now = now or get_datetime_utc()
    alerts: list[AdminOperationalAlertPublic] = []

    failed_runs = session.exec(
        select(IngestionRun)
        .where(IngestionRun.status == IngestionRunStatus.FAILED)
        .order_by(col(IngestionRun.updated_at).desc())
        .limit(limit)
    ).all()
    for run in failed_runs:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"run-failed:{run.id}",
                alert_type="terminal_failure",
                severity=AuditSeverity.HIGH,
                title="Terminal ingestion failure",
                message=_alert_error_message(
                    run.error_details,
                    f"{_enum_value(run.current_stage)} ended in a failed run.",
                ),
                detected_at=_alert_time(detected_now, run.completed_at, run.updated_at),
                run_id=run.id,
                evidence={
                    "status": _enum_value(run.status),
                    "stage": _enum_value(run.current_stage),
                    "error_details": run.error_details,
                },
            )
        )

    stalled_tasks = session.exec(
        select(IngestionTask)
        .where(
            col(IngestionTask.status).in_(
                [IngestionTaskStatus.LEASED, IngestionTaskStatus.RUNNING]
            ),
            col(IngestionTask.leased_until) != None,  # noqa: E711
            col(IngestionTask.leased_until) < detected_now,
        )
        .order_by(col(IngestionTask.leased_until))
        .limit(limit)
    ).all()
    for task in stalled_tasks:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"stalled-lease:{task.id}",
                alert_type="stalled_lease",
                severity=AuditSeverity.WARNING,
                title="Stalled worker lease",
                message=(
                    f"{task.task_type} lease expired for "
                    f"{task.lease_owner or 'an unknown worker'}."
                ),
                detected_at=_alert_time(detected_now, task.leased_until),
                run_id=task.run_id,
                step_id=task.step_id,
                task_id=task.id,
                evidence={
                    "task_type": task.task_type,
                    "status": _enum_value(task.status),
                    "lease_owner": task.lease_owner,
                    "leased_until": task.leased_until.isoformat()
                    if task.leased_until
                    else None,
                    "heartbeat_at": task.heartbeat_at.isoformat()
                    if task.heartbeat_at
                    else None,
                },
            )
        )

    blocking_issues = session.exec(
        select(ReviewIssue)
        .where(
            ReviewIssue.status == ReviewIssueStatus.OPEN,
            ReviewIssue.blocking == True,  # noqa: E712
        )
        .order_by(col(ReviewIssue.created_at).desc())
        .limit(limit)
    ).all()
    for issue in blocking_issues:
        candidate = session.get(ExtractionCandidate, issue.candidate_id)
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"blocking-review-issue:{issue.id}",
                alert_type="unresolved_blocking_issue",
                severity=AuditSeverity.HIGH
                if issue.severity == ReviewIssueSeverity.BLOCKING
                else AuditSeverity.WARNING,
                title="Unresolved blocking review issue",
                message=issue.message,
                detected_at=issue.created_at,
                run_id=candidate.run_id if candidate else None,
                candidate_id=issue.candidate_id,
                issue_id=issue.id,
                evidence={
                    "issue_type": issue.issue_type,
                    "severity": _enum_value(issue.severity),
                    "candidate_path": candidate.canonical_path if candidate else None,
                    "evidence": issue.evidence,
                },
            )
        )

    failed_embedding_runs = session.exec(
        select(EmbeddingRun)
        .where(EmbeddingRun.status == EmbeddingRunStatus.FAILED)
        .order_by(col(EmbeddingRun.created_at).desc())
        .limit(limit)
    ).all()
    for embedding_run in failed_embedding_runs:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"embedding-provider-outage:{embedding_run.id}",
                alert_type="embedding_provider_outage",
                severity=AuditSeverity.HIGH,
                title="Embedding provider outage",
                message=_alert_error_message(
                    embedding_run.error_details,
                    "An embedding benchmark or indexing run failed.",
                ),
                detected_at=_alert_time(
                    detected_now,
                    embedding_run.completed_at,
                    embedding_run.created_at,
                ),
                release_id=embedding_run.release_id,
                embedding_run_id=embedding_run.id,
                evidence={
                    "profile_id": str(embedding_run.profile_id),
                    "benchmark_dataset_version": (
                        embedding_run.benchmark_dataset_version
                    ),
                    "error_details": embedding_run.error_details,
                },
            )
        )

    failed_promotions = session.exec(
        select(ReleasePromotionAttempt)
        .where(ReleasePromotionAttempt.status == ReleasePromotionStatus.FAILED)
        .order_by(col(ReleasePromotionAttempt.created_at).desc())
        .limit(limit)
    ).all()
    for promotion in failed_promotions:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"publication-failed:{promotion.id}",
                alert_type="publication_failure",
                severity=AuditSeverity.HIGH,
                title="Publication failure",
                message=_alert_error_message(
                    promotion.error_details,
                    "Corpus release publication failed before promotion completed.",
                ),
                detected_at=_alert_time(
                    detected_now,
                    promotion.completed_at,
                    promotion.created_at,
                ),
                release_id=promotion.release_id,
                promotion_attempt_id=promotion.id,
                evidence={
                    "vector_index_id": str(promotion.vector_index_id)
                    if promotion.vector_index_id
                    else None,
                    "previous_release_id": str(promotion.previous_release_id)
                    if promotion.previous_release_id
                    else None,
                    "target_collection_name": promotion.target_collection_name,
                    "rollback_completed": promotion.rollback_completed,
                    "error_details": promotion.error_details,
                },
            )
        )

    alerts.sort(key=lambda alert: alert.detected_at, reverse=True)
    return alerts[:limit]


def get_blob_store() -> BlobStore:
    if settings.INGESTION_STORAGE_BACKEND == "r2":
        missing = [
            name
            for name, value in {
                "R2_ENDPOINT_URL": settings.R2_ENDPOINT_URL,
                "R2_BUCKET_NAME": settings.R2_BUCKET_NAME,
                "R2_ACCESS_KEY_ID": settings.R2_ACCESS_KEY_ID,
                "R2_SECRET_ACCESS_KEY": settings.R2_SECRET_ACCESS_KEY,
            }.items()
            if not value
        ]
        if missing:
            raise BlobStoreError(
                f"R2 storage is missing required settings: {', '.join(missing)}"
            )
        return R2BlobStore(
            endpoint_url=cast(str, settings.R2_ENDPOINT_URL),
            bucket_name=cast(str, settings.R2_BUCKET_NAME),
            access_key_id=cast(str, settings.R2_ACCESS_KEY_ID),
            secret_access_key=cast(str, settings.R2_SECRET_ACCESS_KEY),
        )
    return LocalBlobStore(Path(settings.INGESTION_STORAGE_DIR))


def upload_url_for_upload(upload: SourceUpload) -> str:
    if upload.upload_backend == "local":
        return local_upload_url(upload)
    if upload.upload_backend == "r2":
        if _multipart_required(upload):
            return ""
        return _managed_upload_store().create_presigned_put_url(
            key=upload.quarantine_key,
            content_type=upload.mime_type,
            metadata=_upload_object_metadata(upload),
            expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
        )
    raise BlobStoreError(
        f"Unsupported ingestion upload backend: {upload.upload_backend}"
    )


def upload_headers_for_upload(upload: SourceUpload) -> dict[str, str]:
    headers = {"content-type": upload.mime_type}
    if upload.upload_backend == "r2":
        headers.update(_metadata_headers(_upload_object_metadata(upload)))
    return headers


def local_upload_url(upload: SourceUpload) -> str:
    return f"{settings.API_V1_STR}/admin/source-uploads/{upload.id}/object"


def _managed_upload_store() -> ManagedUploadBlobStore:
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


def _multipart_required(upload: SourceUpload) -> bool:
    return upload.expected_size > MULTIPART_THRESHOLD_BYTES


def _upload_object_metadata(upload: SourceUpload) -> dict[str, str]:
    metadata = {"source-upload-id": str(upload.id)}
    if upload.expected_sha256:
        metadata["sha256"] = upload.expected_sha256
    return metadata


def _metadata_headers(metadata: dict[str, str]) -> dict[str, str]:
    return {f"x-amz-meta-{key}": value for key, value in metadata.items()}


def create_source_upload_multipart_parts(
    session: Session,
    upload_id: uuid.UUID,
    *,
    part_count: int,
    expected_version: int,
    idempotency_key: str,
) -> MultipartUpload:
    scope = _idempotency_scope("source_upload.multipart_parts", upload_id)
    request_hash = _idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "part_count": part_count,
            "upload_id": str(upload_id),
        }
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _multipart_upload_from_idempotency_record(record)
    upload = _get_upload(session, upload_id)
    _check_expected_version(upload.lock_version, expected_version)
    if upload.upload_backend != "r2":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multipart upload URLs are available only for R2 upload sessions",
        )
    if not _multipart_required(upload):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multipart upload is required only above 100 MB",
        )
    multipart = _managed_upload_store().create_multipart_upload(
        key=upload.quarantine_key,
        content_type=upload.mime_type,
        part_count=part_count,
        metadata=_upload_object_metadata(upload),
        expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
    )
    upload.multipart_upload_id = multipart.upload_id
    upload.status = SourceUploadStatus.UPLOADING
    upload.expires_at = get_datetime_utc() + timedelta(seconds=UPLOAD_URL_TTL_SECONDS)
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    session.add(upload)
    _add_idempotency_record(
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
    _ensure_allowed_instrument_type(body.instrument_type)
    scope = "source_upload.create"
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        upload = session.get(SourceUpload, record.result_id)
        if not upload:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent source upload result is no longer available",
            )
        return upload
    if body.expected_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Source files must be 500 MB or smaller",
        )
    if body.mime_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Ingestion accepts PDF sources only",
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
    _add_idempotency_record(
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
    session: Session, upload_id: uuid.UUID, content: BinaryIO, content_type: str
) -> SourceUpload:
    upload = _get_upload(session, upload_id)
    if upload.upload_backend != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local upload endpoint can only be used with local upload sessions",
        )
    if content_type.split(";", 1)[0].strip().lower() != upload.mime_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded object content type does not match the upload session",
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
        raise HTTPException(status_code=400, detail=str(exc))

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
    scope = _idempotency_scope("source_upload.complete", upload_id)
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _completed_upload_from_idempotency_record(session, record)
    upload = _get_upload(session, upload_id)
    _check_expected_version(upload.lock_version, body.expected_version)

    try:
        store = get_blob_store()
        if upload.multipart_upload_id:
            if not body.completed_parts:
                raise BlobStoreError(
                    "Multipart completion requires completed part ETags"
                )
            if upload.upload_backend != "r2":
                raise BlobStoreError("Multipart uploads are only supported by R2")
            _managed_upload_store().complete_multipart_upload(
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
        _mark_upload_failed(session, upload, str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded object was not found in quarantine",
        )

    if head.size_bytes != upload.expected_size:
        _mark_upload_failed(session, upload, "Uploaded object size does not match")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded object size does not match the upload session",
        )
    if upload.expected_sha256 and head.sha256 and head.sha256 != upload.expected_sha256:
        _mark_upload_failed(
            session, upload, "Uploaded object metadata hash does not match"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded object SHA-256 does not match the upload session",
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
    session.commit()
    session.refresh(upload)

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
    session.commit()
    session.refresh(run)
    steps = create_run_steps(session, run)
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
    session.commit()
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
    )
    append_run_event(
        session,
        run,
        event_type="upload_completed",
        message="Upload completion recorded; verification queued",
        stage=IngestionStage.VERIFYING_UPLOAD,
        payload={"source_upload_id": str(upload.id)},
    )
    _add_idempotency_record(
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


def verify_source_document(
    session: Session,
    source_document_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    reason: str,
    current_user: User,
) -> SourceDocument:
    scope = _idempotency_scope("source_document.verify", source_document_id)
    request_hash = _idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "reason": reason,
            "source_document_id": str(source_document_id),
        }
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_source_document(session, source_document_id)

    source = _get_source_document(session, source_document_id)
    _check_expected_version(source.lock_version, expected_version)
    if source.verification_status != VerificationStatus.VERIFIED:
        now = get_datetime_utc()
        source.verification_status = VerificationStatus.VERIFIED
        source.verified_by = current_user.id
        source.verified_at = now
        source.lock_version += 1
        session.add(source)
        session.add(
            AuditEvent(
                actor_user_id=current_user.id,
                action="source_document.verified",
                entity_type="source_document",
                entity_id=source.id,
                severity=AuditSeverity.INFO,
                payload={"reason": reason},
            )
        )
        session.commit()

    _queue_materialization_for_verified_source(session, source=source)
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="source_document",
        result_id=source.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(source)
    return source


def update_page_selection(
    session: Session,
    run_id: uuid.UUID,
    body: PageSelectionUpdate,
    current_user: User,
) -> list[SourcePage]:
    scope = _idempotency_scope("ingestion_run.page_selection", run_id)
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _pages_for_idempotency_record(session, record)
    run = session.exec(
        select(IngestionRun).where(IngestionRun.id == run_id).with_for_update()
    ).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    _check_expected_version(run.lock_version, body.expected_run_version)
    imported_review = (
        run.status == IngestionRunStatus.WAITING_FOR_REVIEW
        and run.current_stage == IngestionStage.REVIEW
        and bool((run.pipeline_config or {}).get("review_import_complete"))
    )
    if not imported_review and (
        run.status != IngestionRunStatus.WAITING_FOR_INPUT
        or run.current_stage != IngestionStage.AWAITING_PAGE_CONFIRMATION
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Page selection is not currently awaiting confirmation",
        )
    all_pages = session.exec(
        select(SourcePage).where(SourcePage.run_id == run.id).with_for_update()
    ).all()
    requested_numbers = [item.page_number for item in body.pages]
    if len(requested_numbers) != len(set(requested_numbers)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each profiled page must be included exactly once",
        )
    profiled_numbers = {page.page_number for page in all_pages}
    if set(requested_numbers) != profiled_numbers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page selection must include every profiled page exactly once",
        )
    pages_by_number = {page.page_number: page for page in all_pages}
    if imported_review and any(
        page.inclusion_status
        not in {PageInclusionStatus.INCLUDED, PageInclusionStatus.EXCLUDED}
        or not (page.inclusion_reason or "").strip()
        for page in body.pages
    ):
        raise HTTPException(
            status_code=422,
            detail="Imported review pages require explicit inclusion decisions and reasons",
        )
    pages: list[SourcePage] = []
    for requested_page in body.pages:
        page = pages_by_number.get(requested_page.page_number)
        if not page:
            raise HTTPException(status_code=404, detail="Source page not found")
        _check_expected_version(page.lock_version, requested_page.expected_version)
        page.inclusion_status = requested_page.inclusion_status
        page.inclusion_reason = requested_page.inclusion_reason
        page.lock_version += 1
        session.add(page)
        pages.append(page)
    if imported_review:
        candidates = session.exec(
            select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
        ).all()
        included = {
            page.page_number
            for page in pages
            if page.inclusion_status == PageInclusionStatus.INCLUDED
        }
        for candidate in candidates:
            if (
                candidate.status == ExtractionCandidateStatus.MATERIALIZED
                or candidate.materialized_version_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Materialized runs cannot change page boundaries",
                )
            _revalidate_review_page_coverage(session, candidate, included, current_user)
            if candidate.status in {
                ExtractionCandidateStatus.APPROVED,
                ExtractionCandidateStatus.AUTO_APPROVED,
            }:
                candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
            candidate.lock_version += 1
            session.add(candidate)
            for issue in session.exec(
                select(ReviewIssue).where(
                    ReviewIssue.candidate_id == candidate.id,
                    ReviewIssue.issue_type == "provisional_page_boundaries",
                    ReviewIssue.status == ReviewIssueStatus.OPEN,
                )
            ).all():
                issue.status = ReviewIssueStatus.RESOLVED
                issue.resolved_by = current_user.id
                issue.resolved_at = get_datetime_utc()
                issue.resolution_reason = "All imported source pages received explicit reviewed boundary decisions."
                issue.resolution_evidence = {
                    "page_numbers": sorted(included),
                    "idempotency_key": body.idempotency_key,
                }
                session.add(issue)
            session.flush()
            candidate.blocking_issue_count = _open_blocking_issue_count(
                session, candidate.id
            )
        run.pipeline_config = {
            **run.pipeline_config,
            "provisional_page_boundaries": False,
        }
        run.lock_version += 1
        run.updated_at = get_datetime_utc()
        session.add(run)
        append_run_event(
            session,
            run,
            event_type="review_page_boundaries_confirmed",
            message="Imported page boundaries confirmed; candidate review remains required",
            stage=IngestionStage.REVIEW,
            payload={
                "actor_user_id": str(current_user.id),
                "pages": [item.model_dump(mode="json") for item in body.pages],
            },
            commit=False,
        )
        _add_idempotency_record(
            session,
            scope=scope,
            idempotency_key=body.idempotency_key,
            request_hash=request_hash,
            result_type="page_selection",
            result_id=run.id,
            created_by=current_user.id,
            result_payload={
                "run_id": str(run.id),
                "page_numbers": [page.page_number for page in pages],
            },
        )
        session.commit()
        for page in pages:
            session.refresh(page)
        return pages
    awaiting_step = _get_run_step(
        session, run.id, IngestionStage.AWAITING_PAGE_CONFIRMATION
    )
    awaiting_step.status = IngestionStepStatus.SUCCEEDED
    awaiting_step.completed_units = len(pages)
    awaiting_step.completed_at = get_datetime_utc()
    awaiting_step.updated_at = awaiting_step.completed_at
    session.add(awaiting_step)
    native_extraction_step = _get_run_step(
        session, run.id, IngestionStage.NATIVE_EXTRACTION
    )
    run.status = IngestionRunStatus.RUNNING
    run.current_stage = IngestionStage.NATIVE_EXTRACTION
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add(run)
    enqueue_task(
        session,
        run=run,
        step=native_extraction_step,
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:{IngestionStage.NATIVE_EXTRACTION.value}",
        payload={"source_document_id": str(run.source_document_id)},
        priority=30,
        commit=False,
    )
    append_run_event(
        session,
        run,
        event_type="page_selection_confirmed",
        message="Page inclusion ranges confirmed",
        stage=IngestionStage.AWAITING_PAGE_CONFIRMATION,
        payload={"page_count": len(pages)},
        commit=False,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="page_selection",
        result_id=run.id,
        created_by=current_user.id,
        result_payload={
            "run_id": str(run.id),
            "page_numbers": [page.page_number for page in pages],
        },
    )
    session.commit()
    for page in pages:
        session.refresh(page)
    return pages


def update_review_candidate(
    session: Session,
    candidate_id: uuid.UUID,
    body: ReviewItemUpdate,
    current_user: User,
) -> CandidateRevision:
    scope = _idempotency_scope("review_item.update", candidate_id)
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        revision = (
            session.get(CandidateRevision, record.result_id)
            if record.result_id
            else None
        )
        if not revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent review revision result is no longer available",
            )
        return revision
    candidate = _get_candidate(session, candidate_id)
    _check_expected_version(candidate.lock_version, body.expected_version)
    _validate_review_patch(session, candidate, body)
    latest_revision = _latest_candidate_revision(session, candidate.id)
    previous_text = (
        latest_revision.revised_text if latest_revision else candidate.raw_text
    )
    next_text = body.revised_text if body.revised_text is not None else previous_text
    before_snapshot = _candidate_snapshot(candidate, previous_text)
    changed_fields: dict[str, object] = {}
    json_patch = body.model_dump(mode="json", exclude_unset=True)
    for field_name in (
        "heading",
        "kind",
        "number",
        "parent_candidate_id",
        "canonical_path",
        "sort_key",
        "source_page_start",
        "source_page_end",
        "source_spans",
    ):
        value = getattr(body, field_name)
        if field_name in body.model_fields_set:
            setattr(candidate, field_name, value)
            changed_fields[field_name] = json_patch[field_name]
    after_snapshot = _candidate_snapshot(candidate, next_text)
    for field_name, after_value in after_snapshot.items():
        before_value = before_snapshot.get(field_name)
        if before_value != after_value:
            changed_fields.setdefault(
                field_name, {"before": before_value, "after": after_value}
            )
    revision_number = (latest_revision.revision_number if latest_revision else 1) + 1
    revision = CandidateRevision(
        candidate_id=candidate.id,
        revision_number=revision_number,
        previous_text=previous_text,
        revised_text=next_text,
        diff=_line_diff(previous_text or "", next_text or ""),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        changed_fields=changed_fields,
        reason=body.reason,
        revised_by=current_user.id,
    )
    candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
    candidate.revision_number = revision_number
    candidate.lock_version += 1
    candidate.updated_at = get_datetime_utc()
    session.add(revision)
    session.add(candidate)
    session.flush()
    _revalidate_candidate_revision_text(
        session,
        candidate=candidate,
        revised_text=next_text or "",
        current_user=current_user,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="candidate_revision",
        result_id=revision.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(revision)
    return revision


def derive_review_candidate(
    session: Session,
    candidate_id: uuid.UUID,
    body: ReviewItemDerive,
    current_user: User,
) -> ExtractionCandidate:
    scope = _idempotency_scope("review_item.derive", candidate_id)
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record and record.result_id:
        return _get_candidate(session, record.result_id)
    original = _get_candidate(session, candidate_id)
    _check_expected_version(original.lock_version, body.expected_version)
    if (
        original.materialized_version_id
        or original.status == ExtractionCandidateStatus.MATERIALIZED
    ):
        raise HTTPException(
            status_code=409, detail="Derive from an unmaterialized review candidate"
        )
    candidate = ExtractionCandidate(
        run_id=original.run_id,
        source_document_id=original.source_document_id,
        kind=body.kind,
        number=body.number,
        heading=body.heading,
        parent_candidate_id=body.parent_candidate_id,
        canonical_path=body.canonical_path,
        sort_key=body.sort_key,
        # A recovered structural heading must not inherit its origin's body.
        # The original extraction is retained in the revision's before snapshot.
        raw_text=original.raw_text if body.revised_text is not None else None,
        source_page_start=body.source_page_start,
        source_page_end=body.source_page_end,
        source_spans=body.source_spans,
        parser_version="reviewer-derived-v1",
        extractor_version=original.extractor_version,
        revision_number=2,
    )
    _validate_review_patch(session, candidate, body)
    session.add(candidate)
    session.flush()
    revision = CandidateRevision(
        candidate_id=candidate.id,
        revision_number=2,
        previous_text=original.raw_text,
        revised_text=body.revised_text,
        diff=_line_diff(original.raw_text or "", body.revised_text or ""),
        before_snapshot=_candidate_snapshot(original, original.raw_text),
        after_snapshot=_candidate_snapshot(candidate, body.revised_text),
        changed_fields={"derived_from_candidate_id": str(original.id)},
        reason=body.reason,
        revised_by=current_user.id,
    )
    session.add(revision)
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="review_item.derived",
            entity_type="extraction_candidate",
            entity_id=candidate.id,
            reason=body.reason,
            payload={
                "source_candidate_id": str(original.id),
                "source_document_id": str(original.source_document_id),
            },
        )
    )
    _revalidate_candidate_revision_text(
        session,
        candidate=candidate,
        revised_text=body.revised_text or "",
        current_user=current_user,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="extraction_candidate",
        result_id=candidate.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(candidate)
    return candidate


def _validate_review_patch(
    session: Session, candidate: ExtractionCandidate, body: ReviewItemUpdate
) -> None:
    """Reject unsafe structure edits before changing the audited candidate."""
    if (
        candidate.status == ExtractionCandidateStatus.MATERIALIZED
        or candidate.materialized_version_id
        or candidate.materialized_provision_id
    ):
        raise HTTPException(
            status_code=409, detail="Materialized candidates cannot be revised"
        )
    run = session.get(IngestionRun, candidate.run_id)
    if not run or run.status == IngestionRunStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Cancelled runs cannot be revised")
    # Serialize graph edits within a run, including path uniqueness checks.
    session.exec(
        select(IngestionRun).where(IngestionRun.id == run.id).with_for_update()
    ).one()
    path = body.canonical_path or candidate.canonical_path
    duplicate = session.exec(
        select(ExtractionCandidate.id).where(
            ExtractionCandidate.run_id == candidate.run_id,
            ExtractionCandidate.canonical_path == path,
            ExtractionCandidate.id != candidate.id,
        )
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Canonical path already exists in this run"
        )
    parent_id = (
        body.parent_candidate_id
        if "parent_candidate_id" in body.model_fields_set
        else candidate.parent_candidate_id
    )
    visited = {candidate.id}
    while parent_id:
        if parent_id in visited:
            raise HTTPException(
                status_code=422, detail="Candidate parent would create a cycle"
            )
        visited.add(parent_id)
        parent = session.get(ExtractionCandidate, parent_id)
        if (
            not parent
            or parent.run_id != candidate.run_id
            or parent.source_document_id != candidate.source_document_id
        ):
            raise HTTPException(
                status_code=422, detail="Parent must belong to the same source and run"
            )
        parent_id = parent.parent_candidate_id
    start = (
        body.source_page_start
        if "source_page_start" in body.model_fields_set
        else candidate.source_page_start
    )
    end = (
        body.source_page_end
        if "source_page_end" in body.model_fields_set
        else candidate.source_page_end
    )
    source = session.get(SourceDocument, candidate.source_document_id)
    if start is not None and end is not None and end < start:
        raise HTTPException(
            status_code=422, detail="Source end page precedes start page"
        )
    if (
        source
        and source.page_count
        and any(page and page > source.page_count for page in (start, end))
    ):
        raise HTTPException(
            status_code=422, detail="Source page exceeds the document page count"
        )
    if body.model_fields_set & {"source_spans", "source_page_start", "source_page_end"}:
        spans = (
            body.source_spans
            if "source_spans" in body.model_fields_set
            else candidate.source_spans
        )
        for span in spans or []:
            page = span.get("page_number", span.get("page"))
            if (
                not isinstance(page, int)
                or isinstance(page, bool)
                or page < 1
                or (start is not None and page < start)
                or (end is not None and page > end)
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Each source span must name a page within the candidate range",
                )


def decide_review_candidate(
    session: Session,
    candidate_id: uuid.UUID,
    body: ReviewDecisionCreate,
    current_user: User,
) -> ExtractionCandidate:
    scope = _idempotency_scope("review_item.decision", candidate_id)
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_candidate(session, candidate_id)
    candidate = _get_candidate(session, candidate_id)
    _check_expected_version(candidate.lock_version, body.expected_version)
    if body.decision == ReviewDecisionType.APPROVE and _has_open_blocking_issue(
        session, candidate.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Blocking review issues must be resolved before approval",
        )
    decision = ReviewDecisionRecord(
        candidate_id=candidate.id,
        decision=body.decision,
        decided_by=current_user.id,
        reason=body.reason,
    )
    candidate.status = _candidate_status_for_decision(body.decision)
    candidate.lock_version += 1
    candidate.updated_at = get_datetime_utc()
    session.add(decision)
    session.add(candidate)
    session.flush()
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="review_decision",
        result_id=decision.id,
        created_by=current_user.id,
    )
    session.commit()
    if body.decision == ReviewDecisionType.APPROVE:
        _maybe_complete_review_and_queue_materialization(session, candidate=candidate)
    session.refresh(candidate)
    return candidate


def update_review_issue(
    session: Session,
    issue_id: uuid.UUID,
    body: ReviewIssueUpdate,
    current_user: User,
) -> ReviewIssue:
    scope = _idempotency_scope("review_issue.update", issue_id)
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record:
        issue = session.get(ReviewIssue, issue_id)
        if issue is None:
            raise HTTPException(status_code=404, detail="Review issue not found")
        return issue
    issue = session.exec(
        select(ReviewIssue).where(ReviewIssue.id == issue_id).with_for_update()
    ).one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Review issue not found")
    if issue.status == ReviewIssueStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Review issue is already resolved")
    if issue.blocking and not current_user.is_superuser:
        raise HTTPException(
            status_code=409,
            detail="Blocking issues must be resolved by candidate revalidation",
        )
    if issue.blocking and not body.superuser_override_reason:
        raise HTTPException(
            status_code=409,
            detail="A blocking issue override requires a reason",
        )
    now = get_datetime_utc()
    issue.status = ReviewIssueStatus.RESOLVED
    issue.resolved_by = current_user.id
    issue.resolved_at = now
    issue.resolution_reason = body.reason
    issue.resolution_evidence = body.evidence
    session.add(issue)
    candidate = session.get(ExtractionCandidate, issue.candidate_id)
    if candidate:
        candidate.blocking_issue_count = _open_blocking_issue_count(
            session, candidate.id
        )
        candidate.updated_at = now
        session.add(candidate)
    if body.superuser_override_reason:
        session.add(
            AuditEvent(
                actor_user_id=current_user.id,
                action="review_issue.blocking_override",
                entity_type="review_issue",
                entity_id=issue.id,
                severity=AuditSeverity.HIGH,
                reason=body.superuser_override_reason,
                payload={"issue_type": issue.issue_type},
            )
        )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="review_issue",
        result_id=issue.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(issue)
    return issue


def compose_corpus_release(
    session: Session, body: CompositeReleaseCreate, current_user: User
) -> CorpusRelease:
    scope = "corpus_release.compose"
    request_hash = _idempotency_request_hash(body)
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record and record.result_id:
        return _get_release(session, record.result_id)
    requested = [
        (body.base_release_id, body.expected_base_version),
        *[(item.release_id, item.expected_version) for item in body.members],
    ]
    members: list[CorpusRelease] = []
    snapshots: list[dict[str, object]] = []
    union: dict[uuid.UUID, CorpusReleaseEntry] = {}
    versions_by_provision: dict[uuid.UUID, uuid.UUID] = {}
    for index, (release_id, expected_version) in enumerate(requested):
        member = session.exec(
            select(CorpusRelease)
            .where(CorpusRelease.id == release_id)
            .with_for_update()
        ).one_or_none()
        if member is None:
            raise HTTPException(
                status_code=404, detail="Member corpus release was not found"
            )
        if index == 0:
            # Concurrent identical requests serialize on the production base.
            record = _idempotency_record_for_request(
                session,
                scope=scope,
                idempotency_key=body.idempotency_key,
                request_hash=request_hash,
            )
            if record and record.result_id:
                return _get_release(session, record.result_id)
        _check_expected_version(member.lock_version, expected_version)
        if (index == 0 and member.status != CorpusReleaseStatus.PRODUCTION) or (
            index > 0 and member.status != CorpusReleaseStatus.APPROVED
        ):
            raise HTTPException(
                status_code=409,
                detail="Composition requires the current production base and approved Act releases",
            )
        entries = release_entries(session, member.id)
        try:
            snapshot = member_snapshot(session, member)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        types = {item["type"] for item in snapshot["instruments"]}
        if (index == 0 and str(InstrumentType.CONSTITUTION) not in types) or (
            index > 0
            and (
                types != {str(InstrumentType.ACT)} or len(snapshot["instruments"]) != 1
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="The base must contain the Constitution; each added member must contain one Act",
            )
        if not member.source_manifest_hash:
            raise HTTPException(
                status_code=409,
                detail="Each member requires a retained source manifest hash",
            )
        gates = _release_source_and_review_gates(session, entries, release=member)
        gates.extend(act_review_gates(session, entries))
        if gates:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Member source/review gates must pass before composition",
                    "release_id": str(member.id),
                    "gates": sorted(set(gates)),
                },
            )
        for entry in entries:
            version = session.get(ProvisionVersion, entry.provision_version_id)
            assert version is not None  # Checked by member_snapshot.
            previous = versions_by_provision.setdefault(
                version.provision_id, version.id
            )
            if previous != version.id:
                raise HTTPException(
                    status_code=409,
                    detail="Members contain conflicting versions of the same provision",
                )
            existing = union.setdefault(version.id, entry)
            if (existing.source_document_id, existing.ingestion_run_id) != (
                entry.source_document_id,
                entry.ingestion_run_id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Members disagree about an entry's review provenance",
                )
        members.append(member)
        snapshots.append(snapshot)
    if session.exec(
        select(CorpusRelease).where(CorpusRelease.version == body.version)
    ).first():
        raise HTTPException(status_code=409, detail="Release version already exists")
    release = CorpusRelease(version=body.version, parser_version="composite-v1")
    run = IngestionRun(
        created_by=current_user.id,
        status=IngestionRunStatus.QUEUED,
        current_stage=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
        pipeline_config={
            "composition_release_id": str(release.id),
            "auto_start_embedding": False,
        },
    )
    snapshot_entries = entry_snapshot(session, list(union.values()))
    release.source_manifest_hash = manifest_hash(snapshot_entries)
    composition = {
        "version": 1,
        "base_release_id": str(body.base_release_id),
        "run_id": str(run.id),
        "members": snapshots,
    }
    release.validation_report = {
        "composition": composition,
        "entry_count": len(union),
        "ingestion_run_ids": sorted(
            {
                str(entry.ingestion_run_id)
                for entry in union.values()
                if entry.ingestion_run_id
            }
        ),
        "source_document_ids": sorted(
            {str(entry.source_document_id) for entry in union.values()}
        ),
        "unresolved_gates": [
            "retrieval_documents_pending",
            "selected_embedding_run_missing",
            "ready_retrieval_index_build_missing"
            if settings.RETRIEVAL_INDEX_BACKEND == "pgvector"
            else "ready_vector_index_missing",
        ],
    }
    session.add_all([release, run])
    session.flush()
    for entry in union.values():
        session.add(
            CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=entry.provision_version_id,
                source_document_id=entry.source_document_id,
                ingestion_run_id=entry.ingestion_run_id,
            )
        )
    steps = create_run_steps(session, run, commit=False)
    for step in steps:
        if step.stage == IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS:
            break
        step.status = IngestionStepStatus.SKIPPED
        step.metrics = {
            "reason": "Reusing approved member releases; original ingestion provenance retained"
        }
        session.add(step)
    enqueue_task(
        session,
        run=run,
        step=step,
        task_type=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS.value,
        idempotency_key=f"{run.id}:building_retrieval_documents",
        payload={"release_id": str(release.id)},
        commit=False,
    )
    manifest = {
        "manifest_version": 2,
        "release_id": str(release.id),
        "release_version": release.version,
        "composition": composition,
        "entries": snapshot_entries,
        "source_document_ids": release.validation_report["source_document_ids"],
        "ingestion_run_ids": release.validation_report["ingestion_run_ids"],
        "source_documents": [
            {
                "id": str(source.id),
                "source_document_id": str(source.id),
                "title": source.title,
                "authority": source.authority,
                "source_url": source.source_url,
                "sha256": source.sha256,
                "page_count": source.page_count,
                "verification_status": str(source.verification_status),
            }
            for source in session.exec(
                select(SourceDocument)
                .where(
                    col(SourceDocument.id).in_(
                        {entry.source_document_id for entry in union.values()}
                    )
                )
                .order_by(col(SourceDocument.id))
            ).all()
        ],
    }
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST.value,
        filename=f"release-{release.version}.json",
        content=json.dumps(manifest, sort_keys=True).encode(),
        content_type="application/json",
    )
    session.add(
        IngestionArtifact(
            run_id=run.id,
            artifact_type=IngestionArtifactType.RELEASE_MANIFEST,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            artifact_metadata={
                "release_id": str(release.id),
                "source_manifest_hash": release.source_manifest_hash,
            },
        )
    )
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="corpus_release.compose",
            entity_type="corpus_release",
            entity_id=release.id,
            payload={
                "member_release_ids": [str(member.id) for member in members],
                "source_manifest_hash": release.source_manifest_hash,
            },
        )
    )
    append_run_event(
        session,
        run,
        event_type="release_composed",
        message="Composite retrieval build queued from approved member releases",
        payload={"release_id": str(release.id)},
        commit=False,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="corpus_release",
        result_id=release.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(release)
    return release


def validate_corpus_release(
    session: Session,
    release_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> CorpusRelease:
    scope = _idempotency_scope("corpus_release.validate", release_id)
    request_hash = _idempotency_payload_hash(
        {"expected_version": expected_version, "release_id": str(release_id)}
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_release(session, release_id)
    release = _get_release(session, release_id)
    _check_expected_version(release.lock_version, expected_version)
    entries = session.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    embedding_run = session.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.selected_for_release == True,  # noqa: E712
            EmbeddingRun.status == EmbeddingRunStatus.SUCCEEDED,
        )
    ).first()
    vector_index = None
    retrieval_index_build = None
    if embedding_run:
        if settings.RETRIEVAL_INDEX_BACKEND == "pgvector":
            retrieval_index_build = session.exec(
                select(RetrievalIndexBuild)
                .where(
                    RetrievalIndexBuild.release_id == release.id,
                    RetrievalIndexBuild.embedding_run_id == embedding_run.id,
                    RetrievalIndexBuild.status == VectorIndexStatus.READY,
                )
                .order_by(col(RetrievalIndexBuild.updated_at).desc())
            ).first()
        else:
            vector_index = session.exec(
                select(VectorIndex).where(
                    VectorIndex.release_id == release.id,
                    VectorIndex.embedding_run_id == embedding_run.id,
                    VectorIndex.status == VectorIndexStatus.READY,
                )
            ).first()
    unresolved_gates: list[str] = []
    benchmark_item_count: int | None = None
    if not entries:
        unresolved_gates.append("release_has_no_entries")
    unresolved_gates.extend(
        _release_source_and_review_gates(session, entries, release=release)
    )
    if not embedding_run:
        unresolved_gates.append("selected_embedding_run_missing")
    elif (
        embedding_run.recall_at_10 is None
        or embedding_run.recall_at_10 < MIN_PUBLICATION_RECALL_AT_10
    ):
        unresolved_gates.append("selected_embedding_run_below_recall_threshold")
    if embedding_run and not embedding_run.benchmark_dataset_version:
        unresolved_gates.append("benchmark_dataset_version_missing")
    elif embedding_run and embedding_run.benchmark_dataset_version:
        benchmark_item_count = active_evaluation_item_count(
            session,
            embedding_run.benchmark_dataset_version,
            dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
        )
        if benchmark_item_count <= 0:
            unresolved_gates.append("benchmark_dataset_missing_or_empty")
    if settings.RETRIEVAL_INDEX_BACKEND == "pgvector":
        if not retrieval_index_build:
            unresolved_gates.append("ready_retrieval_index_build_missing")
        else:
            unresolved_gates.extend(
                _retrieval_index_build_validation_gates(retrieval_index_build)
            )
    elif not vector_index:
        unresolved_gates.append("ready_vector_index_missing")
    else:
        unresolved_gates.extend(_vector_index_validation_gates(vector_index))

    release.validation_report = {
        **(release.validation_report or {}),
        "entry_count": len(entries),
        "selected_embedding_run_id": str(embedding_run.id) if embedding_run else None,
        "benchmark_dataset_version": (
            embedding_run.benchmark_dataset_version if embedding_run else None
        ),
        "benchmark_query_count": benchmark_item_count,
        "ready_vector_index_id": str(vector_index.id) if vector_index else None,
        "ready_retrieval_index_build_id": (
            str(retrieval_index_build.id) if retrieval_index_build else None
        ),
        "retrieval_backend": settings.RETRIEVAL_INDEX_BACKEND,
        "minimum_recall_at_10": MIN_PUBLICATION_RECALL_AT_10,
        "unresolved_gates": unresolved_gates,
    }
    release.status = (
        CorpusReleaseStatus.APPROVED
        if not unresolved_gates
        else CorpusReleaseStatus.VALIDATING
    )
    release.lock_version += 1
    session.add(release)
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="corpus_release",
        result_id=release.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(release)
    return release


def read_corpus_release_manifest(
    session: Session, release_id: uuid.UUID
) -> tuple[CorpusRelease, IngestionArtifact, dict[str, object]]:
    release = _get_release(session, release_id)
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.artifact_type == IngestionArtifactType.RELEASE_MANIFEST
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).all()
    artifact = next(
        (
            item
            for item in artifacts
            if str((item.artifact_metadata or {}).get("release_id")) == str(release.id)
        ),
        None,
    )
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Release manifest artifact was not found",
        )
    try:
        manifest = json.loads(get_blob_store().read_bytes(artifact.storage_key))
    except (BlobStoreError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Release manifest artifact could not be read",
        ) from exc
    if not isinstance(manifest, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Release manifest artifact is invalid",
        )
    return release, artifact, cast(dict[str, object], manifest)


def _release_source_and_review_gates(
    session: Session,
    entries: Sequence[CorpusReleaseEntry],
    *,
    release: CorpusRelease | None = None,
) -> list[str]:
    """Recheck mutable source/review state immediately before approval/publication."""
    gates: list[str] = composition_gates(session, release, entries) if release else []
    source_ids = {
        entry.source_document_id for entry in entries if entry.source_document_id
    }
    sources = (
        session.exec(
            select(SourceDocument).where(col(SourceDocument.id).in_(source_ids))
        ).all()
        if source_ids
        else []
    )
    if len(sources) != len(source_ids):
        gates.append("release_source_missing")
    if any(
        source.verification_status != VerificationStatus.VERIFIED for source in sources
    ):
        gates.append("release_source_not_verified")

    run_ids = {entry.ingestion_run_id for entry in entries if entry.ingestion_run_id}
    if not run_ids:
        return gates
    candidates = session.exec(
        select(ExtractionCandidate).where(col(ExtractionCandidate.run_id).in_(run_ids))
    ).all()
    if any(
        candidate.status
        not in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.AUTO_APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }
        for candidate in candidates
    ):
        gates.append("release_candidate_not_approved")
    candidate_ids = [candidate.id for candidate in candidates]
    if candidate_ids:
        blocking_issue = session.exec(
            select(ReviewIssue).where(
                col(ReviewIssue.candidate_id).in_(candidate_ids),
                ReviewIssue.blocking == True,  # noqa: E712
                ReviewIssue.status == ReviewIssueStatus.OPEN,
            )
        ).first()
        if blocking_issue:
            gates.append("release_blocking_review_issue_open")
    return gates


def read_corpus_release_publication_evidence(
    session: Session, release_id: uuid.UUID
) -> tuple[
    CorpusRelease,
    list[VectorIndex],
    list[RetrievalIndexBuild],
    list[ReleasePromotionAttempt],
    list[uuid.UUID],
    list[AuditEvent],
    list[ActiveRetrievalTarget],
]:
    release = _get_release(session, release_id)
    vector_indexes = list(
        session.exec(
            select(VectorIndex)
            .where(VectorIndex.release_id == release.id)
            .order_by(col(VectorIndex.updated_at).desc())
        ).all()
    )
    retrieval_index_builds = list(
        session.exec(
            select(RetrievalIndexBuild)
            .where(RetrievalIndexBuild.release_id == release.id)
            .order_by(col(RetrievalIndexBuild.updated_at).desc())
        ).all()
    )
    promotion_attempts = list(
        session.exec(
            select(ReleasePromotionAttempt)
            .where(ReleasePromotionAttempt.release_id == release.id)
            .order_by(col(ReleasePromotionAttempt.created_at).desc())
        ).all()
    )
    release_entries = list(
        session.exec(
            select(CorpusReleaseEntry).where(
                CorpusReleaseEntry.release_id == release.id
            )
        ).all()
    )
    source_ids = [
        entry.source_document_id
        for entry in release_entries
        if entry.source_document_id
    ]
    sources = (
        list(
            session.exec(
                select(SourceDocument).where(col(SourceDocument.id).in_(source_ids))
            ).all()
        )
        if source_ids
        else []
    )
    source_uploader_ids = sorted(
        {source.created_by for source in sources if source.created_by},
        key=str,
    )
    override_events = list(
        session.exec(
            select(AuditEvent)
            .where(
                AuditEvent.action == "corpus_release.publish_override",
                AuditEvent.entity_id == release.id,
            )
            .order_by(col(AuditEvent.created_at).desc())
        ).all()
    )
    active_targets = list(
        session.exec(
            select(ActiveRetrievalTarget)
            .where(ActiveRetrievalTarget.release_id == release.id)
            .order_by(ActiveRetrievalTarget.index_kind)
        ).all()
    )
    return (
        release,
        vector_indexes,
        retrieval_index_builds,
        promotion_attempts,
        source_uploader_ids,
        override_events,
        active_targets,
    )


def publish_corpus_release(
    session: Session,
    release_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
    superuser_override_reason: str | None,
) -> tuple[CorpusRelease, ReleasePromotionAttempt]:
    current_user_id = current_user.id
    scope = _idempotency_scope("corpus_release.publish", release_id)
    request_hash = _idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "release_id": str(release_id),
            "superuser_override_reason": superuser_override_reason,
        }
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        release = _get_release(session, release_id)
        promotion = (
            session.get(ReleasePromotionAttempt, record.result_id)
            if record.result_id
            else None
        )
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent publication result is no longer available",
            )
        return release, promotion
    release = _get_release(session, release_id)
    _check_expected_version(release.lock_version, expected_version)
    if release.status != CorpusReleaseStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Release must validate cleanly before publication",
        )
    entries = session.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    quality_gates = _release_source_and_review_gates(session, entries, release=release)
    if quality_gates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Release source/review gates no longer pass",
                "gates": quality_gates,
            },
        )
    vector_index = None
    if settings.RETRIEVAL_INDEX_BACKEND == "pgvector":
        if not _ready_retrieval_index_build(session, release.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Release does not have a ready pgvector index build",
            )
    else:
        vector_index = _ready_vector_index(session, release.id)
        if not vector_index:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Release does not have a ready vector index",
            )
    _enforce_actor_separation(
        session,
        release,
        current_user,
        superuser_override_reason=superuser_override_reason,
    )
    if settings.RETRIEVAL_INDEX_BACKEND == "pgvector":
        return _publish_pgvector_release(
            session,
            release_id=release_id,
            expected_version=expected_version,
            current_user=current_user,
            idempotency_scope=scope,
            idempotency_key=idempotency_key,
            idempotency_request_hash=request_hash,
        )

    assert vector_index is not None
    previous_release = session.exec(
        select(CorpusRelease).where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION
        )
    ).first()
    promotion = ReleasePromotionAttempt(
        release_id=release.id,
        vector_index_id=vector_index.id,
        requested_by=current_user_id,
        status=ReleasePromotionStatus.PUBLISHING,
        previous_release_id=previous_release.id if previous_release else None,
        previous_collection_name=_production_collection_name(session, previous_release),
        target_collection_name=vector_index.collection_name,
        started_at=get_datetime_utc(),
    )
    session.add(promotion)
    session.commit()
    try:
        _switch_qdrant_alias(
            alias_name=vector_index.alias_name,
            new_collection_name=vector_index.collection_name,
            old_collection_name=promotion.previous_collection_name,
        )
    except Exception as exc:
        _record_promotion_failure(
            session,
            promotion_id=promotion.id,
            promotion_status=ReleasePromotionStatus.FAILED,
            error_details={
                "phase": "qdrant_alias_switch",
                "error": str(exc),
            },
            rollback_completed=False,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Qdrant alias switch failed; production release was not changed",
        )

    try:
        _mark_release_production_in_db(
            session,
            previous_release=previous_release,
            release=release,
            vector_index=vector_index,
            promotion=promotion,
            current_user_id=current_user_id,
            idempotency_scope=scope,
            idempotency_key=idempotency_key,
            idempotency_request_hash=request_hash,
        )
    except Exception as exc:
        session.rollback()
        rollback_completed, rollback_error = _rollback_qdrant_alias(
            alias_name=vector_index.alias_name,
            target_collection_name=vector_index.collection_name,
            previous_collection_name=promotion.previous_collection_name,
        )
        _record_promotion_failure(
            session,
            promotion_id=promotion.id,
            promotion_status=ReleasePromotionStatus.ROLLED_BACK
            if rollback_completed
            else ReleasePromotionStatus.FAILED,
            error_details={
                "phase": "database_promotion",
                "error": str(exc),
                "rollback_error": rollback_error,
            },
            rollback_completed=rollback_completed,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Publication database update failed after Qdrant alias switch",
        )
    session.refresh(release)
    session.refresh(promotion)
    return release, promotion


def user_has_admin_role(session: Session, user: User, role: AdminRole) -> bool:
    if user.is_superuser:
        return True
    assignment = session.exec(
        select(AdminRoleAssignment).where(
            AdminRoleAssignment.user_id == user.id,
            AdminRoleAssignment.role == role,
            AdminRoleAssignment.revoked_at == None,  # noqa: E711
        )
    ).first()
    return assignment is not None


def require_admin_role(session: Session, user: User, role: AdminRole) -> None:
    if user_has_admin_role(session, user, role):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The user does not have the required admin role",
    )


def cancel_ingestion_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
    reason: str,
) -> IngestionRun:
    scope = _idempotency_scope("ingestion_run.cancel", run_id)
    request_hash = _idempotency_payload_hash(
        {"expected_version": expected_version, "reason": reason, "run_id": str(run_id)}
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_run(session, run_id)
    run = _get_run(session, run_id)
    _check_expected_version(run.lock_version, expected_version)
    if run.status in {IngestionRunStatus.PUBLISHED, IngestionRunStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminal ingestion runs cannot be cancelled",
        )
    cancelled = mark_run_cancelled(session, run, reason)
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=cancelled.id,
        created_by=current_user.id,
    )
    session.commit()
    return cancelled


def resume_ingestion_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> IngestionRun:
    scope = _idempotency_scope("ingestion_run.resume", run_id)
    request_hash = _idempotency_payload_hash(
        {"expected_version": expected_version, "run_id": str(run_id)}
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_run(session, run_id)
    run = _get_run(session, run_id)
    _check_expected_version(run.lock_version, expected_version)
    if run.status not in {
        IngestionRunStatus.WAITING_FOR_INPUT,
        IngestionRunStatus.WAITING_FOR_REVIEW,
        IngestionRunStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only waiting or cancelled ingestion runs can be resumed",
        )
    was_cancelled = run.status == IngestionRunStatus.CANCELLED
    resume_stage = IngestionStage(_enum_value(run.current_stage))
    is_page_confirmation = resume_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    if not was_cancelled:
        append_run_event(
            session,
            run,
            event_type="run_resume_not_required",
            message="Ingestion run is already awaiting operator input",
            stage=resume_stage,
        )
        _add_idempotency_record(
            session,
            scope=scope,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            result_type="ingestion_run",
            result_id=run.id,
            created_by=current_user.id,
        )
        session.commit()
        session.refresh(run)
        return run

    run.status = (
        IngestionRunStatus.WAITING_FOR_INPUT
        if is_page_confirmation
        else IngestionRunStatus.QUEUED
    )
    run.completed_at = None
    run.error_details = None
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add(run)
    resume_step = _get_run_step(session, run.id, resume_stage)
    resume_step.status = (
        IngestionStepStatus.BLOCKED
        if is_page_confirmation
        else IngestionStepStatus.PENDING
    )
    resume_step.lease_owner = None
    resume_step.leased_until = None
    resume_step.heartbeat_at = None
    resume_step.started_at = None
    resume_step.completed_at = None
    resume_step.error_details = None
    resume_step.lock_version += 1
    resume_step.updated_at = run.updated_at
    session.add(resume_step)
    session.commit()
    if not is_page_confirmation:
        payload: dict[str, object] = {"resume": True}
        if run.source_document_id:
            payload["source_document_id"] = str(run.source_document_id)
        enqueue_task(
            session,
            run=run,
            step=resume_step,
            task_type=resume_stage.value,
            idempotency_key=(
                f"{run.id}:{resume_stage.value}:resume:{run.lock_version}"
            ),
            payload=payload,
            priority=5,
        )
    append_run_event(
        session,
        run,
        event_type="run_resumed",
        message="Ingestion run resumed",
        stage=resume_stage,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=run.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(run)
    return run


def start_embedding(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> IngestionRun:
    """Atomically move a release from the human pause into embedding."""
    scope = _idempotency_scope("ingestion_run.start_embedding", run_id)
    request_hash = _idempotency_payload_hash(
        {"expected_version": expected_version, "run_id": str(run_id)}
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_run(session, run_id)
    run = _get_run(session, run_id)
    _check_expected_version(run.lock_version, expected_version)
    if run.status != IngestionRunStatus.READY_TO_EMBED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only runs ready to embed can start embedding",
        )
    profiles = session.exec(
        select(EmbeddingProfile).where(col(EmbeddingProfile.is_active).is_(True))
    ).all()
    if not profiles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least one active embedding profile is required",
        )
    if any(
        profile.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS
        or not profile.model_revision
        for profile in profiles
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active embedding profiles must use 1,024 dimensions and pinned revisions",
        )
    release_id = _release_id_for_run(session, run)
    release = _get_release(session, release_id)
    if (release.validation_report or {}).get("composition") is not None:
        gates = _release_source_and_review_gates(
            session, release_entries(session, release.id), release=release
        )
        if gates:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Composite member gates must pass before embedding",
                    "gates": gates,
                },
            )
    step = _get_run_step(session, run.id, IngestionStage.EMBEDDING)
    step.status = IngestionStepStatus.PENDING
    step.lock_version += 1
    step.updated_at = get_datetime_utc()
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = IngestionStage.EMBEDDING
    run.lock_version += 1
    run.updated_at = get_datetime_utc()
    session.add_all([run, step])
    session.commit()
    enqueue_task(
        session,
        run=run,
        step=step,
        task_type=IngestionStage.EMBEDDING.value,
        idempotency_key=f"{run.id}:{IngestionStage.EMBEDDING.value}:manual",
        payload={
            "source_document_id": str(run.source_document_id),
            "release_id": str(release_id),
        },
        priority=40,
    )
    append_run_event(
        session,
        run,
        event_type="embedding_started",
        message="Embedding benchmark and indexing queued",
        stage=IngestionStage.EMBEDDING,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=run.id,
        created_by=current_user.id,
    )
    session.commit()
    return run


def retry_ingestion_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
) -> IngestionRun:
    scope = _idempotency_scope("ingestion_run.retry", run_id)
    request_hash = _idempotency_payload_hash(
        {"expected_version": expected_version, "run_id": str(run_id)}
    )
    record = _idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return _get_run(session, run_id)
    run = _get_run(session, run_id)
    _check_expected_version(run.lock_version, expected_version)
    if run.status != IngestionRunStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed ingestion runs can be retried",
        )
    run.status = IngestionRunStatus.QUEUED
    run.lock_version += 1
    run.error_details = None
    run.updated_at = get_datetime_utc()
    session.add(run)
    stage_value = _enum_value(run.current_stage)
    task = IngestionTask(
        run_id=run.id,
        task_type=stage_value,
        status=IngestionTaskStatus.PENDING,
        idempotency_key=f"{run.id}:{stage_value}:retry:{run.lock_version}",
        payload={"retry": True},
        priority=5,
    )
    session.add(task)
    session.commit()
    append_run_event(
        session,
        run,
        event_type="run_retried",
        message="Failed ingestion run queued for retry",
        stage=run.current_stage,
    )
    _add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="ingestion_run",
        result_id=run.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(run)
    return run


def latest_revision_text(
    session: Session, candidate: ExtractionCandidate
) -> str | None:
    revision = _latest_candidate_revision(session, candidate.id)
    return revision.revised_text if revision else None


def release_entry_count(session: Session, release_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(CorpusReleaseEntry)
        .where(CorpusReleaseEntry.release_id == release_id)
    ).one()


def _idempotency_scope(operation: str, entity_id: uuid.UUID) -> str:
    return f"{operation}:{entity_id}"


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _alert_time(fallback: datetime, *values: datetime | None) -> datetime:
    for value in values:
        if value is not None:
            return value
    return fallback


def _alert_error_message(
    error_details: dict[str, object] | None,
    fallback: str,
) -> str:
    if not error_details:
        return fallback
    for key in ("message", "error", "detail", "reason"):
        value = error_details.get(key)
        if isinstance(value, str) and value.strip():
            return value
    code = error_details.get("code")
    if isinstance(code, str) and code.strip():
        return f"{fallback} ({code})"
    return fallback


def _idempotency_request_hash(body: object) -> str:
    model_dump = getattr(body, "model_dump", None)
    if callable(model_dump):
        return _idempotency_payload_hash(model_dump(mode="json"))
    return _idempotency_payload_hash(body)


def _idempotency_payload_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _idempotency_record_for_request(
    session: Session,
    *,
    scope: str,
    idempotency_key: str,
    request_hash: str,
) -> IdempotencyRecord | None:
    record = session.exec(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    ).first()
    if not record:
        return None
    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different request",
        )
    return record


def _add_idempotency_record(
    session: Session,
    *,
    scope: str,
    idempotency_key: str,
    request_hash: str,
    result_type: str,
    result_id: uuid.UUID | None,
    created_by: uuid.UUID | None,
    result_payload: dict[str, object] | None = None,
) -> None:
    session.add(
        IdempotencyRecord(
            scope=scope,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            result_type=result_type,
            result_id=result_id,
            result_payload=result_payload,
            created_by=created_by,
        )
    )


def _idempotency_result_payload(record: IdempotencyRecord) -> dict[str, object]:
    payload = record.result_payload
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent mutation result is no longer available",
        )
    return cast(dict[str, object], payload)


def _multipart_upload_from_idempotency_record(
    record: IdempotencyRecord,
) -> MultipartUpload:
    payload = _idempotency_result_payload(record)
    parts_payload = payload.get("parts")
    if not isinstance(parts_payload, list):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent multipart result is no longer available",
        )
    parts: list[MultipartUploadPartUrl] = []
    for item in parts_payload:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent multipart result is no longer available",
            )
        part_number = item.get("part_number")
        upload_url = item.get("upload_url")
        if not isinstance(part_number, int) or not isinstance(upload_url, str):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent multipart result is no longer available",
            )
        parts.append(
            MultipartUploadPartUrl(part_number=part_number, upload_url=upload_url)
        )
    upload_id = payload.get("multipart_upload_id")
    if not isinstance(upload_id, str):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent multipart result is no longer available",
        )
    return MultipartUpload(upload_id=upload_id, parts=tuple(parts))


def _completed_upload_from_idempotency_record(
    session: Session, record: IdempotencyRecord
) -> tuple[SourceUpload, SourceDocument | None, IngestionRun | None, bool]:
    payload = _idempotency_result_payload(record)
    upload_id = payload.get("upload_id")
    if not isinstance(upload_id, str):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent upload completion result is no longer available",
        )
    upload = session.get(SourceUpload, uuid.UUID(upload_id))
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent upload completion result is no longer available",
        )
    source = None
    source_id = payload.get("source_document_id")
    if isinstance(source_id, str):
        source = session.get(SourceDocument, uuid.UUID(source_id))
        if not source:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent upload completion result is no longer available",
            )
    run = None
    run_id = payload.get("run_id")
    if isinstance(run_id, str):
        run = session.get(IngestionRun, uuid.UUID(run_id))
        if not run:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent upload completion result is no longer available",
            )
    return upload, source, run, bool(payload.get("duplicate"))


def _pages_for_idempotency_record(
    session: Session, record: IdempotencyRecord
) -> list[SourcePage]:
    payload = _idempotency_result_payload(record)
    run_id = payload.get("run_id")
    page_numbers = payload.get("page_numbers")
    if not isinstance(run_id, str) or not isinstance(page_numbers, list):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent page-selection result is no longer available",
        )
    numbers = [number for number in page_numbers if isinstance(number, int)]
    if not numbers:
        return []
    pages = session.exec(
        select(SourcePage)
        .where(
            SourcePage.run_id == uuid.UUID(run_id),
            col(SourcePage.page_number).in_(numbers),
        )
        .order_by(col(SourcePage.page_number))
    ).all()
    if len(pages) != len(numbers):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent page-selection result is no longer available",
        )
    return list(pages)


def _get_upload(session: Session, upload_id: uuid.UUID) -> SourceUpload:
    upload = session.get(SourceUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Source upload not found")
    return upload


def _get_run(session: Session, run_id: uuid.UUID) -> IngestionRun:
    run = session.get(IngestionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return run


def _release_id_for_run(session: Session, run: IngestionRun) -> uuid.UUID:
    composed_id = (run.pipeline_config or {}).get("composition_release_id")
    if composed_id:
        release = _get_release(session, uuid.UUID(str(composed_id)))
        if ((release.validation_report or {}).get("composition") or {}).get(
            "run_id"
        ) != str(run.id):
            raise HTTPException(
                status_code=409,
                detail="Composite run identity differs from its release",
            )
        return release.id
    original = session.exec(
        select(CorpusRelease).where(CorpusRelease.version == f"draft-{run.id.hex[:12]}")
    ).first()
    if original:
        return original.id
    release_ids = session.exec(
        select(CorpusReleaseEntry.release_id)
        .where(CorpusReleaseEntry.ingestion_run_id == run.id)
        .distinct()
    ).all()
    originals = [
        item
        for release_id in release_ids
        if (item := session.get(CorpusRelease, release_id))
        and not (item.validation_report or {}).get("composition")
    ]
    if len(originals) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingestion run does not identify a single original corpus release",
        )
    return originals[0].id


def _get_source_document(
    session: Session, source_document_id: uuid.UUID
) -> SourceDocument:
    source = session.get(SourceDocument, source_document_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source document not found")
    return source


def _get_run_step(
    session: Session, run_id: uuid.UUID, stage: IngestionStage
) -> IngestionStep:
    step = session.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run_id,
            IngestionStep.stage == stage,
        )
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail=f"{stage.value} step not found")
    return step


def _get_candidate(session: Session, candidate_id: uuid.UUID) -> ExtractionCandidate:
    candidate = session.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.id == candidate_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Review item not found")
    return candidate


def _get_release(session: Session, release_id: uuid.UUID) -> CorpusRelease:
    release = session.get(CorpusRelease, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Corpus release not found")
    return release


def _check_expected_version(actual_version: int, expected_version: int) -> None:
    if actual_version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The record was modified by another operation",
        )


def _mark_upload_failed(
    session: Session, upload: SourceUpload, error_message: str
) -> None:
    upload.status = SourceUploadStatus.FAILED
    upload.error_message = error_message
    upload.lock_version += 1
    upload.updated_at = get_datetime_utc()
    session.add(upload)
    session.commit()


def _validate_pdf(content: bytes) -> int:
    try:
        return inspect_pdf_bytes(content, max_pages=MAX_SOURCE_PAGES).page_count
    except PdfInspectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


def _ensure_allowed_instrument_type(instrument_type: InstrumentType) -> None:
    if str(instrument_type) not in settings.INGESTION_ALLOWED_INSTRUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Ingestion is disabled for instrument type: {instrument_type}",
        )


def _get_or_create_instrument(
    session: Session, upload: SourceUpload
) -> LegalInstrument:
    _ensure_allowed_instrument_type(upload.instrument_type)
    instrument = session.exec(
        select(LegalInstrument).where(LegalInstrument.slug == upload.instrument_slug)
    ).first()
    if instrument:
        if instrument.instrument_type != upload.instrument_type:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Instrument slug already belongs to a different instrument type",
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


def finalize_verified_upload(
    session: Session,
    *,
    run: IngestionRun,
    upload: SourceUpload,
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
        _ensure_allowed_instrument_type(upload.instrument_type)
        get_blob_store().delete_quarantine(upload.quarantine_key)
        source = existing_source
        upload.status = SourceUploadStatus.DUPLICATE
        upload.canonical_key = source.storage_key
    else:
        store = get_blob_store()
        original = store.promote_quarantine_to_original(
            quarantine_key=upload.quarantine_key,
            expected_sha256=sha256,
            content_type=upload.mime_type,
            extension=Path(upload.original_filename).suffix or ".pdf",
            metadata={
                "source_upload_id": str(upload.id),
                "source_url": upload.source_url,
            },
        )
        instrument = _get_or_create_instrument(session, upload)
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
    session.refresh(source)
    return source


def _latest_candidate_revision(
    session: Session, candidate_id: uuid.UUID
) -> CandidateRevision | None:
    return session.exec(
        select(CandidateRevision)
        .where(CandidateRevision.candidate_id == candidate_id)
        .order_by(col(CandidateRevision.revision_number).desc())
    ).first()


def _line_diff(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
        )
    )


def _candidate_snapshot(
    candidate: ExtractionCandidate, revised_text: str | None
) -> dict[str, object]:
    return {
        "heading": candidate.heading,
        "kind": str(candidate.kind),
        "number": candidate.number,
        "parent_candidate_id": (
            str(candidate.parent_candidate_id)
            if candidate.parent_candidate_id
            else None
        ),
        "canonical_path": candidate.canonical_path,
        "sort_key": candidate.sort_key,
        "source_page_start": candidate.source_page_start,
        "source_page_end": candidate.source_page_end,
        "source_spans": candidate.source_spans,
        "revised_text": revised_text,
    }


def _has_open_blocking_issue(session: Session, candidate_id: uuid.UUID) -> bool:
    issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate_id,
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    return issue is not None


def _revalidate_candidate_revision_text(
    session: Session,
    *,
    candidate: ExtractionCandidate,
    revised_text: str,
    current_user: User,
) -> None:
    run = session.get(IngestionRun, candidate.run_id)
    if (
        run
        and (run.pipeline_config or {}).get("review_import_complete")
        and not (run.pipeline_config or {}).get("provisional_page_boundaries", True)
    ):
        included = set(
            session.exec(
                select(SourcePage.page_number).where(
                    SourcePage.run_id == candidate.run_id,
                    SourcePage.inclusion_status == PageInclusionStatus.INCLUDED,
                )
            ).all()
        )
        _revalidate_review_page_coverage(session, candidate, included, current_user)
    open_revision_issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "revision_unbalanced_punctuation",
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    open_extraction_issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "unbalanced_punctuation",
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    if has_unbalanced_punctuation(revised_text):
        if open_extraction_issue and open_revision_issue:
            open_revision_issue.status = ReviewIssueStatus.RESOLVED
            open_revision_issue.resolved_by = current_user.id
            open_revision_issue.resolved_at = get_datetime_utc()
            open_revision_issue.resolution_reason = "Duplicate punctuation finding; the extraction-time blocker remains open."
            open_revision_issue.resolution_evidence = {
                "duplicate_of": str(open_extraction_issue.id),
                "revision_number": candidate.revision_number,
            }
            session.add(open_revision_issue)
        elif not open_revision_issue and not open_extraction_issue:
            session.add(
                ReviewIssue(
                    candidate_id=candidate.id,
                    issue_type="revision_unbalanced_punctuation",
                    severity=ReviewIssueSeverity.BLOCKING,
                    status=ReviewIssueStatus.OPEN,
                    blocking=True,
                    message="Revised candidate text has unbalanced punctuation.",
                    evidence={"canonical_path": candidate.canonical_path},
                )
            )
    # Revalidate the current revision, including extraction-time findings.
    # Exact source-character agreement can clear an obsolete coverage finding
    # without waiving the provenance gate or changing the immutable raw text.
    compact_revision, _ = compact_text(revised_text)
    source_text = "\n".join(
        str(span.get("text") or "") for span in candidate.source_spans or []
    )
    spans_have_coordinates = bool(candidate.source_spans) and all(
        all(key in (span.get("bbox") or {}) for key in ("x0", "y0", "x1", "y1"))
        for span in candidate.source_spans or []
    )
    exact_source_match = (
        bool(compact_revision)
        and spans_have_coordinates
        and (compact_revision == compact_text(source_text)[0])
    )
    for issue in session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).all():
        repaired_punctuation = issue.issue_type in {
            "unbalanced_punctuation",
            "revision_unbalanced_punctuation",
        } and not has_unbalanced_punctuation(revised_text)
        repaired_coverage = (
            issue.issue_type in {"missing_source_spans", "source_span_coverage"}
            and exact_source_match
        )
        if repaired_punctuation or repaired_coverage:
            issue.status = ReviewIssueStatus.RESOLVED
            issue.resolved_by = current_user.id
            issue.resolved_at = get_datetime_utc()
            issue.resolution_reason = (
                "Finding cleared by candidate revision revalidation."
            )
            issue.resolution_evidence = {
                "revision_number": candidate.revision_number,
                "exact_source_character_match": exact_source_match,
                "punctuation_balanced": not has_unbalanced_punctuation(revised_text),
            }
            session.add(issue)
    session.flush()
    candidate.blocking_issue_count = _open_blocking_issue_count(session, candidate.id)
    session.add(candidate)


def _open_blocking_issue_count(session: Session, candidate_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(ReviewIssue)
        .where(
            ReviewIssue.candidate_id == candidate_id,
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).one()


def _revalidate_review_page_coverage(
    session: Session,
    candidate: ExtractionCandidate,
    included: set[int],
    current_user: User,
) -> None:
    pages: set[int | None] = set(
        range(
            candidate.source_page_start or 1,
            (candidate.source_page_end or candidate.source_page_start or 1) + 1,
        )
    )
    for span in candidate.source_spans or []:
        page = span.get("page_number", span.get("page"))
        pages.add(
            page if isinstance(page, int) and not isinstance(page, bool) else None
        )
    invalid = pages - included
    issue = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "excluded_source_page",
        )
    ).first()
    if invalid:
        if issue is None:
            issue = ReviewIssue(
                candidate_id=candidate.id,
                issue_type="excluded_source_page",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate source mapping includes excluded or unknown pages.",
            )
        issue.status = ReviewIssueStatus.OPEN
        issue.evidence = {
            "excluded_or_unknown_pages": sorted(str(page) for page in invalid)
        }
        issue.resolved_by = None
        issue.resolved_at = None
        session.add(issue)
    elif issue and issue.status == ReviewIssueStatus.OPEN:
        issue.status = ReviewIssueStatus.RESOLVED
        issue.resolved_by = current_user.id
        issue.resolved_at = get_datetime_utc()
        issue.resolution_reason = (
            "Current candidate mapping uses only confirmed included source pages."
        )
        issue.resolution_evidence = {"revision_number": candidate.revision_number}
        session.add(issue)


def _candidate_status_for_decision(
    decision: ReviewDecisionType,
) -> ExtractionCandidateStatus:
    if decision == ReviewDecisionType.APPROVE:
        return ExtractionCandidateStatus.APPROVED
    if decision == ReviewDecisionType.REJECT:
        return ExtractionCandidateStatus.REJECTED
    return ExtractionCandidateStatus.NEEDS_CORRECTION


def _maybe_complete_review_and_queue_materialization(
    session: Session,
    *,
    candidate: ExtractionCandidate,
) -> None:
    run = session.get(IngestionRun, candidate.run_id)
    if not run or not (
        run.current_stage == IngestionStage.REVIEW
        or run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    ):
        return
    # Approval is often performed in batches. Avoid loading every candidate's
    # text and spans after each decision while any review remains unfinished.
    unfinished = session.exec(
        select(ExtractionCandidate.id).where(
            ExtractionCandidate.run_id == run.id,
            col(ExtractionCandidate.status).not_in(
                [
                    ExtractionCandidateStatus.APPROVED,
                    ExtractionCandidateStatus.AUTO_APPROVED,
                    ExtractionCandidateStatus.MATERIALIZED,
                    ExtractionCandidateStatus.REJECTED,
                ]
            ),
        )
    ).first()
    if unfinished:
        return
    candidates = _live_review_candidates(session, run.id)
    if not _review_candidates_ready_for_materialization(session, candidates):
        return

    source = session.get(SourceDocument, candidate.source_document_id)
    if not source or source.verification_status != VerificationStatus.VERIFIED:
        _mark_review_waiting_for_source_verification(
            session, run=run, source=source, candidates=candidates
        )
        return

    _complete_review_and_queue_materialization(
        session, run=run, source=source, candidates=candidates
    )


def _queue_materialization_for_verified_source(
    session: Session,
    *,
    source: SourceDocument,
) -> None:
    runs = session.exec(
        select(IngestionRun).where(
            IngestionRun.source_document_id == source.id,
            IngestionRun.status == IngestionRunStatus.WAITING_FOR_REVIEW,
            IngestionRun.current_stage == IngestionStage.REVIEW,
        )
    ).all()
    for run in runs:
        candidates = _live_review_candidates(session, run.id)
        if _review_candidates_ready_for_materialization(session, candidates):
            _complete_review_and_queue_materialization(
                session, run=run, source=source, candidates=candidates
            )


def _live_review_candidates(
    session: Session, run_id: uuid.UUID
) -> list[ExtractionCandidate]:
    # Rejected candidates (duplicate scans, junk fragments) are a final review
    # decision: they are never materialized and their findings do not block.
    return list(
        session.exec(
            select(ExtractionCandidate).where(
                ExtractionCandidate.run_id == run_id,
                ExtractionCandidate.status != ExtractionCandidateStatus.REJECTED,
            )
        ).all()
    )


def _review_candidates_ready_for_materialization(
    session: Session, candidates: Sequence[ExtractionCandidate]
) -> bool:
    if not candidates:
        return False
    if any(
        item.status
        not in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.AUTO_APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }
        for item in candidates
    ):
        return False
    candidate_ids = [item.id for item in candidates]
    unresolved_blocking_issue = session.exec(
        select(ReviewIssue).where(
            col(ReviewIssue.candidate_id).in_(candidate_ids),
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    return unresolved_blocking_issue is None


def _mark_review_waiting_for_source_verification(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument | None,
    candidates: Sequence[ExtractionCandidate],
) -> None:
    now = get_datetime_utc()
    review_step = _get_run_step(session, run.id, IngestionStage.REVIEW)
    review_step.status = IngestionStepStatus.BLOCKED
    review_step.metrics = {
        "candidate_count": len(candidates),
        "source_verification_required": True,
    }
    review_step.updated_at = now
    review_step.lock_version += 1
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    run.updated_at = now
    session.add(review_step)
    session.add(run)
    existing_event = session.exec(
        select(IngestionEvent).where(
            IngestionEvent.run_id == run.id,
            IngestionEvent.event_type == "source_verification_required",
        )
    ).first()
    if existing_event:
        session.commit()
        return
    append_run_event(
        session,
        run,
        event_type="source_verification_required",
        message="Document-level source verification is required before materialization",
        stage=IngestionStage.REVIEW,
        payload={
            "candidate_count": len(candidates),
            "source_document_id": str(source.id) if source else None,
        },
    )


def _complete_review_and_queue_materialization(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    candidates: Sequence[ExtractionCandidate],
) -> None:
    now = get_datetime_utc()
    review_step = _get_run_step(session, run.id, IngestionStage.REVIEW)
    review_step.status = IngestionStepStatus.SUCCEEDED
    review_step.completed_units = len(candidates)
    review_step.completed_at = now
    review_step.updated_at = now
    review_step.lock_version += 1
    session.add(review_step)

    materializing_step = _get_run_step(session, run.id, IngestionStage.MATERIALIZING)
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = IngestionStage.MATERIALIZING
    run.lock_version += 1
    run.updated_at = now
    session.add(run)
    session.commit()
    enqueue_task(
        session,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:{IngestionStage.MATERIALIZING.value}",
        payload={"source_document_id": str(source.id)},
        priority=50,
    )
    append_run_event(
        session,
        run,
        event_type="review_completed",
        message="Review approved; materialization queued",
        step=review_step,
        payload={"candidate_count": len(candidates)},
    )


def _ready_vector_index(session: Session, release_id: uuid.UUID) -> VectorIndex | None:
    indexes = session.exec(
        select(VectorIndex).where(
            VectorIndex.release_id == release_id,
            VectorIndex.status == VectorIndexStatus.READY,
        )
    ).all()
    for index in indexes:
        if not _vector_index_validation_gates(index):
            return index
    return None


def _ready_retrieval_index_build(
    session: Session, release_id: uuid.UUID
) -> RetrievalIndexBuild | None:
    builds = session.exec(
        select(RetrievalIndexBuild)
        .where(
            RetrievalIndexBuild.release_id == release_id,
            RetrievalIndexBuild.status == VectorIndexStatus.READY,
        )
        .order_by(col(RetrievalIndexBuild.updated_at).desc())
    ).all()
    for build in builds:
        if not _retrieval_index_build_validation_gates(build):
            return build
    return None


def _retrieval_index_build_validation_gates(
    build: RetrievalIndexBuild,
) -> list[str]:
    gates: list[str] = []
    report = build.validation_report or {}
    if build.backend != "pgvector":
        gates.append("retrieval_index_backend_mismatch")
    if build.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        gates.append("retrieval_index_vector_dimensions_mismatch")
    if build.expected_segment_count <= 0:
        gates.append("retrieval_index_has_no_expected_segments")
    if build.stored_segment_count != build.expected_segment_count:
        gates.append("retrieval_index_segment_count_mismatch")
    if build.stored_embedding_count != build.expected_segment_count:
        gates.append("retrieval_index_embedding_count_mismatch")
    if not build.profile_hash:
        gates.append("retrieval_index_profile_hash_missing")
    if not build.checksum:
        gates.append("retrieval_index_checksum_missing")
    if report.get("is_valid") is not True:
        gates.append("retrieval_index_local_validation_missing")
    if report.get("vector_dimensions") != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        gates.append("retrieval_index_report_dimensions_mismatch")
    if report.get("lexical_smoke_query_supported") is not True:
        gates.append("retrieval_index_lexical_validation_missing")
    return gates


def _publish_pgvector_release(
    session: Session,
    *,
    release_id: uuid.UUID,
    expected_version: int,
    current_user: User,
    idempotency_scope: str,
    idempotency_key: str,
    idempotency_request_hash: str,
) -> tuple[CorpusRelease, ReleasePromotionAttempt]:
    """Atomically promote a validated pgvector build and its active target."""
    release = session.exec(
        select(CorpusRelease).where(CorpusRelease.id == release_id).with_for_update()
    ).one()
    _check_expected_version(release.lock_version, expected_version)
    build = _ready_retrieval_index_build(session, release.id)
    if build is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Release does not have a ready pgvector index build",
        )
    report = validate_index_build(
        session,
        build=build,
        expected_segment_count=build.expected_segment_count,
    )
    build.validation_report = report
    if not report["is_valid"] or _retrieval_index_build_validation_gates(build):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="pgvector index validation no longer passes",
        )
    index_kind = build.index_kind
    target = session.exec(
        select(ActiveRetrievalTarget)
        .where(ActiveRetrievalTarget.index_kind == index_kind)
        .with_for_update()
    ).first()
    # During the expand/migrate period a production release may have been
    # published by the legacy backend without an active pgvector target. Lock
    # the canonical production row as well so the single-production invariant
    # is preserved across the backend cutover.
    previous_release = session.exec(
        select(CorpusRelease)
        .where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION,
            CorpusRelease.id != release.id,
        )
        .with_for_update()
    ).first()
    if previous_release is None and target is not None:
        target_release = session.get(CorpusRelease, target.release_id)
        if target_release is not None and target_release.id != release.id:
            previous_release = target_release
    now = get_datetime_utc()
    promotion = ReleasePromotionAttempt(
        release_id=release.id,
        retrieval_index_build_id=build.id,
        index_kind=index_kind,
        requested_by=current_user.id,
        status=ReleasePromotionStatus.PUBLISHING,
        previous_release_id=previous_release.id if previous_release else None,
        started_at=now,
    )
    session.add(promotion)
    session.flush()
    if target is None:
        target = ActiveRetrievalTarget(
            index_kind=index_kind,
            release_id=release.id,
            embedding_run_id=build.embedding_run_id,
            retrieval_index_build_id=build.id,
            profile_id=build.profile_id,
            lock_version=1,
            activated_by=current_user.id,
            activated_at=now,
            updated_at=now,
        )
    else:
        target.release_id = release.id
        target.embedding_run_id = build.embedding_run_id
        target.retrieval_index_build_id = build.id
        target.profile_id = build.profile_id
        target.lock_version += 1
        target.activated_by = current_user.id
        target.activated_at = now
        target.updated_at = now
    if previous_release and previous_release.id != release.id:
        previous_release.status = CorpusReleaseStatus.RETIRED
        previous_release.lock_version += 1
        session.add(previous_release)
        # Preserve atomic promotion while satisfying the immediate unique index
        # regardless of the UUID order SQLAlchemy uses for pending updates.
        session.flush()
    release.status = CorpusReleaseStatus.PRODUCTION
    release.approved_by = current_user.id
    release.approved_at = now
    release.lock_version += 1
    build.status = VectorIndexStatus.PROMOTED
    build.updated_at = now
    promotion.status = ReleasePromotionStatus.SUCCEEDED
    promotion.completed_at = now
    contributing_run_ids = set(
        session.exec(
            select(CorpusReleaseEntry.ingestion_run_id)
            .where(
                CorpusReleaseEntry.release_id == release.id,
                col(CorpusReleaseEntry.ingestion_run_id).is_not(None),
            )
            .distinct()
        ).all()
    )
    composition = (release.validation_report or {}).get("composition")
    if composition:
        contributing_run_ids.add(uuid.UUID(composition["run_id"]))
    for run_id in contributing_run_ids:
        if run_id is None:
            continue
        contributing_run = session.exec(
            select(IngestionRun).where(IngestionRun.id == run_id).with_for_update()
        ).one_or_none()
        if contributing_run is None:
            continue
        publishing_step = session.exec(
            select(IngestionStep)
            .where(
                IngestionStep.run_id == contributing_run.id,
                IngestionStep.stage == IngestionStage.PUBLISHING,
            )
            .with_for_update()
        ).first()
        if publishing_step is not None:
            publishing_step.status = IngestionStepStatus.SUCCEEDED
            publishing_step.completed_at = now
            publishing_step.updated_at = now
            publishing_step.lock_version += 1
            session.add(publishing_step)
        contributing_run.status = IngestionRunStatus.PUBLISHED
        contributing_run.current_stage = IngestionStage.PUBLISHING
        contributing_run.completed_at = now
        contributing_run.updated_at = now
        contributing_run.lock_version += 1
        session.add(contributing_run)
        append_run_event(
            session,
            contributing_run,
            event_type="release_published",
            message="Corpus release published to the active pgvector target",
            step=publishing_step,
            stage=IngestionStage.PUBLISHING,
            payload={
                "release_id": str(release.id),
                "retrieval_index_build_id": str(build.id),
                "index_kind": index_kind,
            },
            commit=False,
        )
    session.add_all([target, release, build, promotion])
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="corpus_release.publish",
            entity_type="corpus_release",
            entity_id=release.id,
            severity=AuditSeverity.INFO,
            payload={
                "backend": "pgvector",
                "index_kind": index_kind,
                "retrieval_index_build_id": str(build.id),
                "active_target_lock_version": target.lock_version,
            },
        )
    )
    _add_idempotency_record(
        session,
        scope=idempotency_scope,
        idempotency_key=idempotency_key,
        request_hash=idempotency_request_hash,
        result_type="release_promotion_attempt",
        result_id=promotion.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(release)
    session.refresh(promotion)
    return release, promotion


def _vector_index_validation_gates(vector_index: VectorIndex) -> list[str]:
    gates: list[str] = []
    report = vector_index.validation_report or {}
    if vector_index.point_count <= 0:
        gates.append("vector_index_has_no_points")
    if not vector_index.payload_schema_hash:
        gates.append("vector_index_payload_schema_hash_missing")
    if not vector_index.checksum:
        gates.append("vector_index_checksum_missing")
    if not vector_index.profile_hash:
        gates.append("vector_index_profile_hash_missing")
    if report.get("is_valid") is not True:
        gates.append("vector_index_local_validation_missing")
    sparse_errors = report.get("sparse_errors")
    if isinstance(sparse_errors, list) and sparse_errors:
        gates.append("vector_index_sparse_validation_failed")
    if report.get("remote_point_count") != vector_index.point_count:
        gates.append("vector_index_remote_count_mismatch")
    smoke_queries = report.get("smoke_queries")
    if not isinstance(smoke_queries, list) or not smoke_queries:
        gates.append("vector_index_smoke_queries_missing")
    elif any(
        not isinstance(query, dict) or query.get("passed") is not True
        for query in smoke_queries
    ):
        gates.append("vector_index_smoke_queries_failed")
    return gates


def _production_collection_name(
    session: Session, release: CorpusRelease | None
) -> str | None:
    if not release:
        return None
    vector_index = session.exec(
        select(VectorIndex).where(
            VectorIndex.release_id == release.id,
            VectorIndex.status == VectorIndexStatus.PROMOTED,
        )
    ).first()
    return vector_index.collection_name if vector_index else None


def _mark_release_production_in_db(
    session: Session,
    *,
    previous_release: CorpusRelease | None,
    release: CorpusRelease,
    vector_index: VectorIndex,
    promotion: ReleasePromotionAttempt,
    current_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key: str,
    idempotency_request_hash: str,
) -> None:
    approved_at = get_datetime_utc()
    if previous_release and previous_release.id != release.id:
        previous_release.status = CorpusReleaseStatus.RETIRED
        previous_release.lock_version += 1
        session.add(previous_release)
        session.flush()

    release.status = CorpusReleaseStatus.PRODUCTION
    release.approved_by = current_user_id
    release.approved_at = approved_at
    release.lock_version += 1
    vector_index.status = VectorIndexStatus.PROMOTED
    vector_index.updated_at = approved_at
    promotion.status = ReleasePromotionStatus.SUCCEEDED
    promotion.completed_at = approved_at
    composition = (release.validation_report or {}).get("composition")
    if composition:
        run = _get_run(session, uuid.UUID(composition["run_id"]))
        step = _get_run_step(session, run.id, IngestionStage.PUBLISHING)
        run.status = IngestionRunStatus.PUBLISHED
        run.current_stage = IngestionStage.PUBLISHING
        run.completed_at = run.updated_at = approved_at
        run.lock_version += 1
        step.status = IngestionStepStatus.SUCCEEDED
        step.completed_at = step.updated_at = approved_at
        step.lock_version += 1
        session.add_all([run, step])
        append_run_event(
            session,
            run,
            event_type="release_published",
            message="Composite corpus release published",
            step=step,
            payload={"release_id": str(release.id)},
            commit=False,
        )
    session.add(release)
    session.add(vector_index)
    session.add(promotion)
    session.add(
        AuditEvent(
            actor_user_id=current_user_id,
            action="corpus_release.publish",
            entity_type="corpus_release",
            entity_id=release.id,
            severity=AuditSeverity.INFO,
            payload={
                "vector_index_id": str(vector_index.id),
                "collection_name": vector_index.collection_name,
            },
        )
    )
    _add_idempotency_record(
        session,
        scope=idempotency_scope,
        idempotency_key=idempotency_key,
        request_hash=idempotency_request_hash,
        result_type="release_promotion_attempt",
        result_id=promotion.id,
        created_by=current_user_id,
    )
    session.commit()


def _rollback_qdrant_alias(
    *,
    alias_name: str,
    target_collection_name: str,
    previous_collection_name: str | None,
) -> tuple[bool, str | None]:
    try:
        if previous_collection_name:
            _switch_qdrant_alias(
                alias_name=alias_name,
                new_collection_name=previous_collection_name,
                old_collection_name=target_collection_name,
            )
        else:
            _delete_qdrant_alias(
                alias_name=alias_name,
                collection_name=target_collection_name,
            )
    except Exception as exc:
        return False, str(exc)
    return True, None


def _record_promotion_failure(
    session: Session,
    *,
    promotion_id: uuid.UUID,
    promotion_status: ReleasePromotionStatus,
    error_details: dict[str, object],
    rollback_completed: bool,
) -> None:
    try:
        promotion = session.get(ReleasePromotionAttempt, promotion_id)
        if not promotion:
            return
        promotion.status = promotion_status
        promotion.error_details = error_details
        promotion.rollback_completed = rollback_completed
        promotion.completed_at = get_datetime_utc()
        session.add(promotion)
        session.add(
            AuditEvent(
                actor_user_id=promotion.requested_by,
                action="corpus_release.publish_failed",
                entity_type="corpus_release",
                entity_id=promotion.release_id,
                severity=AuditSeverity.HIGH,
                payload={
                    "promotion_id": str(promotion.id),
                    "status": promotion_status.value,
                    "rollback_completed": rollback_completed,
                    "error_details": error_details,
                },
            )
        )
        session.commit()
    except Exception:
        session.rollback()


def _switch_qdrant_alias(
    *,
    alias_name: str,
    new_collection_name: str,
    old_collection_name: str | None,
) -> None:
    adapter = _qdrant_adapter()
    adapter.switch_alias(
        alias_name=alias_name,
        new_collection_name=new_collection_name,
        old_collection_name=old_collection_name,
    )


def _delete_qdrant_alias(*, alias_name: str, collection_name: str) -> None:
    adapter = _qdrant_adapter()
    adapter.delete_alias(alias_name=alias_name, collection_name=collection_name)


def _qdrant_adapter() -> QdrantHttpIndexAdapter:
    if not settings.QDRANT_URL:
        raise QdrantIndexError("Qdrant URL is not configured")
    return QdrantHttpIndexAdapter(
        base_url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def _enforce_actor_separation(
    session: Session,
    release: CorpusRelease,
    current_user: User,
    *,
    superuser_override_reason: str | None,
) -> None:
    entries = session.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    source_ids = [
        entry.source_document_id for entry in entries if entry.source_document_id
    ]
    sources = session.exec(
        select(SourceDocument).where(col(SourceDocument.id).in_(source_ids))
    ).all()
    uploader_ids = {source.created_by for source in sources if source.created_by}
    if current_user.id not in uploader_ids:
        return
    if current_user.is_superuser and superuser_override_reason:
        session.add(
            AuditEvent(
                actor_user_id=current_user.id,
                action="corpus_release.publish_override",
                entity_type="corpus_release",
                entity_id=release.id,
                severity=AuditSeverity.HIGH,
                reason=superuser_override_reason,
                payload={
                    "source_upload_actor_ids": sorted(str(uid) for uid in uploader_ids)
                },
            )
        )
        session.commit()
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Publisher must differ from the source uploader",
    )
