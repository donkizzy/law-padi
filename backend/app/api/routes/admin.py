import asyncio
import tempfile
import uuid
from collections.abc import AsyncIterable, Iterator
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlmodel import Session, col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.ingestion.blob_store import BlobStoreError
from app.ingestion.r2_blob_store import R2BlobStore
from app.ingestion.service import (
    MULTIPART_THRESHOLD_BYTES,
    cancel_ingestion_run,
    complete_source_upload,
    compose_corpus_release,
    create_source_upload_multipart_parts,
    create_source_upload_session,
    decide_review_candidate,
    derive_review_candidate,
    get_blob_store,
    latest_revision_text,
    publish_corpus_release,
    put_local_upload_object,
    read_admin_operational_alerts,
    read_corpus_release_manifest,
    read_corpus_release_publication_evidence,
    release_entry_count,
    require_admin_role,
    resume_ingestion_run,
    retry_ingestion_run,
    start_embedding,
    update_page_selection,
    update_review_candidate,
    update_review_issue,
    upload_headers_for_upload,
    upload_url_for_upload,
    user_has_admin_role,
    validate_corpus_release,
    verify_source_document,
)
from app.legal.enums import (
    AdminRole,
    CorpusReleaseStatus,
    EmbeddingRunStatus,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    ReviewIssueStatus,
)
from app.legal.models import (
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    VectorIndex,
)
from app.legal.schemas import (
    ActiveRetrievalTargetPublic,
    AdminMetrics,
    AdminOperationalAlertsPublic,
    AuditEventPublic,
    AuditEventsPublic,
    CandidateRevisionPublic,
    CompositeReleaseCreate,
    CorpusReleaseActorSeparationPublic,
    CorpusReleaseManifestPublic,
    CorpusReleasePromotionAttemptPublic,
    CorpusReleasePublic,
    CorpusReleasePublicationEvidencePublic,
    CorpusReleasePublishRequest,
    CorpusReleasePublishResponse,
    CorpusReleaseRetrievalIndexBuildPublic,
    CorpusReleasesPublic,
    CorpusReleaseValidationRequest,
    CorpusReleaseVectorIndexPublic,
    EmbeddingBenchmarkPublic,
    EmbeddingBenchmarkResult,
    EmbeddingProfileCreate,
    EmbeddingProfilePublic,
    EmbeddingProfileUpdate,
    IngestionArtifactPublic,
    IngestionEventPublic,
    IngestionRunControlRequest,
    IngestionRunDetail,
    IngestionRunPublic,
    IngestionRunsPublic,
    IngestionStepPublic,
    IngestionTaskPublic,
    MultipartPartPublic,
    MultipartPartsPublic,
    MultipartPartsRequest,
    MyAdminRolesPublic,
    OcrBenchmarkEvaluateRequest,
    OcrBenchmarkProviderResult,
    OcrBenchmarkPublic,
    PageSelectionUpdate,
    PublicProvisionVersion,
    PublicProvisionVersions,
    ReviewDecisionCreate,
    ReviewDecisionPublic,
    ReviewIssuePublic,
    ReviewIssueUpdate,
    ReviewItemDerive,
    ReviewItemPublic,
    ReviewItemsPublic,
    ReviewItemUpdate,
    SourceDocumentPublic,
    SourceDocumentVerificationRequest,
    SourcePagePublic,
    SourcePagesPublic,
    SourceUploadComplete,
    SourceUploadCompleteResponse,
    SourceUploadCreate,
    SourceUploadPublic,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/my-roles")
def read_my_admin_roles(
    session: SessionDep, current_user: CurrentUser
) -> MyAdminRolesPublic:
    from app.ingestion.service import user_has_admin_role

    if current_user.is_superuser:
        roles = [
            AdminRole.INGESTION_UPLOADER,
            AdminRole.LEGAL_REVIEWER,
            AdminRole.CORPUS_PUBLISHER,
        ]
    else:
        roles = [
            role
            for role in (
                AdminRole.INGESTION_UPLOADER,
                AdminRole.LEGAL_REVIEWER,
                AdminRole.CORPUS_PUBLISHER,
            )
            if user_has_admin_role(session, current_user, role)
        ]
    return MyAdminRolesPublic(
        user_id=current_user.id, is_superuser=current_user.is_superuser, roles=roles
    )


@router.get("/audit-events")
def read_audit_events(
    session: SessionDep,
    current_user: CurrentUser,
    entity_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = 100,
) -> AuditEventsPublic:
    from app.legal.models import AuditEvent

    _require_any_admin(session, current_user)
    query = select(AuditEvent).order_by(col(AuditEvent.created_at).desc()).limit(limit)
    if entity_id is not None:
        query = query.where(AuditEvent.entity_id == entity_id)
    if entity_type is not None:
        query = query.where(AuditEvent.entity_type == entity_type)
    events = session.exec(query).all()
    return AuditEventsPublic(
        data=[AuditEventPublic.model_validate(event) for event in events],
        count=len(events),
    )


@router.get("/metrics")
def read_admin_metrics(session: SessionDep, current_user: CurrentUser) -> AdminMetrics:
    _require_any_admin(session, current_user)
    active_runs = session.exec(
        select(func.count())
        .select_from(IngestionRun)
        .where(
            col(IngestionRun.status).in_(
                [
                    IngestionRunStatus.QUEUED,
                    IngestionRunStatus.RUNNING,
                    IngestionRunStatus.READY_TO_EMBED,
                    IngestionRunStatus.INDEXING,
                    IngestionRunStatus.READY_TO_PUBLISH,
                    IngestionRunStatus.PUBLISHING,
                ]
            )
        )
    ).one()
    blocked_runs = session.exec(
        select(func.count())
        .select_from(IngestionStep)
        .where(IngestionStep.status == IngestionStepStatus.BLOCKED)
    ).one()
    failed_runs = session.exec(
        select(func.count())
        .select_from(IngestionRun)
        .where(IngestionRun.status == IngestionRunStatus.FAILED)
    ).one()
    queue_depth = session.exec(
        select(func.count())
        .select_from(IngestionTask)
        .where(IngestionTask.status == IngestionTaskStatus.PENDING)
    ).one()
    worker_heartbeat = session.exec(select(func.max(IngestionTask.heartbeat_at))).one()
    pages_processed = session.exec(select(func.count()).select_from(SourcePage)).one()
    ocr_steps = session.exec(
        select(func.count())
        .select_from(IngestionStep)
        .where(
            col(IngestionStep.stage).in_(
                [IngestionStage.LOCAL_OCR, IngestionStage.MANAGED_OCR]
            ),
            IngestionStep.status == IngestionStepStatus.SUCCEEDED,
        )
    ).one()
    review_issues = session.exec(
        select(func.count())
        .select_from(ReviewIssue)
        .where(ReviewIssue.status == ReviewIssueStatus.OPEN)
    ).one()
    total_candidates = session.exec(
        select(func.count()).select_from(ExtractionCandidate)
    ).one()
    auto_approved = session.exec(
        select(func.count())
        .select_from(ExtractionCandidate)
        .where(ExtractionCandidate.status == ExtractionCandidateStatus.AUTO_APPROVED)
    ).one()
    embedding_total = session.exec(select(func.count()).select_from(EmbeddingRun)).one()
    embedding_done = session.exec(
        select(func.count())
        .select_from(EmbeddingRun)
        .where(EmbeddingRun.status == EmbeddingRunStatus.SUCCEEDED)
    ).one()
    production_release = session.exec(
        select(CorpusRelease).where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION
        )
    ).first()
    return AdminMetrics(
        active_runs=active_runs,
        blocked_runs=blocked_runs,
        failed_runs=failed_runs,
        queue_depth=queue_depth,
        worker_heartbeat=worker_heartbeat,
        pages_processed=pages_processed,
        ocr_fallback_rate=(ocr_steps / pages_processed) if pages_processed else 0,
        review_issues=review_issues,
        auto_approval_rate=(auto_approved / total_candidates)
        if total_candidates
        else 0,
        embedding_progress=(embedding_done / embedding_total) if embedding_total else 0,
        current_production_release=production_release.version
        if production_release
        else None,
    )


@router.get("/alerts")
def read_admin_alerts(
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminOperationalAlertsPublic:
    _require_any_admin(session, current_user)
    alerts = read_admin_operational_alerts(session)
    return AdminOperationalAlertsPublic(data=alerts, count=len(alerts))


@router.post("/source-uploads")
def create_source_upload(
    body: SourceUploadCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> SourceUploadPublic:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    upload = create_source_upload_session(session, body, current_user)
    return _upload_public(upload)


@router.put("/source-uploads/{upload_id}/object", status_code=204)
async def put_source_upload_object(
    upload_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
) -> Response:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    content_type = request.headers.get("content-type", "application/octet-stream")
    upload = session.get(SourceUpload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Source upload not found")
    with tempfile.TemporaryFile(mode="w+b") as content:
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > upload.expected_size:
                raise HTTPException(
                    status_code=413,
                    detail="Uploaded object exceeds the expected size",
                )
            content.write(chunk)
        if received != upload.expected_size:
            raise HTTPException(
                status_code=400,
                detail="Uploaded object size does not match the upload session",
            )
        content.seek(0)
        put_local_upload_object(session, upload_id, content, content_type)
    return Response(status_code=204)


@router.post("/source-uploads/{upload_id}/multipart-parts")
def create_multipart_upload_parts(
    upload_id: uuid.UUID,
    body: MultipartPartsRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> MultipartPartsPublic:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    upload = session.get(SourceUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Source upload not found")
    multipart = create_source_upload_multipart_parts(
        session,
        upload_id,
        part_count=body.part_count,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
    )
    parts = [
        MultipartPartPublic(
            part_number=part.part_number,
            upload_url=part.upload_url,
        )
        for part in multipart.parts
    ]
    return MultipartPartsPublic(
        upload_id=upload.id,
        multipart_upload_id=multipart.upload_id,
        parts=parts,
    )


@router.post("/source-uploads/{upload_id}/complete")
def complete_upload(
    upload_id: uuid.UUID,
    body: SourceUploadComplete,
    session: SessionDep,
    current_user: CurrentUser,
) -> SourceUploadCompleteResponse:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    upload, source, run, duplicate = complete_source_upload(
        session, upload_id, body, current_user
    )
    return SourceUploadCompleteResponse(
        upload=_upload_public(upload),
        source_document=_source_public(source) if source else None,
        run=_run_public(run) if run else None,
        duplicate=duplicate,
    )


@router.post("/source-documents/{source_document_id}/verify")
def verify_document_source(
    source_document_id: uuid.UUID,
    body: SourceDocumentVerificationRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> SourceDocumentPublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    source = verify_source_document(
        session,
        source_document_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        reason=body.reason,
        current_user=current_user,
    )
    return _source_public(source)


@router.get("/ingestion-runs")
def read_ingestion_runs(
    session: SessionDep,
    current_user: CurrentUser,
    status: IngestionRunStatus | None = None,
    stage: IngestionStage | None = None,
    skip: int = 0,
    limit: int = 100,
) -> IngestionRunsPublic:
    _require_any_admin(session, current_user)
    statement = select(IngestionRun)
    count_statement = select(func.count()).select_from(IngestionRun)
    if status:
        statement = statement.where(IngestionRun.status == status)
        count_statement = count_statement.where(IngestionRun.status == status)
    if stage:
        statement = statement.where(IngestionRun.current_stage == stage)
        count_statement = count_statement.where(IngestionRun.current_stage == stage)
    runs = session.exec(
        statement.order_by(col(IngestionRun.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return IngestionRunsPublic(
        data=[_run_public(run) for run in runs],
        count=session.exec(count_statement).one(),
    )


@router.get("/ingestion-runs/{run_id}")
def read_ingestion_run(
    run_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> IngestionRunDetail:
    _require_any_admin(session, current_user)
    run = session.get(IngestionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    steps = session.exec(
        select(IngestionStep)
        .where(IngestionStep.run_id == run.id)
        .order_by(col(IngestionStep.created_at))
    ).all()
    events = session.exec(
        select(IngestionEvent)
        .where(IngestionEvent.run_id == run.id)
        .order_by(col(IngestionEvent.sequence))
    ).all()
    tasks = session.exec(
        select(IngestionTask)
        .where(IngestionTask.run_id == run.id)
        .order_by(col(IngestionTask.created_at))
    ).all()
    return IngestionRunDetail(
        **_run_public(run).model_dump(),
        steps=[_step_public(step) for step in steps],
        events=[_event_public(event) for event in events],
        tasks=[_task_public(task) for task in tasks],
    )


@router.get("/ingestion-artifacts/{artifact_id}/content")
def read_ingestion_artifact_content(
    artifact_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Response:
    """Stream a retained artifact only to authorized ingestion administrators."""
    _require_any_admin(session, current_user)
    artifact = session.get(IngestionArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Ingestion artifact not found")
    run = session.get(IngestionRun, artifact.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    if (
        not current_user.is_superuser
        and not user_has_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
        and not user_has_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
        and run.created_by != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Artifact access is not permitted")

    store = get_blob_store()
    try:
        head = store.head(artifact.storage_key)
    except (BlobStoreError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=404, detail="Ingestion artifact object was not found"
        ) from exc

    if isinstance(store, R2BlobStore):
        return RedirectResponse(
            store.create_presigned_get_url(
                key=artifact.storage_key,
                expires_in_seconds=5 * 60,
            ),
            status_code=307,
        )

    def stream() -> Iterator[bytes]:
        with store.open_read(artifact.storage_key) as handle:
            while chunk := handle.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=artifact.mime_type or head.content_type,
        headers={
            "Content-Length": str(head.size_bytes),
            "Content-Disposition": f'inline; filename="artifact-{artifact.id}"',
        },
    )


@router.get("/ingestion-runs/{run_id}/events", response_class=EventSourceResponse)
async def stream_ingestion_run_events(
    run_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
    replay_only: bool = False,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> AsyncIterable[ServerSentEvent]:
    _require_any_admin(session, current_user)
    if not session.get(IngestionRun, run_id):
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    try:
        after_sequence = int(last_event_id or 0)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Last-Event-ID must be numeric"
        ) from exc

    from app.core.db import engine

    while not await request.is_disconnected():
        with Session(engine) as poll_session:
            events = poll_session.exec(
                select(IngestionEvent)
                .where(
                    IngestionEvent.run_id == run_id,
                    IngestionEvent.sequence > after_sequence,
                )
                .order_by(col(IngestionEvent.sequence))
            ).all()
            for event in events:
                after_sequence = event.sequence
                yield ServerSentEvent(
                    data=_event_public(event).model_dump(mode="json"),
                    event=event.event_type,
                    id=str(event.sequence),
                )
        if not events:
            yield ServerSentEvent(comment="keepalive")
        if replay_only:
            break
        await asyncio.sleep(1)


@router.get("/ingestion-runs/{run_id}/pages")
def read_ingestion_run_pages(
    run_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> SourcePagesPublic:
    _require_any_admin(session, current_user)
    pages = session.exec(
        select(SourcePage)
        .where(SourcePage.run_id == run_id)
        .order_by(col(SourcePage.page_number))
    ).all()
    return SourcePagesPublic(
        data=[_page_public(session, page) for page in pages], count=len(pages)
    )


@router.patch("/ingestion-runs/{run_id}/page-selection")
def patch_page_selection(
    run_id: uuid.UUID,
    body: PageSelectionUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> SourcePagesPublic:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    pages = update_page_selection(session, run_id, body, current_user)
    return SourcePagesPublic(
        data=[_page_public(session, page) for page in pages], count=len(pages)
    )


@router.post("/ingestion-runs/{run_id}/retry")
def retry_run(
    run_id: uuid.UUID,
    body: IngestionRunControlRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> IngestionRunPublic:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    run = retry_ingestion_run(
        session,
        run_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        current_user=current_user,
    )
    return _run_public(run)


@router.post("/ingestion-runs/{run_id}/cancel")
def cancel_run(
    run_id: uuid.UUID,
    body: IngestionRunControlRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> IngestionRunPublic:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    run = cancel_ingestion_run(
        session,
        run_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        current_user=current_user,
        reason=body.reason or "Run cancelled",
    )
    return _run_public(run)


@router.post("/ingestion-runs/{run_id}/resume")
def resume_run(
    run_id: uuid.UUID,
    body: IngestionRunControlRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> IngestionRunPublic:
    require_admin_role(session, current_user, AdminRole.INGESTION_UPLOADER)
    run = resume_ingestion_run(
        session,
        run_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        current_user=current_user,
    )
    return _run_public(run)


@router.post("/ingestion-runs/{run_id}/start-embedding")
def start_embedding_run(
    run_id: uuid.UUID,
    body: IngestionRunControlRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> IngestionRunPublic:
    require_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
    run = start_embedding(
        session,
        run_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        current_user=current_user,
    )
    return _run_public(run)


@router.get("/review-items")
def read_review_items(
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID | None = None,
    issue: str | None = None,
    confidence_lte: float | None = None,
    page: int | None = None,
    path: str | None = None,
    status: ExtractionCandidateStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> ReviewItemsPublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    statement = select(ExtractionCandidate)
    count_statement = select(func.count()).select_from(ExtractionCandidate)
    if run_id:
        statement = statement.where(col(ExtractionCandidate.run_id) == run_id)
        count_statement = count_statement.where(
            col(ExtractionCandidate.run_id) == run_id
        )
    if confidence_lte is not None:
        statement = statement.where(
            col(ExtractionCandidate.parser_confidence) <= confidence_lte
        )
        count_statement = count_statement.where(
            col(ExtractionCandidate.parser_confidence) <= confidence_lte
        )
    if page is not None:
        statement = statement.where(
            col(ExtractionCandidate.source_page_start).is_not(None),
            col(ExtractionCandidate.source_page_end).is_not(None),
            col(ExtractionCandidate.source_page_start) <= page,
            col(ExtractionCandidate.source_page_end) >= page,
        )
        count_statement = count_statement.where(
            col(ExtractionCandidate.source_page_start).is_not(None),
            col(ExtractionCandidate.source_page_end).is_not(None),
            col(ExtractionCandidate.source_page_start) <= page,
            col(ExtractionCandidate.source_page_end) >= page,
        )
    if path:
        statement = statement.where(
            col(ExtractionCandidate.canonical_path).contains(path)
        )
        count_statement = count_statement.where(
            col(ExtractionCandidate.canonical_path).contains(path)
        )
    if status:
        statement = statement.where(col(ExtractionCandidate.status) == status)
        count_statement = count_statement.where(
            col(ExtractionCandidate.status) == status
        )
    if issue:
        issue_candidate_ids = session.exec(
            select(ReviewIssue.candidate_id).where(ReviewIssue.issue_type == issue)
        ).all()
        statement = statement.where(
            col(ExtractionCandidate.id).in_(issue_candidate_ids)
        )
        count_statement = count_statement.where(
            col(ExtractionCandidate.id).in_(issue_candidate_ids)
        )
    candidates = session.exec(
        statement.order_by(col(ExtractionCandidate.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return ReviewItemsPublic(
        data=[_review_public(session, candidate) for candidate in candidates],
        count=session.exec(count_statement).one(),
    )


@router.get("/review-items/{candidate_id}")
def read_review_item(
    candidate_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> ReviewItemPublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    candidate = session.get(ExtractionCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Review item not found")
    return _review_public(session, candidate)


@router.patch("/review-items/{candidate_id}")
def patch_review_item(
    candidate_id: uuid.UUID,
    body: ReviewItemUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ReviewItemPublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    update_review_candidate(session, candidate_id, body, current_user)
    candidate = session.get(ExtractionCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Review item not found")
    return _review_public(session, candidate)


@router.post("/review-items/{candidate_id}/derived-items")
def derive_review_item(
    candidate_id: uuid.UUID,
    body: ReviewItemDerive,
    session: SessionDep,
    current_user: CurrentUser,
) -> ReviewItemPublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    candidate = derive_review_candidate(session, candidate_id, body, current_user)
    return _review_public(session, candidate)


@router.post("/review-items/{candidate_id}/decision")
def decide_review_item(
    candidate_id: uuid.UUID,
    body: ReviewDecisionCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ReviewItemPublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    candidate = decide_review_candidate(session, candidate_id, body, current_user)
    return _review_public(session, candidate)


@router.patch("/review-issues/{issue_id}")
def patch_review_issue(
    issue_id: uuid.UUID,
    body: ReviewIssueUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ReviewIssuePublic:
    require_admin_role(session, current_user, AdminRole.LEGAL_REVIEWER)
    issue = update_review_issue(session, issue_id, body, current_user)
    return ReviewIssuePublic.model_validate(issue)


@router.get("/embedding-benchmarks/{release_id}")
def read_embedding_benchmark(
    release_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> EmbeddingBenchmarkPublic:
    _require_any_admin(session, current_user)
    runs = session.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release_id)
    ).all()
    results: list[EmbeddingBenchmarkResult] = []
    for run in runs:
        profile = session.get(EmbeddingProfile, run.profile_id)
        if profile:
            results.append(
                EmbeddingBenchmarkResult(
                    profile_id=profile.id,
                    provider=profile.provider,
                    model_name=profile.model_name,
                    status=run.status,
                    recall_at_10=run.recall_at_10,
                    ndcg_at_10=run.ndcg_at_10,
                    cost_usd=run.cost_usd,
                    p95_latency_ms=run.p95_latency_ms,
                    selected_for_release=run.selected_for_release,
                    metrics=run.metrics,
                )
            )
    return EmbeddingBenchmarkPublic(release_id=release_id, results=results)


@router.get("/embedding-profiles")
def read_embedding_profiles(
    session: SessionDep, current_user: CurrentUser
) -> list[EmbeddingProfilePublic]:
    _require_any_admin(session, current_user)
    profiles = session.exec(
        select(EmbeddingProfile).order_by(col(EmbeddingProfile.name))
    ).all()
    return [EmbeddingProfilePublic.model_validate(profile) for profile in profiles]


@router.post("/embedding-profiles", status_code=201)
def create_embedding_profile(
    body: EmbeddingProfileCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> EmbeddingProfilePublic:
    require_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
    if body.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        raise HTTPException(
            status_code=409, detail="V1 profiles require 1,024 dimensions"
        )
    if body.is_active and not body.model_revision:
        raise HTTPException(
            status_code=409, detail="Active profiles require a pinned revision"
        )
    if session.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.name == body.name)
    ).first():
        raise HTTPException(status_code=409, detail="Embedding profile already exists")
    profile = EmbeddingProfile.model_validate(body)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return EmbeddingProfilePublic.model_validate(profile)


@router.patch("/embedding-profiles/{profile_id}")
def update_embedding_profile(
    profile_id: uuid.UUID,
    body: EmbeddingProfileUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> EmbeddingProfilePublic:
    require_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
    profile = session.get(EmbeddingProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Embedding profile not found")
    values = body.model_dump(exclude_unset=True)
    if values.get("is_active") is True and not values.get(
        "model_revision", profile.model_revision
    ):
        raise HTTPException(
            status_code=409, detail="Active profiles require a pinned revision"
        )
    profile.sqlmodel_update(values)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return EmbeddingProfilePublic.model_validate(profile)


@router.get("/ocr-benchmarks/{dataset_version}")
def read_ocr_benchmark(
    dataset_version: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> OcrBenchmarkPublic:
    from app.ingestion.evaluation import (
        active_evaluation_item_count,
        load_ocr_evaluation_pages,
    )
    from app.legal.enums import EvaluationDatasetKind, EvaluationItemKind

    _require_any_admin(session, current_user)
    pages = load_ocr_evaluation_pages(session, dataset_version)
    count = active_evaluation_item_count(
        session,
        dataset_version,
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        item_kind=EvaluationItemKind.OCR_PAGE,
    )
    return OcrBenchmarkPublic(
        dataset_version=dataset_version,
        sample_count=len(pages),
        winner=None,
        providers=[],
        active_dataset_items=count,
    )


@router.post("/ocr-benchmarks/{dataset_version}/evaluate")
def evaluate_ocr_benchmark_route(
    dataset_version: str,
    body: OcrBenchmarkEvaluateRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> OcrBenchmarkPublic:
    from app.ingestion.evaluation import (
        active_evaluation_item_count,
        load_ocr_evaluation_pages,
    )
    from app.ingestion.ocr_benchmark import OcrBenchmarkSample, evaluate_ocr_benchmark
    from app.legal.enums import EvaluationDatasetKind, EvaluationItemKind

    _require_any_admin(session, current_user)
    if body.dataset_version != dataset_version:
        raise HTTPException(
            status_code=400, detail="Dataset version mismatch in OCR benchmark request"
        )
    pages = {
        page.item_key: page
        for page in load_ocr_evaluation_pages(session, dataset_version)
    }
    if not pages:
        raise HTTPException(
            status_code=404, detail="OCR benchmark dataset has no pages"
        )
    grouped_texts: dict[str, dict[str, str]] = {}
    grouped_conf: dict[str, dict[str, float]] = {}
    grouped_cost: dict[str, dict[str, float]] = {}
    grouped_timing: dict[str, dict[str, float]] = {}
    grouped_failures: dict[str, dict[str, str]] = {}
    for sample in body.samples:
        if sample.provider not in (
            "google_document_ai",
            "azure_document_intelligence",
            "tesseract",
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown OCR provider: {sample.provider}",
            )
        grouped_texts.setdefault(sample.item_key, {})
        if sample.text is not None:
            grouped_texts[sample.item_key][sample.provider] = sample.text
        if sample.confidence is not None:
            grouped_conf.setdefault(sample.item_key, {})[sample.provider] = (
                sample.confidence
            )
        if sample.cost_usd is not None:
            grouped_cost.setdefault(sample.item_key, {})[sample.provider] = (
                sample.cost_usd
            )
        if sample.timing_ms is not None:
            grouped_timing.setdefault(sample.item_key, {})[sample.provider] = (
                sample.timing_ms
            )
        if sample.failure is not None:
            grouped_failures.setdefault(sample.item_key, {})[sample.provider] = (
                sample.failure
            )
    benchmark_samples: list[OcrBenchmarkSample] = []
    for item_key, page in pages.items():
        benchmark_samples.append(
            OcrBenchmarkSample(
                item_key=item_key,
                expected_text=page.expected_text,
                provider_texts=grouped_texts.get(item_key, {}),
                provider_confidence=grouped_conf.get(item_key, {}),
                provider_cost_usd=grouped_cost.get(item_key, {}),
                provider_timing_ms=grouped_timing.get(item_key, {}),
                provider_failures=grouped_failures.get(item_key, {}),
            )
        )
    result = evaluate_ocr_benchmark(
        dataset_version=dataset_version, samples=benchmark_samples
    )
    count = active_evaluation_item_count(
        session,
        dataset_version,
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        item_kind=EvaluationItemKind.OCR_PAGE,
    )
    return OcrBenchmarkPublic(
        dataset_version=dataset_version,
        sample_count=result.sample_count,
        winner=result.winner,
        providers=[
            OcrBenchmarkProviderResult(
                provider=item.provider,
                page_count=item.page_count,
                failure_count=item.failure_count,
                mean_character_accuracy=item.mean_character_accuracy,
                mean_confidence=item.mean_confidence,
                total_cost_usd=item.total_cost_usd,
                mean_timing_ms=item.mean_timing_ms,
            )
            for item in result.providers
        ],
        active_dataset_items=count,
    )


@router.get("/corpus-releases")
def read_corpus_releases(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> CorpusReleasesPublic:
    _require_any_admin(session, current_user)
    releases = session.exec(
        select(CorpusRelease)
        .order_by(col(CorpusRelease.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    count = session.exec(select(func.count()).select_from(CorpusRelease)).one()
    return CorpusReleasesPublic(
        data=[_release_public(session, release) for release in releases],
        count=count,
    )


@router.post("/corpus-releases/{release_id}/validate")
def validate_release(
    release_id: uuid.UUID,
    body: CorpusReleaseValidationRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> CorpusReleasePublic:
    require_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
    release = validate_corpus_release(
        session,
        release_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        current_user=current_user,
    )
    return _release_public(session, release)


@router.post("/corpus-releases/compose", status_code=201)
def compose_release(
    body: CompositeReleaseCreate, session: SessionDep, current_user: CurrentUser
) -> CorpusReleasePublic:
    require_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
    return _release_public(session, compose_corpus_release(session, body, current_user))


@router.get("/corpus-releases/{release_id}/manifest")
def read_release_manifest(
    release_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> CorpusReleaseManifestPublic:
    _require_any_admin(session, current_user)
    release, artifact, manifest = read_corpus_release_manifest(session, release_id)
    return CorpusReleaseManifestPublic(
        release_id=release.id,
        release_version=release.version,
        source_manifest_hash=release.source_manifest_hash,
        artifact=IngestionArtifactPublic.model_validate(artifact),
        manifest=manifest,
    )


@router.get("/corpus-releases/{release_id}/publication-evidence")
def read_release_publication_evidence(
    release_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> CorpusReleasePublicationEvidencePublic:
    _require_any_admin(session, current_user)
    (
        release,
        vector_indexes,
        retrieval_index_builds,
        promotion_attempts,
        source_uploader_ids,
        override_events,
        active_targets,
    ) = read_corpus_release_publication_evidence(session, release_id)
    approved_by_differs_from_uploaders = (
        None
        if release.approved_by is None
        else release.approved_by not in source_uploader_ids
    )
    return CorpusReleasePublicationEvidencePublic(
        release_id=release.id,
        release_version=release.version,
        vector_indexes=[
            CorpusReleaseVectorIndexPublic.model_validate(vector_index)
            for vector_index in vector_indexes
        ],
        retrieval_index_builds=[
            CorpusReleaseRetrievalIndexBuildPublic.model_validate(build)
            for build in retrieval_index_builds
        ],
        promotion_attempts=[
            CorpusReleasePromotionAttemptPublic.model_validate(promotion)
            for promotion in promotion_attempts
        ],
        active_targets=[
            ActiveRetrievalTargetPublic.model_validate(target)
            for target in active_targets
        ],
        actor_separation=CorpusReleaseActorSeparationPublic(
            current_actor_id=current_user.id,
            source_uploader_ids=source_uploader_ids,
            current_actor_is_source_uploader=current_user.id in source_uploader_ids,
            approved_by=release.approved_by,
            approved_by_differs_from_uploaders=approved_by_differs_from_uploaders,
            superuser_override_recorded=bool(override_events),
            override_reasons=[
                event.reason for event in override_events if event.reason
            ],
        ),
    )


@router.post("/corpus-releases/{release_id}/publish")
def publish_release(
    release_id: uuid.UUID,
    body: CorpusReleasePublishRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> CorpusReleasePublishResponse:
    require_admin_role(session, current_user, AdminRole.CORPUS_PUBLISHER)
    release, promotion = publish_corpus_release(
        session,
        release_id,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        current_user=current_user,
        superuser_override_reason=body.superuser_override_reason,
    )
    vector_index = (
        session.get(VectorIndex, promotion.vector_index_id)
        if promotion.vector_index_id is not None
        else None
    )
    retrieval_build = (
        session.get(RetrievalIndexBuild, promotion.retrieval_index_build_id)
        if promotion.retrieval_index_build_id is not None
        else None
    )
    return CorpusReleasePublishResponse(
        release=_release_public(session, release),
        promotion_status=promotion.status,
        vector_index_status=(
            retrieval_build.status
            if retrieval_build is not None
            else vector_index.status
            if vector_index is not None
            else None
        ),
    )


@router.get("/corpus-releases/production/provision-versions")
def read_production_provision_versions(
    session: SessionDep, current_user: CurrentUser
) -> PublicProvisionVersions:
    _require_any_admin(session, current_user)
    production_release = session.exec(
        select(CorpusRelease).where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION
        )
    ).first()
    if not production_release:
        return PublicProvisionVersions(data=[], count=0)
    entries = session.exec(
        select(CorpusReleaseEntry).where(
            CorpusReleaseEntry.release_id == production_release.id
        )
    ).all()
    data: list[PublicProvisionVersion] = []
    for entry in entries:
        version = session.get(ProvisionVersion, entry.provision_version_id)
        if not version:
            continue
        provision = session.get(Provision, version.provision_id)
        if not provision:
            continue
        data.append(
            PublicProvisionVersion(
                id=version.id,
                provision_id=version.provision_id,
                text=version.text,
                canonical_path=provision.canonical_path,
                release_version=production_release.version,
                status=production_release.status,
            )
        )
    return PublicProvisionVersions(data=data, count=len(data))


def _require_any_admin(session: Session, current_user: CurrentUser) -> None:
    if current_user.is_superuser:
        return
    for role in (
        AdminRole.INGESTION_UPLOADER,
        AdminRole.LEGAL_REVIEWER,
        AdminRole.CORPUS_PUBLISHER,
    ):
        try:
            require_admin_role(session, current_user, role)
            return
        except HTTPException:
            continue
    raise HTTPException(
        status_code=403, detail="The user does not have an ingestion admin role"
    )


def _check_expected_version(actual_version: int, expected_version: int) -> None:
    if actual_version != expected_version:
        raise HTTPException(
            status_code=409, detail="The record was modified by another operation"
        )


def _upload_public(upload: SourceUpload) -> SourceUploadPublic:
    return SourceUploadPublic(
        id=upload.id,
        idempotency_key=upload.idempotency_key,
        source_document_id=upload.source_document_id,
        instrument_slug=upload.instrument_slug,
        instrument_title=upload.instrument_title,
        instrument_type=upload.instrument_type,
        source_title=upload.source_title,
        authority=upload.authority,
        source_url=upload.source_url,
        source_tier=upload.source_tier,
        is_legal_revision=upload.is_legal_revision,
        legal_revision_effective_at=upload.legal_revision_effective_at,
        original_filename=upload.original_filename,
        mime_type=upload.mime_type,
        expected_size=upload.expected_size,
        expected_sha256=upload.expected_sha256,
        actual_sha256=upload.actual_sha256,
        upload_backend=upload.upload_backend,
        quarantine_key=upload.quarantine_key,
        canonical_key=upload.canonical_key,
        upload_url=upload_url_for_upload(upload),
        upload_headers=upload_headers_for_upload(upload),
        multipart_required=upload.expected_size > MULTIPART_THRESHOLD_BYTES,
        status=upload.status,
        error_message=upload.error_message,
        lock_version=upload.lock_version,
        expires_at=upload.expires_at,
        completed_at=upload.completed_at,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
    )


def _source_public(source: SourceDocument) -> SourceDocumentPublic:
    return SourceDocumentPublic(
        id=source.id,
        legal_instrument_id=source.legal_instrument_id,
        authority=source.authority,
        title=source.title,
        source_url=source.source_url,
        mime_type=source.mime_type,
        sha256=source.sha256,
        storage_backend=source.storage_backend,
        storage_bucket=source.storage_bucket,
        storage_key=source.storage_key,
        original_filename=source.original_filename,
        file_size=source.file_size,
        page_count=source.page_count,
        published_at=source.published_at,
        retrieved_at=source.retrieved_at,
        source_tier=source.source_tier,
        is_legal_revision=source.is_legal_revision,
        legal_revision_effective_at=source.legal_revision_effective_at,
        parser_version=source.parser_version,
        verification_status=source.verification_status,
        created_by=source.created_by,
        verified_by=source.verified_by,
        verified_at=source.verified_at,
        lock_version=source.lock_version,
        created_at=source.created_at,
    )


def _run_public(run: IngestionRun) -> IngestionRunPublic:
    return IngestionRunPublic(
        id=run.id,
        source_upload_id=run.source_upload_id,
        source_document_id=run.source_document_id,
        created_by=run.created_by,
        status=run.status,
        current_stage=run.current_stage,
        pipeline_version=run.pipeline_version,
        pipeline_config=run.pipeline_config,
        expected_page_count=run.expected_page_count,
        total_units=run.total_units,
        completed_units=run.completed_units,
        failed_units=run.failed_units,
        lock_version=run.lock_version,
        error_details=run.error_details,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def _step_public(step: IngestionStep) -> IngestionStepPublic:
    return IngestionStepPublic.model_validate(step)


def _event_public(event: IngestionEvent) -> IngestionEventPublic:
    return IngestionEventPublic.model_validate(event)


def _task_public(task: IngestionTask) -> IngestionTaskPublic:
    return IngestionTaskPublic.model_validate(task)


def _page_public(session: Session, page: SourcePage) -> SourcePagePublic:
    artifact = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == page.run_id,
            IngestionArtifact.source_page_id == page.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.PAGE_THUMBNAIL,
        )
    ).first()
    public = SourcePagePublic.model_validate(page)
    public.thumbnail_url = (
        f"{settings.API_V1_STR}/admin/ingestion-artifacts/{artifact.id}/content"
        if artifact
        else None
    )
    return public


def _review_public(
    session: Session, candidate: ExtractionCandidate
) -> ReviewItemPublic:
    issues = session.exec(
        select(ReviewIssue)
        .where(ReviewIssue.candidate_id == candidate.id)
        .order_by(col(ReviewIssue.created_at))
    ).all()
    revisions = session.exec(
        select(CandidateRevision)
        .where(CandidateRevision.candidate_id == candidate.id)
        .order_by(col(CandidateRevision.revision_number))
    ).all()
    decisions = session.exec(
        select(ReviewDecisionRecord)
        .where(ReviewDecisionRecord.candidate_id == candidate.id)
        .order_by(col(ReviewDecisionRecord.created_at))
    ).all()
    source = session.get(SourceDocument, candidate.source_document_id)
    source_page_thumbnail_url = None
    if candidate.source_page_start is not None:
        source_page = session.exec(
            select(SourcePage).where(
                SourcePage.run_id == candidate.run_id,
                SourcePage.source_document_id == candidate.source_document_id,
                SourcePage.page_number == candidate.source_page_start,
            )
        ).first()
        if source_page:
            thumbnail = session.exec(
                select(IngestionArtifact).where(
                    IngestionArtifact.run_id == candidate.run_id,
                    IngestionArtifact.source_page_id == source_page.id,
                    IngestionArtifact.artifact_type
                    == IngestionArtifactType.PAGE_THUMBNAIL,
                )
            ).first()
            if thumbnail:
                source_page_thumbnail_url = (
                    f"{settings.API_V1_STR}/admin/ingestion-artifacts/"
                    f"{thumbnail.id}/content"
                )
    return ReviewItemPublic(
        id=candidate.id,
        run_id=candidate.run_id,
        source_document_id=candidate.source_document_id,
        source_document=_source_public(source) if source else None,
        parent_candidate_id=candidate.parent_candidate_id,
        materialized_provision_id=candidate.materialized_provision_id,
        materialized_version_id=candidate.materialized_version_id,
        kind=candidate.kind,
        number=candidate.number,
        heading=candidate.heading,
        canonical_path=candidate.canonical_path,
        sort_key=candidate.sort_key,
        raw_text=candidate.raw_text,
        latest_revision_text=latest_revision_text(session, candidate),
        normalized_text=candidate.normalized_text,
        source_page_start=candidate.source_page_start,
        source_page_end=candidate.source_page_end,
        source_page_thumbnail_url=source_page_thumbnail_url,
        source_spans=candidate.source_spans,
        ancestor_headings=candidate.ancestor_headings,
        parser_version=candidate.parser_version,
        extractor_version=candidate.extractor_version,
        parser_confidence=candidate.parser_confidence,
        extractor_confidence=candidate.extractor_confidence,
        status=candidate.status,
        blocking_issue_count=candidate.blocking_issue_count,
        revision_number=candidate.revision_number,
        lock_version=candidate.lock_version,
        issues=[ReviewIssuePublic.model_validate(issue) for issue in issues],
        revisions=[
            CandidateRevisionPublic.model_validate(revision) for revision in revisions
        ],
        decisions=[
            ReviewDecisionPublic.model_validate(decision) for decision in decisions
        ],
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _release_public(session: Session, release: CorpusRelease) -> CorpusReleasePublic:
    instruments = session.exec(
        select(LegalInstrument)
        .join(Provision, col(Provision.instrument_id) == col(LegalInstrument.id))
        .join(ProvisionVersion, col(ProvisionVersion.provision_id) == col(Provision.id))
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.provision_version_id) == col(ProvisionVersion.id),
        )
        .where(CorpusReleaseEntry.release_id == release.id)
        .distinct()
        .order_by(LegalInstrument.slug)
    ).all()
    return CorpusReleasePublic(
        id=release.id,
        version=release.version,
        status=release.status,
        source_manifest_hash=release.source_manifest_hash,
        embedding_model=release.embedding_model,
        embedding_model_version=release.embedding_model_version,
        parser_version=release.parser_version,
        validation_report=release.validation_report,
        approved_by=release.approved_by,
        approved_at=release.approved_at,
        lock_version=release.lock_version,
        created_at=release.created_at,
        evidence_count=release_entry_count(session, release.id),
        instrument_slugs=[instrument.slug for instrument in instruments],
        instrument_types=sorted(
            {instrument.instrument_type for instrument in instruments}
        ),
    )
