import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlmodel import Session, col, delete, func, select

from app import crud
from app.core.config import settings
from app.ingestion import LocalBlobStore, MultipartUpload, MultipartUploadPartUrl
from app.ingestion.workflow import append_run_event, create_run_steps
from app.legal.enums import (
    AdminRole,
    AuditSeverity,
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
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    ReleasePromotionStatus,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    SourceTier,
    SourceUploadStatus,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    AdminRoleAssignment,
    AuditEvent,
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    IdempotencyRecord,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    ReleasePromotionAttempt,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    VectorIndex,
)
from app.models import User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email


def test_admin_metrics_requires_an_ingestion_admin_role(
    client: TestClient,
    db: Session,
) -> None:
    headers = authentication_token_from_email(
        client=client, email=random_email(), db=db
    )

    response = client.get(f"{settings.API_V1_STR}/admin/metrics", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "The user does not have an ingestion admin role"


def test_admin_metrics_counts_auto_approved_candidates(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    db.exec(delete(ReviewDecisionRecord))
    db.exec(delete(ReviewIssue))
    db.exec(delete(CandidateRevision))
    db.exec(delete(ExtractionCandidate))
    db.commit()
    source, run = _source_and_run(db)
    db.add(
        ExtractionCandidate(
            run_id=run.id,
            source_document_id=source.id,
            kind=ProvisionKind.SECTION,
            number="37",
            canonical_path=f"constitution.1999.section37.{uuid.uuid4().hex}",
            sort_key="037",
            status=ExtractionCandidateStatus.AUTO_APPROVED,
        )
    )
    db.add(
        ExtractionCandidate(
            run_id=run.id,
            source_document_id=source.id,
            kind=ProvisionKind.SECTION,
            number="38",
            canonical_path=f"constitution.1999.section38.{uuid.uuid4().hex}",
            sort_key="038",
            status=ExtractionCandidateStatus.APPROVED,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/metrics", headers=superuser_token_headers
    )

    assert response.status_code == 200
    assert response.json()["auto_approval_rate"] == 0.5


def test_admin_alerts_surface_dashboard_only_operational_failures(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    admin = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert admin
    now = datetime.now(UTC)
    source, failed_run = _source_and_run(db, created_by=admin.id)
    failed_run.status = IngestionRunStatus.FAILED
    failed_run.current_stage = IngestionStage.NATIVE_EXTRACTION
    failed_run.error_details = {"message": "Native extraction worker failed."}
    failed_run.completed_at = now
    failed_run.updated_at = now
    native_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == failed_run.id,
            IngestionStep.stage == IngestionStage.NATIVE_EXTRACTION,
        )
    ).one()
    stale_task = IngestionTask(
        run_id=failed_run.id,
        step_id=native_step.id,
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        status=IngestionTaskStatus.LEASED,
        lease_owner="worker-alert-test",
        leased_until=now - timedelta(minutes=5),
        heartbeat_at=now - timedelta(minutes=10),
        idempotency_key=f"{failed_run.id}:stalled-alert",
    )
    candidate = ExtractionCandidate(
        run_id=failed_run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        canonical_path=f"constitution.1999.section37.alert.{uuid.uuid4().hex}",
        sort_key="037",
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=1,
    )
    db.add_all([failed_run, stale_task, candidate])
    db.commit()
    db.refresh(stale_task)
    db.refresh(candidate)
    blocking_issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="source_span_coverage",
        severity=ReviewIssueSeverity.BLOCKING,
        status=ReviewIssueStatus.OPEN,
        blocking=True,
        message="Candidate requires source-span verification.",
        evidence={"page": 2},
    )
    release, vector_index = _release_bundle(db, uploader=admin)
    failed_profile = EmbeddingProfile(
        name=f"bge-m3-alert-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
        model_name="BAAI/bge-m3",
        model_revision="pinned",
        vector_dimensions=1024,
        configuration={"endpoint": "private-tei"},
    )
    db.add(failed_profile)
    db.commit()
    db.refresh(failed_profile)
    failed_embedding = EmbeddingRun(
        release_id=release.id,
        profile_id=failed_profile.id,
        status=EmbeddingRunStatus.FAILED,
        benchmark_dataset_version="alert-benchmark-v1",
        error_details={"message": "HF TEI endpoint returned 502."},
        completed_at=now,
    )
    failed_promotion = ReleasePromotionAttempt(
        release_id=release.id,
        vector_index_id=vector_index.id,
        requested_by=admin.id,
        status=ReleasePromotionStatus.FAILED,
        target_collection_name=vector_index.collection_name,
        error_details={"message": "Qdrant alias switch failed."},
        completed_at=now,
    )
    db.add_all([blocking_issue, failed_embedding, failed_promotion])
    db.commit()
    db.refresh(blocking_issue)
    db.refresh(failed_embedding)
    db.refresh(failed_promotion)

    response = client.get(
        f"{settings.API_V1_STR}/admin/alerts",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    alerts = response.json()["data"]
    indexed_alerts = {alert["id"]: alert for alert in alerts}
    terminal_alert = indexed_alerts[f"run-failed:{failed_run.id}"]
    stalled_alert = indexed_alerts[f"stalled-lease:{stale_task.id}"]
    issue_alert = indexed_alerts[f"blocking-review-issue:{blocking_issue.id}"]
    embedding_alert = indexed_alerts[f"embedding-provider-outage:{failed_embedding.id}"]
    publication_alert = indexed_alerts[f"publication-failed:{failed_promotion.id}"]

    assert terminal_alert["alert_type"] == "terminal_failure"
    assert terminal_alert["message"] == "Native extraction worker failed."
    assert stalled_alert["alert_type"] == "stalled_lease"
    assert stalled_alert["task_id"] == str(stale_task.id)
    assert issue_alert["alert_type"] == "unresolved_blocking_issue"
    assert issue_alert["candidate_id"] == str(candidate.id)
    assert embedding_alert["alert_type"] == "embedding_provider_outage"
    assert embedding_alert["release_id"] == str(release.id)
    assert publication_alert["alert_type"] == "publication_failure"
    assert publication_alert["promotion_attempt_id"] == str(failed_promotion.id)


def test_scoped_admin_role_can_review_but_cannot_upload(
    client: TestClient,
    db: Session,
) -> None:
    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    db.add(
        AdminRoleAssignment(
            user_id=user.id,
            role=AdminRole.LEGAL_REVIEWER,
            reason="route test",
        )
    )
    db.commit()

    review_response = client.get(
        f"{settings.API_V1_STR}/admin/review-items", headers=headers
    )
    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=headers,
        json=_source_upload_payload(_pdf_bytes()),
    )

    assert review_response.status_code == 200
    assert upload_response.status_code == 403


def test_pdf_upload_session_completion_creates_immutable_source_and_run(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_bytes()
    source_upload_body = _source_upload_payload(pdf)

    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=source_upload_body,
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert upload["status"] == SourceUploadStatus.CREATED
    assert upload["multipart_required"] is False
    assert upload["upload_headers"] == {"content-type": "application/pdf"}
    assert upload["upload_url"].endswith(f"/source-uploads/{upload['id']}/object")

    repeat_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=source_upload_body,
    )
    assert repeat_response.status_code == 200
    assert repeat_response.json()["id"] == upload["id"]
    conflicting_repeat = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json={
            **source_upload_body,
            "instrument_slug": f"constitution-repeat-{uuid.uuid4().hex}",
        },
    )
    assert conflicting_repeat.status_code == 409
    assert conflicting_repeat.json()["detail"] == (
        "Idempotency key was already used for a different request"
    )

    put_response = client.put(
        upload["upload_url"],
        headers={**superuser_token_headers, "content-type": "application/pdf"},
        content=pdf,
    )
    assert put_response.status_code == 204
    stored_upload = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert stored_upload
    db.refresh(stored_upload)

    complete_body = {
        "idempotency_key": f"complete-{uuid.uuid4().hex}",
        "expected_version": stored_upload.lock_version,
        "actual_sha256": _sha256(pdf),
    }
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json=complete_body,
    )

    assert complete_response.status_code == 200
    payload = complete_response.json()
    assert payload["duplicate"] is False
    assert payload["upload"]["status"] == SourceUploadStatus.COMPLETED
    assert payload["source_document"]["sha256"] == _sha256(pdf)
    assert payload["source_document"]["page_count"] == 1
    assert payload["run"]["status"] == IngestionRunStatus.QUEUED
    assert payload["run"]["current_stage"] == IngestionStage.VERIFYING_UPLOAD
    repeated_complete = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json=complete_body,
    )
    assert repeated_complete.status_code == 200
    assert (
        repeated_complete.json()["source_document"]["id"]
        == payload["source_document"]["id"]
    )
    assert repeated_complete.json()["run"]["id"] == payload["run"]["id"]
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionRun)
            .where(IngestionRun.source_upload_id == uuid.UUID(upload["id"]))
        ).one()
        == 1
    )

    source = db.get(SourceDocument, payload["source_document"]["id"])
    assert source
    assert source.storage_key
    assert source.storage_key.startswith("sources/sha256/")
    assert (tmp_path / source.storage_key).exists()

    run_id = uuid.UUID(payload["run"]["id"])
    steps = db.exec(
        select(IngestionStep)
        .where(IngestionStep.run_id == run_id)
        .order_by(IngestionStep.created_at)
    ).all()
    assert [step.stage for step in steps][0] == IngestionStage.UPLOADING
    assert [step.stage for step in steps][-1] == IngestionStage.PUBLISHING
    assert steps[0].status == IngestionStepStatus.SUCCEEDED

    task = db.exec(select(IngestionTask).where(IngestionTask.run_id == run_id)).one()
    assert task.status == IngestionTaskStatus.PENDING
    assert task.task_type == IngestionStage.VERIFYING_UPLOAD

    event = db.exec(select(IngestionEvent).where(IngestionEvent.run_id == run_id)).one()
    assert event.event_type == "upload_completed"

    detail_response = client.get(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run_id}",
        headers=superuser_token_headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["steps"]
    assert detail["events"][0]["event_type"] == "upload_completed"
    assert detail["tasks"][0]["task_type"] == IngestionStage.VERIFYING_UPLOAD

    replay_response = client.get(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run_id}/events",
        headers={**superuser_token_headers, "Last-Event-ID": "0"},
    )
    assert replay_response.status_code == 200
    assert "upload_completed" in replay_response.text
    assert "id: 1" in replay_response.text


def test_ingestion_run_events_replays_only_after_last_event_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _source, run = _source_and_run(db)
    profiling_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.PROFILING,
        )
    ).one()
    first_event = append_run_event(
        db,
        run,
        event_type="stage_started",
        message="Profiling started",
        step=profiling_step,
    )
    second_event = append_run_event(
        db,
        run,
        event_type="stage_succeeded",
        message="Profiling completed",
        stage=IngestionStage.PROFILING,
    )

    response = client.get(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/events",
        headers={
            **superuser_token_headers,
            "Last-Event-ID": str(first_event.sequence),
        },
    )

    assert response.status_code == 200
    assert f"id: {second_event.sequence}" in response.text
    assert "stage_succeeded" in response.text
    assert "Profiling completed" in response.text
    assert f"id: {first_event.sequence}" not in response.text
    assert "Profiling started" not in response.text


def test_r2_pdf_upload_session_uses_presigned_quarantine_put_and_completion(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _ManagedLocalBlobStore(tmp_path)
    monkeypatch.setattr(settings, "INGESTION_STORAGE_BACKEND", "r2")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "law-padi-ingestion")
    monkeypatch.setattr("app.ingestion.service.get_blob_store", lambda: store)
    pdf = _unique_pdf_bytes()

    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=_source_upload_payload(pdf),
    )

    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert upload["upload_backend"] == "r2"
    assert upload["multipart_required"] is False
    assert upload["upload_url"] == (
        f"https://r2.example.test/{upload['quarantine_key']}?signed=put"
    )
    assert upload["upload_headers"] == {
        "content-type": "application/pdf",
        "x-amz-meta-source-upload-id": upload["id"],
        "x-amz-meta-sha256": _sha256(pdf),
    }
    assert store.presigned_put_calls[-1]["metadata"] == {
        "source-upload-id": upload["id"],
        "sha256": _sha256(pdf),
    }

    store.put_quarantine(
        upload_id=upload["id"],
        filename="constitution.pdf",
        content=pdf,
        content_type="application/pdf",
        metadata={"sha256": _sha256(pdf)},
    )
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": upload["lock_version"],
            "actual_sha256": _sha256(pdf),
        },
    )

    assert complete_response.status_code == 200
    payload = complete_response.json()
    assert payload["upload"]["status"] == SourceUploadStatus.COMPLETED
    assert payload["source_document"]["storage_backend"] == "r2"
    assert payload["source_document"]["storage_bucket"] == "law-padi-ingestion"


def test_r2_multipart_part_urls_are_issued_by_blob_store_for_large_uploads(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _ManagedLocalBlobStore(tmp_path)
    monkeypatch.setattr(settings, "INGESTION_STORAGE_BACKEND", "r2")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "law-padi-ingestion")
    monkeypatch.setattr("app.ingestion.service.get_blob_store", lambda: store)
    pdf = _pdf_bytes()

    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=_source_upload_payload(
            pdf,
            expected_size=100 * 1024 * 1024 + 1,
        ),
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert upload["multipart_required"] is True
    assert upload["upload_url"] == ""

    parts_body = {
        "idempotency_key": f"parts-{uuid.uuid4().hex}",
        "expected_version": upload["lock_version"],
        "part_count": 3,
    }
    parts_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/multipart-parts",
        headers=superuser_token_headers,
        json=parts_body,
    )

    assert parts_response.status_code == 200
    payload = parts_response.json()
    assert payload["multipart_upload_id"] == "managed-multipart-1"
    assert [part["part_number"] for part in payload["parts"]] == [1, 2, 3]
    assert payload["parts"][0]["upload_url"].endswith("?partNumber=1")
    assert store.multipart_calls[-1]["metadata"] == {
        "source-upload-id": upload["id"],
        "sha256": _sha256(pdf),
    }
    stored_upload = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert stored_upload
    db.refresh(stored_upload)
    assert stored_upload.multipart_upload_id == "managed-multipart-1"
    assert stored_upload.status == SourceUploadStatus.UPLOADING
    assert stored_upload.lock_version == 2
    repeated_parts = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/multipart-parts",
        headers=superuser_token_headers,
        json=parts_body,
    )
    assert repeated_parts.status_code == 200
    assert repeated_parts.json() == payload
    assert len(store.multipart_calls) == 1


def test_upload_completion_reuses_existing_source_for_duplicate_pdf(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_bytes()
    first = _complete_pdf_upload(client, superuser_token_headers, db, pdf)

    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=_source_upload_payload(pdf, slug=f"constitution-dupe-{uuid.uuid4().hex}"),
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    put_response = client.put(
        upload["upload_url"],
        headers={**superuser_token_headers, "content-type": "application/pdf"},
        content=pdf,
    )
    assert put_response.status_code == 204
    stored_upload = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert stored_upload
    db.refresh(stored_upload)

    duplicate_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": stored_upload.lock_version,
        },
    )

    assert duplicate_response.status_code == 200
    payload = duplicate_response.json()
    assert payload["duplicate"] is True
    assert payload["run"] is None
    assert payload["source_document"]["id"] == first["source_document"]["id"]
    assert payload["upload"]["status"] == SourceUploadStatus.DUPLICATE


def test_upload_session_rejects_non_pdf_sources(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=_source_upload_payload(b"not a pdf", mime_type="text/plain"),
    )

    assert response.status_code == 422
    assert "Constitution PDF" in response.text


def test_upload_completion_rejects_corrupt_pdf_and_marks_upload_failed(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    content = b"%PDF-corrupt"
    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json=_source_upload_payload(content),
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert (
        client.put(
            upload["upload_url"],
            headers={**superuser_token_headers, "content-type": "application/pdf"},
            content=content,
        ).status_code
        == 204
    )
    stored_upload = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert stored_upload
    db.refresh(stored_upload)

    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": stored_upload.lock_version,
        },
    )

    assert complete_response.status_code == 400
    db.refresh(stored_upload)
    assert stored_upload.status == SourceUploadStatus.FAILED


def test_page_selection_records_admin_confirmation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=1,
            role=PageRole.FRONT_MATTER,
            inclusion_status=PageInclusionStatus.SUGGESTED_EXCLUDE,
            inclusion_reason="cover page",
        ),
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=2,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        ),
    ]
    db.add_all(pages)
    db.commit()
    for page_item in pages:
        db.refresh(page_item)

    selection_body = {
        "idempotency_key": f"pages-{uuid.uuid4().hex}",
        "pages": [
            {
                "page_number": 1,
                "inclusion_status": PageInclusionStatus.EXCLUDED,
                "inclusion_reason": "front matter excluded",
                "expected_version": pages[0].lock_version,
            },
            {
                "page_number": 2,
                "inclusion_status": PageInclusionStatus.INCLUDED,
                "inclusion_reason": "legal body",
                "expected_version": pages[1].lock_version,
            },
        ],
    }
    response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json=selection_body,
    )

    assert response.status_code == 200
    assert [page["inclusion_status"] for page in response.json()["data"]] == [
        PageInclusionStatus.EXCLUDED,
        PageInclusionStatus.INCLUDED,
    ]
    db.refresh(run)
    assert run.status == IngestionRunStatus.RUNNING
    assert run.current_stage == IngestionStage.RENDERING
    rendering_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.RENDERING.value,
        )
    ).one()
    assert rendering_task.status == IngestionTaskStatus.PENDING
    repeated_response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json=selection_body,
    )
    assert repeated_response.status_code == 200
    assert [page["inclusion_status"] for page in repeated_response.json()["data"]] == [
        PageInclusionStatus.EXCLUDED,
        PageInclusionStatus.INCLUDED,
    ]
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.RENDERING.value,
            )
        ).one()
        == 1
    )
    event = db.exec(
        select(IngestionEvent)
        .where(IngestionEvent.run_id == run.id)
        .order_by(IngestionEvent.sequence.desc())
    ).first()
    assert event
    assert event.event_type == "page_selection_confirmed"


def test_run_control_mutations_are_idempotent(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _source, cancel_run = _source_and_run(db)
    cancel_body = {
        "idempotency_key": f"cancel-{uuid.uuid4().hex}",
        "expected_version": cancel_run.lock_version,
        "reason": "Operator cancelled run",
    }
    cancel_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{cancel_run.id}/cancel",
        headers=superuser_token_headers,
        json=cancel_body,
    )
    assert cancel_response.status_code == 200
    repeated_cancel = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{cancel_run.id}/cancel",
        headers=superuser_token_headers,
        json=cancel_body,
    )
    assert repeated_cancel.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionEvent)
            .where(
                IngestionEvent.run_id == cancel_run.id,
                IngestionEvent.event_type == "run_cancelled",
            )
        ).one()
        == 1
    )

    _source, resume_run = _source_and_run(db)
    resume_run.status = IngestionRunStatus.WAITING_FOR_INPUT
    resume_run.current_stage = IngestionStage.AWAITING_PAGE_CONFIRMATION
    db.add(resume_run)
    db.commit()
    db.refresh(resume_run)
    resume_body = {
        "idempotency_key": f"resume-{uuid.uuid4().hex}",
        "expected_version": resume_run.lock_version,
    }
    resume_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{resume_run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )
    assert resume_response.status_code == 200
    repeated_resume = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{resume_run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )
    assert repeated_resume.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionEvent)
            .where(
                IngestionEvent.run_id == resume_run.id,
                IngestionEvent.event_type == "run_resumed",
            )
        ).one()
        == 1
    )

    _source, retry_run = _source_and_run(db)
    retry_run.status = IngestionRunStatus.FAILED
    retry_run.current_stage = IngestionStage.NATIVE_EXTRACTION
    db.add(retry_run)
    db.commit()
    db.refresh(retry_run)
    retry_body = {
        "idempotency_key": f"retry-{uuid.uuid4().hex}",
        "expected_version": retry_run.lock_version,
    }
    retry_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{retry_run.id}/retry",
        headers=superuser_token_headers,
        json=retry_body,
    )
    assert retry_response.status_code == 200
    repeated_retry = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{retry_run.id}/retry",
        headers=superuser_token_headers,
        json=retry_body,
    )
    assert repeated_retry.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == retry_run.id,
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
            )
        ).one()
        == 1
    )


def test_resume_cancelled_run_requeues_current_stage_once(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    run.status = IngestionRunStatus.CANCELLED
    run.current_stage = IngestionStage.NATIVE_EXTRACTION
    run.error_details = {"reason": "Operator cancelled run"}
    step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NATIVE_EXTRACTION,
        )
    ).one()
    step.status = IngestionStepStatus.CANCELLED
    step.completed_at = datetime.now(UTC)
    db.add(run)
    db.add(step)
    db.commit()
    db.refresh(run)
    resume_body = {
        "idempotency_key": f"resume-{uuid.uuid4().hex}",
        "expected_version": run.lock_version,
    }

    resume_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )

    assert resume_response.status_code == 200
    db.refresh(run)
    db.refresh(step)
    assert run.status == IngestionRunStatus.QUEUED
    assert run.current_stage == IngestionStage.NATIVE_EXTRACTION
    assert step.status == IngestionStepStatus.PENDING
    assert step.completed_at is None
    tasks = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
        )
    ).all()
    assert len(tasks) == 1
    assert tasks[0].status == IngestionTaskStatus.PENDING
    assert tasks[0].payload == {
        "resume": True,
        "source_document_id": str(source.id),
    }

    repeated_resume = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/resume",
        headers=superuser_token_headers,
        json=resume_body,
    )

    assert repeated_resume.status_code == 200
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
            )
        ).one()
        == 1
    )
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionEvent)
            .where(
                IngestionEvent.run_id == run.id,
                IngestionEvent.event_type == "run_resumed",
            )
        ).one()
        == 1
    )


def test_review_item_revision_and_decision_enforce_blocking_issues(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to privacy",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Every citizen is entitled to privacy.",
        normalized_text="Every citizen is entitled to privacy.",
        source_page_start=2,
        source_page_end=2,
        parser_confidence=0.62,
        extractor_confidence=0.71,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=1,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="low_confidence",
        severity=ReviewIssueSeverity.BLOCKING,
        status=ReviewIssueStatus.OPEN,
        blocking=True,
        message="Parser confidence fell below the publication threshold",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    list_response = client.get(
        f"{settings.API_V1_STR}/admin/review-items"
        f"?issue=low_confidence&confidence_lte=0.75&page=2&path=section.37",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["data"]] == [str(candidate.id)]

    blocked_decision = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"decision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "decision": ReviewDecisionType.APPROVE,
            "reason": "Approved too early",
        },
    )
    assert blocked_decision.status_code == 409

    revision_key = f"review-{uuid.uuid4().hex}"
    revision_body = {
        "idempotency_key": revision_key,
        "expected_version": candidate.lock_version,
        "revised_text": "Every citizen is entitled to private and family life.",
        "reason": "Corrected extracted constitutional text.",
    }
    revision_response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json=revision_body,
    )
    assert revision_response.status_code == 200
    revised = revision_response.json()
    assert revised["latest_revision_text"] == (
        "Every citizen is entitled to private and family life."
    )
    assert revised["revision_number"] == 2
    repeated_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json=revision_body,
    )
    assert repeated_revision.status_code == 200
    assert repeated_revision.json()["revision_number"] == 2
    assert (
        db.exec(
            select(func.count())
            .select_from(CandidateRevision)
            .where(CandidateRevision.candidate_id == candidate.id)
        ).one()
        == 1
    )
    conflicting_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={**revision_body, "revised_text": "Different text with same key."},
    )
    assert conflicting_revision.status_code == 409
    assert conflicting_revision.json()["detail"] == (
        "Idempotency key was already used for a different request"
    )

    issue.status = ReviewIssueStatus.RESOLVED
    issue.resolved_by = _superuser(db).id
    issue.resolved_at = datetime.now(UTC)
    candidate.blocking_issue_count = 0
    db.add(issue)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    decision_key = f"decision-{uuid.uuid4().hex}"
    decision_body = {
        "idempotency_key": decision_key,
        "expected_version": candidate.lock_version,
        "decision": ReviewDecisionType.APPROVE,
        "reason": "Reviewed against source pages.",
    }
    decision_response = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json=decision_body,
    )

    assert decision_response.status_code == 200
    decided = decision_response.json()
    assert decided["status"] == ExtractionCandidateStatus.APPROVED
    assert decided["decisions"][0]["decision"] == ReviewDecisionType.APPROVE
    assert db.exec(
        select(ReviewDecisionRecord).where(
            ReviewDecisionRecord.candidate_id == candidate.id
        )
    ).one()
    repeated_decision = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json=decision_body,
    )
    assert repeated_decision.status_code == 200
    assert repeated_decision.json()["status"] == ExtractionCandidateStatus.APPROVED
    assert (
        db.exec(
            select(func.count())
            .select_from(ReviewDecisionRecord)
            .where(ReviewDecisionRecord.candidate_id == candidate.id)
        ).one()
        == 1
    )
    assert (
        db.exec(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(
                col(IdempotencyRecord.idempotency_key).in_([revision_key, decision_key])
            )
        ).one()
        == 2
    )


def test_review_revision_reruns_unit_validators_and_resolves_fixed_issue(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to privacy",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Every citizen is entitled to privacy.",
        normalized_text="Every citizen is entitled to privacy.",
        source_page_start=2,
        source_page_end=2,
        parser_confidence=0.9,
        extractor_confidence=0.9,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=0,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    bad_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"revision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "Every citizen is entitled to privacy (",
            "reason": "Testing correction validation",
        },
    )
    assert bad_revision.status_code == 200
    bad_payload = bad_revision.json()
    assert bad_payload["blocking_issue_count"] == 1
    assert [
        issue["issue_type"]
        for issue in bad_payload["issues"]
        if issue["status"] == ReviewIssueStatus.OPEN
    ] == ["revision_unbalanced_punctuation"]
    blocked_decision = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"decision-{uuid.uuid4().hex}",
            "expected_version": bad_payload["lock_version"],
            "decision": ReviewDecisionType.APPROVE,
            "reason": "Still malformed",
        },
    )
    assert blocked_decision.status_code == 409

    db.refresh(candidate)
    fixed_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"revision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "Every citizen is entitled to privacy.",
            "reason": "Fixed punctuation after validator rerun",
        },
    )

    assert fixed_revision.status_code == 200
    fixed_payload = fixed_revision.json()
    assert fixed_payload["blocking_issue_count"] == 0
    issue = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "revision_unbalanced_punctuation",
        )
    ).one()
    assert issue.status == ReviewIssueStatus.RESOLVED
    assert issue.resolved_by == _superuser(db).id
    assert issue.resolved_at is not None


def test_final_review_approval_requires_explicit_source_verification(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    review_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.REVIEW,
        )
    ).one()
    review_step.status = IngestionStepStatus.BLOCKED
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to privacy",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Every citizen is entitled to privacy.",
        normalized_text="every citizen is entitled to privacy.",
        source_page_start=2,
        source_page_end=2,
        source_spans=[
            {"page": 2, "bbox": {"x0": 36.0, "y0": 440.0, "x1": 220.0, "y1": 460.0}}
        ],
        parser_confidence=0.94,
        extractor_confidence=0.96,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=0,
    )
    db.add_all([run, review_step, candidate])
    db.commit()
    db.refresh(candidate)

    response = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"decision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "decision": ReviewDecisionType.APPROVE,
            "reason": "Reviewed against source pages.",
        },
    )

    assert response.status_code == 200
    db.refresh(source)
    db.refresh(run)
    db.refresh(review_step)
    assert source.verification_status == VerificationStatus.UNVERIFIED
    assert source.verified_by is None
    assert review_step.status == IngestionStepStatus.BLOCKED
    assert review_step.metrics == {
        "candidate_count": 1,
        "source_verification_required": True,
    }
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW
    assert (
        db.exec(
            select(IngestionTask).where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.MATERIALIZING.value,
            )
        ).first()
        is None
    )
    source_event = db.exec(
        select(IngestionEvent).where(
            IngestionEvent.run_id == run.id,
            IngestionEvent.event_type == "source_verification_required",
        )
    ).one()
    assert source_event.payload == {
        "candidate_count": 1,
        "source_document_id": str(source.id),
    }

    verification_body = {
        "idempotency_key": f"verify-source-{uuid.uuid4().hex}",
        "expected_version": source.lock_version,
        "reason": "Verified source URL, hash, and page evidence.",
    }
    verify_response = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=superuser_token_headers,
        json=verification_body,
    )

    assert verify_response.status_code == 200
    verify_payload = verify_response.json()
    assert verify_payload["verification_status"] == VerificationStatus.VERIFIED.value
    assert verify_payload["verified_by"] == str(_superuser(db).id)
    assert verify_payload["lock_version"] == 2
    repeated_verify = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=superuser_token_headers,
        json=verification_body,
    )
    assert repeated_verify.status_code == 200
    assert repeated_verify.json()["lock_version"] == 2
    db.refresh(source)
    db.refresh(run)
    db.refresh(review_step)
    assert source.verification_status == VerificationStatus.VERIFIED
    assert source.verified_by == _superuser(db).id
    assert review_step.status == IngestionStepStatus.SUCCEEDED
    assert run.status == IngestionRunStatus.QUEUED
    assert run.current_stage == IngestionStage.MATERIALIZING
    materializing_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.MATERIALIZING.value,
        )
    ).one()
    assert materializing_task.status == IngestionTaskStatus.PENDING
    event = db.exec(
        select(IngestionEvent).where(
            IngestionEvent.run_id == run.id,
            IngestionEvent.event_type == "review_completed",
        )
    ).one()
    assert event.payload == {"candidate_count": 1}
    audit_events = db.exec(
        select(AuditEvent).where(
            AuditEvent.action == "source_document.verified",
            AuditEvent.entity_id == source.id,
        )
    ).all()
    assert len(audit_events) == 1
    audit_event = audit_events[0]
    assert audit_event.actor_user_id == _superuser(db).id
    assert audit_event.payload == {
        "reason": "Verified source URL, hash, and page evidence."
    }


def test_source_document_verification_requires_legal_reviewer_role(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, _run = _source_and_run(db)

    response = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=normal_user_token_headers,
        json={
            "idempotency_key": f"verify-source-{uuid.uuid4().hex}",
            "expected_version": source.lock_version,
            "reason": "Verified source metadata.",
        },
    )

    assert response.status_code == 403


def test_release_validation_and_publish_require_selected_ready_index_and_two_people(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alias_calls: list[dict[str, str | None]] = []

    class FakeQdrantAdapter:
        def switch_alias(
            self,
            *,
            alias_name: str,
            new_collection_name: str,
            old_collection_name: str | None = None,
        ) -> None:
            alias_calls.append(
                {
                    "alias_name": alias_name,
                    "new_collection_name": new_collection_name,
                    "old_collection_name": old_collection_name,
                }
            )

    monkeypatch.setattr(
        "app.ingestion.service._qdrant_adapter", lambda: FakeQdrantAdapter()
    )
    release, vector_index = _release_bundle(db, uploader=_superuser(db))

    validate_key = f"validate-{uuid.uuid4().hex}"
    validate_body = {
        "idempotency_key": validate_key,
        "expected_version": release.lock_version,
    }
    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json=validate_body,
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["status"] == CorpusReleaseStatus.APPROVED
    assert validate_response.json()["validation_report"]["unresolved_gates"] == []
    db.refresh(release)
    validated_lock_version = release.lock_version

    repeated_validate = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json=validate_body,
    )
    assert repeated_validate.status_code == 200
    assert repeated_validate.json()["lock_version"] == validated_lock_version
    db.refresh(release)
    assert release.lock_version == validated_lock_version

    blocked_publish = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert blocked_publish.status_code == 409
    assert blocked_publish.json()["detail"] == (
        "Publisher must differ from the source uploader"
    )
    db.refresh(release)

    publish_key = f"publish-{uuid.uuid4().hex}"
    publish_body = {
        "idempotency_key": publish_key,
        "expected_version": release.lock_version,
        "superuser_override_reason": "Solo seeded superuser in route test",
    }
    publish_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json=publish_body,
    )

    assert publish_response.status_code == 200
    payload = publish_response.json()
    assert payload["release"]["status"] == CorpusReleaseStatus.PRODUCTION
    assert payload["promotion_status"] == "succeeded"
    assert payload["vector_index_status"] == VectorIndexStatus.PROMOTED
    assert alias_calls == [
        {
            "alias_name": vector_index.alias_name,
            "new_collection_name": vector_index.collection_name,
            "old_collection_name": None,
        }
    ]
    db.refresh(vector_index)
    assert vector_index.status == VectorIndexStatus.PROMOTED
    high_audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.action == "corpus_release.publish_override",
            AuditEvent.severity == AuditSeverity.HIGH,
        )
    ).first()
    assert high_audit
    promotion_count = db.exec(
        select(func.count())
        .select_from(ReleasePromotionAttempt)
        .where(ReleasePromotionAttempt.release_id == release.id)
    ).one()
    assert promotion_count == 1

    repeated_publish = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json=publish_body,
    )
    assert repeated_publish.status_code == 200
    assert repeated_publish.json()["promotion_status"] == "succeeded"
    assert (
        db.exec(
            select(func.count())
            .select_from(ReleasePromotionAttempt)
            .where(ReleasePromotionAttempt.release_id == release.id)
        ).one()
        == 1
    )
    assert (
        db.exec(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(
                col(IdempotencyRecord.idempotency_key).in_([validate_key, publish_key])
            )
        ).one()
        == 2
    )


def test_read_release_manifest_returns_retained_manifest_artifact(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    release, _vector_index = _release_bundle(db, uploader=_superuser(db))
    release_entry = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).one()
    manifest = {
        "release_id": str(release.id),
        "release_version": release.version,
        "source_documents": [
            {
                "id": str(release_entry.source_document_id),
                "title": "Official 1999 Constitution PDF",
                "authority": "Official Gazette",
                "sha256": "a" * 64,
                "page_count": 3,
            }
        ],
        "entries": [
            {
                "provision_version_id": str(release_entry.provision_version_id),
                "source_document_id": str(release_entry.source_document_id),
                "canonical_path": "constitution.1999.section.37",
                "source_page_start": 2,
                "source_page_end": 2,
            }
        ],
    }
    blob = LocalBlobStore(tmp_path).put_artifact(
        run_id=str(release_entry.ingestion_run_id),
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST.value,
        filename="release-manifest.json",
        content=json.dumps(manifest).encode(),
        content_type="application/json",
        metadata={
            "release_id": str(release.id),
            "source_manifest_hash": release.source_manifest_hash or "",
        },
    )
    artifact = IngestionArtifact(
        run_id=release_entry.ingestion_run_id,
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        artifact_metadata=blob.metadata,
    )
    db.add(artifact)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/manifest",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["release_id"] == str(release.id)
    assert payload["release_version"] == release.version
    assert payload["source_manifest_hash"] == release.source_manifest_hash
    assert payload["artifact"]["id"] == str(artifact.id)
    assert payload["manifest"]["source_documents"][0]["title"] == (
        "Official 1999 Constitution PDF"
    )
    assert payload["manifest"]["entries"][0]["canonical_path"] == (
        "constitution.1999.section.37"
    )


def test_read_release_manifest_404s_when_artifact_is_missing(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _vector_index = _release_bundle(db, uploader=_superuser(db))

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/manifest",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Release manifest artifact was not found"


def test_read_release_publication_evidence_returns_index_actor_and_promotion_history(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    uploader = _superuser(db)
    release, vector_index = _release_bundle(db, uploader=uploader)
    release.approved_by = uploader.id
    promotion = ReleasePromotionAttempt(
        release_id=release.id,
        vector_index_id=vector_index.id,
        requested_by=uploader.id,
        status=ReleasePromotionStatus.ROLLED_BACK,
        previous_release_id=None,
        previous_collection_name="law_padi_old",
        target_collection_name=vector_index.collection_name,
        rollback_completed=True,
        error_details={"phase": "database_promotion"},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    override = AuditEvent(
        actor_user_id=uploader.id,
        action="corpus_release.publish_override",
        entity_type="corpus_release",
        entity_id=release.id,
        severity=AuditSeverity.HIGH,
        reason="Solo superuser override for route test",
    )
    db.add_all([release, promotion, override])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publication-evidence",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["release_id"] == str(release.id)
    assert payload["vector_indexes"][0]["id"] == str(vector_index.id)
    assert payload["vector_indexes"][0]["validation_report"]["remote_point_count"] == 1
    assert payload["promotion_attempts"][0]["id"] == str(promotion.id)
    assert payload["promotion_attempts"][0]["status"] == (
        ReleasePromotionStatus.ROLLED_BACK
    )
    assert payload["promotion_attempts"][0]["rollback_completed"] is True
    assert payload["actor_separation"] == {
        "current_actor_id": str(uploader.id),
        "source_uploader_ids": [str(uploader.id)],
        "current_actor_is_source_uploader": True,
        "approved_by": str(uploader.id),
        "approved_by_differs_from_uploaders": False,
        "superuser_override_recorded": True,
        "override_reasons": ["Solo superuser override for route test"],
    }


def test_read_release_publication_evidence_requires_admin_role(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _vector_index = _release_bundle(db, uploader=_superuser(db))

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publication-evidence",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


def test_publish_release_fails_when_qdrant_alias_adapter_is_not_configured(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.ingestion.service.settings.QDRANT_URL", None)
    release, vector_index = _release_bundle(db, uploader=_superuser(db))
    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert validate_response.status_code == 200
    db.refresh(release)

    publish_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
            "superuser_override_reason": "Solo seeded superuser in route test",
        },
    )

    assert publish_response.status_code == 502
    assert publish_response.json()["detail"] == (
        "Qdrant alias switch failed; production release was not changed"
    )
    db.refresh(release)
    db.refresh(vector_index)
    assert release.status == CorpusReleaseStatus.APPROVED
    assert vector_index.status == VectorIndexStatus.READY
    promotion = db.exec(
        select(ReleasePromotionAttempt).where(
            ReleasePromotionAttempt.release_id == release.id
        )
    ).one()
    assert promotion.status == ReleasePromotionStatus.FAILED
    assert promotion.rollback_completed is False
    assert promotion.error_details
    assert promotion.error_details["phase"] == "qdrant_alias_switch"


def test_release_validation_rejects_ready_index_without_validation_evidence(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, vector_index = _release_bundle(db, uploader=_superuser(db))
    vector_index.validation_report = {"is_valid": True}
    db.add(vector_index)
    db.commit()
    db.refresh(release)

    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CorpusReleaseStatus.VALIDATING
    assert payload["validation_report"]["unresolved_gates"] == [
        "vector_index_remote_count_mismatch",
        "vector_index_smoke_queries_missing",
    ]


def test_release_validation_rejects_selected_embedding_below_recall_gate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _vector_index = _release_bundle(db, uploader=_superuser(db))
    embedding_run = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    embedding_run.recall_at_10 = 0.94
    db.add(embedding_run)
    db.commit()
    db.refresh(release)

    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CorpusReleaseStatus.VALIDATING
    assert payload["validation_report"]["unresolved_gates"] == [
        "selected_embedding_run_below_recall_threshold"
    ]


def test_release_validation_requires_active_retrieval_benchmark_dataset(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _vector_index = _release_bundle(db, uploader=_superuser(db))
    embedding_run = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    assert embedding_run.benchmark_dataset_version
    dataset = db.exec(
        select(EvaluationDataset).where(
            EvaluationDataset.version == embedding_run.benchmark_dataset_version
        )
    ).one()
    dataset.is_active = False
    db.add(dataset)
    db.commit()
    db.refresh(release)

    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CorpusReleaseStatus.VALIDATING
    assert payload["validation_report"]["benchmark_query_count"] == 0
    assert payload["validation_report"]["unresolved_gates"] == [
        "benchmark_dataset_missing_or_empty"
    ]


def test_publish_release_switches_qdrant_alias_when_adapter_is_configured(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alias_calls: list[dict[str, str | None]] = []

    class FakeQdrantAdapter:
        def switch_alias(
            self,
            *,
            alias_name: str,
            new_collection_name: str,
            old_collection_name: str | None = None,
        ) -> None:
            alias_calls.append(
                {
                    "alias_name": alias_name,
                    "new_collection_name": new_collection_name,
                    "old_collection_name": old_collection_name,
                }
            )

    monkeypatch.setattr(
        "app.ingestion.service._qdrant_adapter", lambda: FakeQdrantAdapter()
    )
    release, vector_index = _release_bundle(db, uploader=_superuser(db))
    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert validate_response.status_code == 200
    db.refresh(release)

    publish_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
            "superuser_override_reason": "Solo seeded superuser in route test",
        },
    )

    assert publish_response.status_code == 200
    assert alias_calls[-1]["alias_name"] == vector_index.alias_name
    assert alias_calls[-1]["new_collection_name"] == vector_index.collection_name
    db.refresh(vector_index)
    assert vector_index.status == VectorIndexStatus.PROMOTED


def test_publish_release_rolls_back_qdrant_alias_when_database_step_fails(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _retire_existing_production_release(db)
    previous_release, previous_index = _release_bundle(db, uploader=_superuser(db))
    previous_release.status = CorpusReleaseStatus.PRODUCTION
    previous_index.status = VectorIndexStatus.PROMOTED
    db.add(previous_release)
    db.add(previous_index)
    db.commit()
    target_release, target_index = _release_bundle(db, uploader=_superuser(db))
    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{target_release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": target_release.lock_version,
        },
    )
    assert validate_response.status_code == 200
    db.refresh(target_release)

    alias_calls: list[dict[str, str | None]] = []

    class FakeQdrantAdapter:
        def switch_alias(
            self,
            *,
            alias_name: str,
            new_collection_name: str,
            old_collection_name: str | None = None,
        ) -> None:
            alias_calls.append(
                {
                    "alias_name": alias_name,
                    "new_collection_name": new_collection_name,
                    "old_collection_name": old_collection_name,
                }
            )

        def delete_alias(self, *, alias_name: str, collection_name: str) -> None:
            alias_calls.append(
                {
                    "alias_name": alias_name,
                    "new_collection_name": None,
                    "old_collection_name": collection_name,
                }
            )

    def fail_database_promotion(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr(
        "app.ingestion.service._qdrant_adapter", lambda: FakeQdrantAdapter()
    )
    monkeypatch.setattr(
        "app.ingestion.service._mark_release_production_in_db",
        fail_database_promotion,
    )

    publish_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{target_release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": target_release.lock_version,
            "superuser_override_reason": "Solo seeded superuser in route test",
        },
    )

    assert publish_response.status_code == 500
    assert alias_calls == [
        {
            "alias_name": target_index.alias_name,
            "new_collection_name": target_index.collection_name,
            "old_collection_name": previous_index.collection_name,
        },
        {
            "alias_name": target_index.alias_name,
            "new_collection_name": previous_index.collection_name,
            "old_collection_name": target_index.collection_name,
        },
    ]
    db.refresh(previous_release)
    db.refresh(target_release)
    db.refresh(target_index)
    assert previous_release.status == CorpusReleaseStatus.PRODUCTION
    assert target_release.status == CorpusReleaseStatus.APPROVED
    assert target_index.status == VectorIndexStatus.READY
    promotion = db.exec(
        select(ReleasePromotionAttempt).where(
            ReleasePromotionAttempt.release_id == target_release.id
        )
    ).one()
    assert promotion.status == ReleasePromotionStatus.ROLLED_BACK
    assert promotion.rollback_completed is True
    assert promotion.error_details
    assert promotion.error_details["phase"] == "database_promotion"
    assert db.exec(
        select(AuditEvent).where(
            AuditEvent.action == "corpus_release.publish_failed",
            AuditEvent.entity_id == target_release.id,
        )
    ).one()


def _complete_pdf_upload(
    client: TestClient,
    headers: dict[str, str],
    db: Session,
    pdf: bytes,
) -> dict[str, object]:
    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=headers,
        json=_source_upload_payload(pdf),
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert (
        client.put(
            upload["upload_url"],
            headers={**headers, "content-type": "application/pdf"},
            content=pdf,
        ).status_code
        == 204
    )
    stored_upload = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert stored_upload
    db.refresh(stored_upload)
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": stored_upload.lock_version,
            "actual_sha256": _sha256(pdf),
        },
    )
    assert complete_response.status_code == 200
    return complete_response.json()


def _source_upload_payload(
    content: bytes,
    *,
    idempotency_key: str | None = None,
    slug: str | None = None,
    mime_type: str = "application/pdf",
    expected_size: int | None = None,
) -> dict[str, object]:
    source_slug = slug or f"constitution-1999-{uuid.uuid4().hex}"
    return {
        "idempotency_key": idempotency_key or f"upload-{uuid.uuid4().hex}",
        "expected_size": expected_size or len(content),
        "expected_sha256": _sha256(content),
        "original_filename": "constitution.pdf",
        "mime_type": mime_type,
        "instrument_slug": source_slug,
        "instrument_title": "Constitution of the Federal Republic of Nigeria 1999",
        "instrument_short_title": "CFRN 1999",
        "instrument_year": 1999,
        "instrument_status": InstrumentStatus.ENACTED,
        "enacted_at": date(1999, 5, 29).isoformat(),
        "effective_at": date(1999, 5, 29).isoformat(),
        "source_title": f"{source_slug} official PDF",
        "authority": "Official Gazette",
        "source_url": f"https://example.test/{source_slug}.pdf",
        "source_tier": SourceTier.OFFICIAL,
        "published_at": date(1999, 5, 29).isoformat(),
        "retrieved_at": date.today().isoformat(),
    }


class _ManagedLocalBlobStore(LocalBlobStore):
    def __init__(self, root: object) -> None:
        super().__init__(root)
        self.presigned_put_calls: list[dict[str, object]] = []
        self.multipart_calls: list[dict[str, object]] = []

    def create_presigned_put_url(
        self,
        *,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
        expires_in_seconds: int,
    ) -> str:
        self.presigned_put_calls.append(
            {
                "key": key,
                "content_type": content_type,
                "metadata": metadata,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return f"https://r2.example.test/{key}?signed=put"

    def create_multipart_upload(
        self,
        *,
        key: str,
        content_type: str,
        part_count: int,
        metadata: dict[str, str] | None = None,
        expires_in_seconds: int,
    ) -> MultipartUpload:
        self.multipart_calls.append(
            {
                "key": key,
                "content_type": content_type,
                "part_count": part_count,
                "metadata": metadata,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return MultipartUpload(
            upload_id="managed-multipart-1",
            parts=tuple(
                MultipartUploadPartUrl(
                    part_number=part_number,
                    upload_url=f"https://r2.example.test/{key}?partNumber={part_number}",
                )
                for part_number in range(1, part_count + 1)
            ),
        )

    def complete_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[object],
    ) -> object:
        return self.head(key)

    def abort_multipart_upload(self, *, key: str, upload_id: str) -> None:
        return None


def _pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


def _unique_pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": f"constitution-{uuid.uuid4().hex}"})
    writer.write(output)
    return output.getvalue()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_text(content: str) -> str:
    return _sha256(content.encode())


def _superuser(db: Session) -> User:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    return user


def _source_and_run(
    db: Session, *, created_by: uuid.UUID | None = None
) -> tuple[SourceDocument, IngestionRun]:
    instrument = LegalInstrument(
        slug=f"constitution-direct-{uuid.uuid4().hex}",
        title="Constitution of the Federal Republic of Nigeria 1999",
        short_title="CFRN 1999",
        instrument_type=InstrumentType.CONSTITUTION,
        jurisdiction="NG",
        year=1999,
        status=InstrumentStatus.ENACTED,
        enacted_at=date(1999, 5, 29),
        effective_at=date(1999, 5, 29),
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Official Gazette",
        title=f"Source {uuid.uuid4().hex}",
        source_url=f"https://example.test/source-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        sha256=_sha256(uuid.uuid4().bytes),
        storage_backend="local",
        storage_key=f"originals/sha256/{uuid.uuid4().hex}.pdf",
        original_filename="constitution.pdf",
        file_size=128,
        page_count=3,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
        source_tier=SourceTier.OFFICIAL,
        created_by=created_by,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    run = IngestionRun(
        source_document_id=source.id,
        created_by=created_by,
        status=IngestionRunStatus.WAITING_FOR_INPUT,
        current_stage=IngestionStage.AWAITING_PAGE_CONFIRMATION,
        pipeline_config={"instrument_parser": "constitution"},
        expected_page_count=source.page_count,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    create_run_steps(db, run)
    return source, run


def _retire_existing_production_release(db: Session) -> None:
    releases = db.exec(
        select(CorpusRelease).where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION
        )
    ).all()
    for release in releases:
        release.status = CorpusReleaseStatus.RETIRED
        release.lock_version += 1
        db.add(release)
    db.commit()


def _release_bundle(
    db: Session, *, uploader: User
) -> tuple[CorpusRelease, VectorIndex]:
    source, run = _source_and_run(db, created_by=uploader.id)
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    text = "The privacy of citizens, their homes and correspondence is guaranteed."
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=text,
        valid_from=date(1999, 5, 29),
        source_document_id=source.id,
        source_page_start=2,
        source_page_end=2,
        text_sha256=_sha256_text(text),
    )
    release = CorpusRelease(
        version=f"test-release-{uuid.uuid4().hex}",
        status=CorpusReleaseStatus.BUILDING,
        source_manifest_hash=_sha256_text(str(uuid.uuid4())),
        parser_version="constitution-parser-v1",
    )
    benchmark_dataset_version = f"golden-{uuid.uuid4().hex}"
    benchmark_dataset = EvaluationDataset(
        version=benchmark_dataset_version,
        name="Nigerian Constitution retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        language="en",
        jurisdiction="NG",
        source_document_id=source.id,
        content_sha256=_sha256_text(benchmark_dataset_version),
    )
    profile = EmbeddingProfile(
        name=f"openai-small-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="text-embedding-3-small",
        vector_dimensions=1536,
        configuration={
            "chunking": "provision",
            "benchmark_dataset_version": benchmark_dataset_version,
        },
    )
    db.add_all([version, release, benchmark_dataset, profile])
    db.commit()
    db.refresh(version)
    db.refresh(release)
    db.refresh(benchmark_dataset)
    db.refresh(profile)
    db.add(
        EvaluationItem(
            dataset_id=benchmark_dataset.id,
            item_key="privacy-exact-reference",
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            query_text="Which section protects privacy?",
            expected_canonical_paths=[provision.canonical_path],
        )
    )
    entry = CorpusReleaseEntry(
        release_id=release.id,
        provision_version_id=version.id,
        source_document_id=source.id,
        ingestion_run_id=run.id,
    )
    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        status=EmbeddingRunStatus.SUCCEEDED,
        benchmark_dataset_version=benchmark_dataset_version,
        recall_at_10=0.96,
        ndcg_at_10=0.94,
        selected_for_release=True,
    )
    db.add_all([entry, embedding_run])
    db.commit()
    db.refresh(embedding_run)
    vector_index = VectorIndex(
        release_id=release.id,
        embedding_run_id=embedding_run.id,
        profile_id=profile.id,
        collection_name=f"law_padi_test_{uuid.uuid4().hex}",
        status=VectorIndexStatus.READY,
        point_count=1,
        vector_dimensions=1536,
        payload_schema_hash=_sha256_text("payload-schema-v1"),
        checksum=_sha256_text("vector-checksum"),
        validation_report={
            "is_valid": True,
            "duplicate_ids": [],
            "dimension_errors": [],
            "payload_errors": [],
            "remote_point_count": 1,
            "smoke_queries": [
                {
                    "expected_point_id": "point-1",
                    "hit_ids": ["point-1"],
                    "matched_payload": True,
                    "passed": True,
                }
            ],
        },
    )
    db.add(vector_index)
    db.commit()
    db.refresh(release)
    db.refresh(vector_index)
    return release, vector_index
