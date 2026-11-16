import hashlib
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlmodel import Session, col, delete, func, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.ingestion import LocalBlobStore, MultipartUpload, MultipartUploadPartUrl
from app.ingestion.pgvector_repository import (
    validate_index_build,
    write_embeddings,
    write_segments,
)
from app.ingestion.retrieval import build_retrieval_documents
from app.ingestion.service import update_page_selection
from app.ingestion.worker import run_until_idle
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
    RetrievalIndexBuild,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    VectorIndex,
)
from app.legal.schemas import PageSelectionUpdate
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
    release, build = _release_bundle(db, uploader=admin)
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
        retrieval_index_build_id=build.id,
        requested_by=admin.id,
        status=ReleasePromotionStatus.FAILED,
        error_details={"message": "Publication transaction failed."},
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


@pytest.mark.parametrize("backend", ["local", "r2"])
def test_source_upload_mutations_and_replays_require_the_owner(
    client: TestClient,
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
) -> None:
    def uploader_headers() -> dict[str, str]:
        email = random_email()
        headers = authentication_token_from_email(client=client, email=email, db=db)
        user = crud.get_user_by_email(session=db, email=email)
        assert user is not None
        db.add(
            AdminRoleAssignment(
                user_id=user.id, role=AdminRole.INGESTION_UPLOADER, reason="route test"
            )
        )
        db.commit()
        return headers

    owner = uploader_headers()
    other = uploader_headers()
    monkeypatch.setattr(settings, "INGESTION_STORAGE_BACKEND", backend)
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    store = _ManagedLocalBlobStore(tmp_path)
    if backend == "r2":
        monkeypatch.setattr("app.ingestion.service.get_blob_store", lambda: store)
    base = f"{settings.API_V1_STR}/admin"
    pdf = _unique_pdf_bytes()
    body = _source_upload_payload(pdf)
    response = client.post(f"{base}/source-uploads", headers=owner, json=body)
    assert response.status_code == 200
    upload = response.json()
    upload_url = f"{base}/source-uploads/{upload['id']}"
    assert (
        client.post(f"{base}/source-uploads", headers=other, json=body).status_code
        == 404
    )
    if backend == "local":
        assert (
            client.put(
                f"{upload_url}/object",
                headers={**owner, "content-type": "application/pdf"},
                content=pdf,
            ).status_code
            == 204
        )
    else:
        store.put_quarantine(
            upload_id=upload["id"],
            filename="constitution.pdf",
            content=pdf,
            content_type="application/pdf",
        )
        parts_body = {
            "idempotency_key": f"parts-{uuid.uuid4().hex}",
            "expected_version": upload["lock_version"],
            "part_count": 1,
        }
        assert (
            client.post(
                f"{upload_url}/multipart-parts",
                headers=other,
                json=parts_body,
            ).status_code
            == 404
        )
        assert not store.multipart_calls
        assert len(store.presigned_put_calls) == 1
    complete_body = {
        "idempotency_key": f"complete-{uuid.uuid4().hex}",
        "expected_version": upload["lock_version"] + (backend == "local"),
        "actual_sha256": _sha256(pdf),
    }
    assert (
        client.post(
            f"{upload_url}/complete",
            headers=other,
            json=complete_body,
        ).status_code
        == 404
    )
    complete = client.post(f"{upload_url}/complete", headers=owner, json=complete_body)
    assert complete.status_code == 200
    assert complete.json()["upload"]["upload_url"] == ""
    assert (
        client.post(
            f"{upload_url}/complete",
            headers=other,
            json=complete_body,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{upload_url}/complete",
            headers=owner,
            json=complete_body,
        ).json()["run"]["id"]
        == complete.json()["run"]["id"]
    )
    listed = client.get(f"{base}/ingestion-runs", headers=other).json()["data"]
    victim = next(row for row in listed if row["source_upload_id"] == upload["id"])
    size = victim["pipeline_config"]["expected_size"]
    for headers, expected in ((other, 404), (owner, 409)):
        assert (
            client.put(
                f"{base}/source-uploads/{victim['source_upload_id']}/object",
                headers={**headers, "content-type": "application/pdf"},
                content=b"b" * size,
            ).status_code
            == expected
        )
    assert store.read_bytes(upload["quarantine_key"]) == pdf
    record = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert record is not None
    db.refresh(record)
    assert record.status == SourceUploadStatus.UPLOADED_PENDING_VERIFICATION
    assert record.lock_version == complete.json()["upload"]["lock_version"]
    task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == uuid.UUID(complete.json()["run"]["id"])
        )
    ).one()
    task.status = IngestionTaskStatus.CANCELLED
    db.add(task)
    db.commit()


def test_embedding_profile_routes_reject_publisher_endpoint_overrides(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{settings.API_V1_STR}/admin/embedding-profiles"
    profile = {
        "name": f"override-{uuid.uuid4().hex}",
        "provider": "huggingface_tei",
        "model_name": "dummy-model",
        "model_revision": "pinned",
        "is_active": False,
    }
    override = {"configuration": {"endpoint_url": "https://audit.invalid/embed"}}
    assert (
        client.post(
            url, headers=superuser_token_headers, json=profile | override
        ).status_code
        == 422
    )
    created = client.post(url, headers=superuser_token_headers, json=profile)
    assert created.status_code == 201
    assert (
        client.patch(
            f"{url}/{created.json()['id']}",
            headers=superuser_token_headers,
            json=override,
        ).status_code
        == 422
    )


def test_pdf_upload_session_completion_keeps_source_in_quarantine_until_worker_verification(
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
    assert (
        payload["upload"]["status"] == SourceUploadStatus.UPLOADED_PENDING_VERIFICATION
    )
    assert payload["source_document"] is None
    assert payload["run"]["status"] == IngestionRunStatus.QUEUED
    assert payload["run"]["current_stage"] == IngestionStage.VERIFYING_UPLOAD
    run_id = uuid.UUID(payload["run"]["id"])
    repeated_complete = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json=complete_body,
    )
    assert repeated_complete.status_code == 200
    assert repeated_complete.json()["source_document"] is None
    assert repeated_complete.json()["run"]["id"] == payload["run"]["id"]
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionRun)
            .where(IngestionRun.source_upload_id == uuid.UUID(upload["id"]))
        ).one()
        == 1
    )

    run = db.get(IngestionRun, run_id)
    assert run
    assert run.source_document_id is None
    assert (tmp_path / upload["quarantine_key"]).exists()
    assert not list(tmp_path.glob("sources/sha256/*/original.pdf"))

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

    with client.stream(
        "GET",
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run_id}/events?replay_only=true",
        headers={**superuser_token_headers, "Last-Event-ID": "0"},
    ) as replay_response:
        assert replay_response.status_code == 200
        replay_text = next(replay_response.iter_text())
        assert "upload_completed" in replay_text
        assert "id: 1" in replay_text


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

    with client.stream(
        "GET",
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/events?replay_only=true",
        headers={
            **superuser_token_headers,
            "Last-Event-ID": str(first_event.sequence),
        },
    ) as response:
        assert response.status_code == 200
        response_text = next(response.iter_text())
        assert f"id: {second_event.sequence}" in response_text
        assert "stage_succeeded" in response_text
        assert "Profiling completed" in response_text
        assert f"id: {first_event.sequence}" not in response_text
        assert "Profiling started" not in response_text


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
    assert (
        payload["upload"]["status"] == SourceUploadStatus.UPLOADED_PENDING_VERIFICATION
    )
    assert payload["source_document"] is None


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


def test_worker_reuses_existing_source_for_duplicate_pdf(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_bytes()
    first = _complete_pdf_upload(client, superuser_token_headers, db, pdf)
    first_run = db.get(IngestionRun, uuid.UUID(str(first["run"]["id"])))
    assert first_run
    db.expire_all()
    run_until_idle(db, worker_id="upload-test", max_tasks=100)
    first_upload = db.get(SourceUpload, uuid.UUID(str(first["upload"]["id"])))
    assert first_upload
    db.refresh(first_upload)
    assert first_upload.source_document_id is not None

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
    assert payload["duplicate"] is False
    assert payload["run"] is not None
    assert payload["source_document"] is None
    second_run = db.get(IngestionRun, uuid.UUID(payload["run"]["id"]))
    assert second_run
    run_until_idle(db, worker_id="upload-test", max_tasks=100)
    db.refresh(stored_upload)
    assert stored_upload.status == SourceUploadStatus.DUPLICATE
    assert stored_upload.source_document_id == first_upload.source_document_id


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
    assert "PDF sources only" in response.text


def test_worker_rejects_corrupt_pdf_and_keeps_it_out_of_canonical_storage(
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

    assert complete_response.status_code == 200
    db.refresh(stored_upload)
    assert stored_upload.status == SourceUploadStatus.UPLOADED_PENDING_VERIFICATION
    db.expire_all()
    run_until_idle(db, worker_id="upload-test", max_tasks=100)
    db.refresh(stored_upload)
    assert stored_upload.status == SourceUploadStatus.FAILED
    assert not db.exec(
        select(SourceDocument).where(SourceDocument.sha256 == _sha256(content))
    ).first()
    assert (tmp_path / stored_upload.quarantine_key).exists()


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
    run.status = IngestionRunStatus.WAITING_FOR_INPUT
    run.current_stage = IngestionStage.AWAITING_PAGE_CONFIRMATION
    db.add(run)
    db.commit()
    for page_item in pages:
        db.refresh(page_item)

    selection_body = {
        "idempotency_key": f"pages-{uuid.uuid4().hex}",
        "expected_run_version": run.lock_version,
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
    assert run.current_stage == IngestionStage.NATIVE_EXTRACTION
    native_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
        )
    ).one()
    assert native_task.status == IngestionTaskStatus.PENDING
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
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
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


def test_concurrent_page_selection_has_one_winner_and_one_conflict(
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=1,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
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
    for page in pages:
        db.refresh(page)
    expected_run_version = run.lock_version
    expected_page_versions = {page.page_number: page.lock_version for page in pages}
    admin = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert admin
    barrier = threading.Barrier(2)

    def confirm_once(index: int) -> int:
        with Session(engine) as concurrent_session:
            current_user = concurrent_session.get(User, admin.id)
            assert current_user
            body = PageSelectionUpdate(
                idempotency_key=f"concurrent-pages-{index}-{uuid.uuid4().hex}",
                expected_run_version=expected_run_version,
                pages=[
                    {
                        "page_number": page_number,
                        "inclusion_status": PageInclusionStatus.INCLUDED,
                        "inclusion_reason": "Concurrent confirmation test",
                        "expected_version": expected_page_versions[page_number],
                    }
                    for page_number in sorted(expected_page_versions)
                ],
            )
            barrier.wait()
            try:
                update_page_selection(concurrent_session, run.id, body, current_user)
            except HTTPException as exc:
                concurrent_session.rollback()
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(confirm_once, range(2)))

    assert sorted(statuses) == [200, 409]
    db.expire_all()
    db.refresh(run)
    assert run.current_stage == IngestionStage.NATIVE_EXTRACTION
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
    db.refresh(resume_run)
    assert resume_run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert resume_run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
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
                IngestionEvent.event_type == "run_resume_not_required",
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


def test_retry_keeps_the_failed_stage_task_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _source, run = _source_and_run(db)
    run.status = IngestionRunStatus.FAILED
    run.current_stage = IngestionStage.EMBEDDING
    release_id = str(uuid.uuid4())
    db.add(run)
    db.add(
        IngestionTask(
            run_id=run.id,
            task_type=IngestionStage.EMBEDDING.value,
            status=IngestionTaskStatus.FAILED,
            idempotency_key=f"{run.id}:embedding:manual",
            payload={"release_id": release_id, "source_document_id": "source"},
            created_at=datetime(2026, 10, 23, 10, 0, tzinfo=UTC),
        )
    )
    # A later retry that held only the flag must not hide the stage's inputs.
    db.add(
        IngestionTask(
            run_id=run.id,
            task_type=IngestionStage.EMBEDDING.value,
            status=IngestionTaskStatus.FAILED,
            idempotency_key=f"{run.id}:embedding:retry:old",
            payload={"retry": True},
            created_at=datetime(2026, 10, 23, 11, 0, tzinfo=UTC),
        )
    )
    db.commit()
    db.refresh(run)

    response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/retry",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"retry-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
        },
    )

    assert response.status_code == 200
    retry_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.status == IngestionTaskStatus.PENDING,
        )
    ).one()
    assert retry_task.payload == {
        "release_id": release_id,
        "source_document_id": "source",
        "retry": True,
    }


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


def test_resume_cancelled_page_confirmation_reopens_admin_gate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    page = SourcePage(
        run_id=run.id,
        source_document_id=source.id,
        page_number=1,
        role=PageRole.LEGAL_BODY,
        inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        inclusion_reason="Suggested legal body page",
    )
    db.add(page)
    db.commit()
    db.refresh(run)
    db.refresh(page)
    awaiting_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.AWAITING_PAGE_CONFIRMATION,
        )
    ).one()

    cancel_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/cancel",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"cancel-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
            "reason": "Operator cancelled run",
        },
    )
    assert cancel_response.status_code == 200
    db.refresh(run)
    db.refresh(awaiting_step)
    assert run.status == IngestionRunStatus.CANCELLED
    assert awaiting_step.status == IngestionStepStatus.CANCELLED

    resume_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/resume",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"resume-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
        },
    )
    assert resume_response.status_code == 200
    db.refresh(run)
    db.refresh(awaiting_step)
    assert run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    assert run.error_details is None
    assert run.completed_at is None
    assert awaiting_step.status == IngestionStepStatus.BLOCKED
    assert awaiting_step.completed_at is None
    assert not db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.AWAITING_PAGE_CONFIRMATION.value,
        )
    ).first()

    page_selection_response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"pages-{uuid.uuid4().hex}",
            "expected_run_version": run.lock_version,
            "pages": [
                {
                    "page_number": page.page_number,
                    "inclusion_status": PageInclusionStatus.INCLUDED,
                    "inclusion_reason": "Confirmed legal body page",
                    "expected_version": page.lock_version,
                }
            ],
        },
    )
    assert page_selection_response.status_code == 200


def test_imported_review_boundaries_preserve_review_and_block_excluded_text(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    run.pipeline_config = {
        "review_import_complete": True,
        "provisional_page_boundaries": True,
    }
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=number,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        )
        for number in range(1, 4)
    ]
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="142",
        canonical_path=f"boundaries-{uuid.uuid4().hex}.section142",
        sort_key="142",
        raw_text="Citation sentence. Authentication text.",
        source_page_start=2,
        source_page_end=3,
        source_spans=[
            {"page_number": 2, "text": "Citation sentence."},
            {"page_number": 3, "text": "Authentication text."},
        ],
    )
    db.add_all([run, *pages, candidate])
    db.commit()
    boundary_issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="provisional_page_boundaries",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Confirm imported boundaries",
    )
    db.add(boundary_issue)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"boundaries-{uuid.uuid4().hex}",
            "expected_run_version": run.lock_version,
            "pages": [
                {
                    "page_number": page.page_number,
                    "expected_version": page.lock_version,
                    "inclusion_status": "included"
                    if page.page_number == 2
                    else "excluded",
                    "inclusion_reason": "Checked legal body against front and authentication matter.",
                }
                for page in pages
            ],
        },
    )
    assert response.status_code == 200
    db.expire_all()
    retained_run = db.get(IngestionRun, run.id)
    assert retained_run and retained_run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert retained_run.current_stage == IngestionStage.REVIEW
    assert retained_run.pipeline_config["provisional_page_boundaries"] is False
    assert db.get(ReviewIssue, boundary_issue.id).status == ReviewIssueStatus.RESOLVED
    excluded = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "excluded_source_page",
        )
    ).one()
    assert excluded.status == ReviewIssueStatus.OPEN
    assert not db.exec(
        select(IngestionTask).where(IngestionTask.run_id == run.id)
    ).all()
    retained_candidate = db.get(ExtractionCandidate, candidate.id)
    assert retained_candidate
    fixed = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"repair-{uuid.uuid4().hex}",
            "expected_version": retained_candidate.lock_version,
            "source_page_end": 2,
            "source_spans": [{"page_number": 2, "text": "Citation sentence."}],
            "revised_text": "Citation sentence.",
            "reason": "Removed authentication material from the provision mapping.",
        },
    )
    assert fixed.status_code == 200
    assert (
        next(
            issue
            for issue in fixed.json()["issues"]
            if issue["issue_type"] == "excluded_source_page"
        )["status"]
        == "resolved"
    )
    assert fixed.json()["source_document"]["verification_status"] != "verified"


def test_recover_missing_provision_preserves_origin_and_requires_review(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    original = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="142",
        canonical_path=f"recovery-{uuid.uuid4().hex}.section142",
        sort_key="142",
        raw_text="Citation sentence.\nSCHEDULE\nSchedule wording.",
        source_page_start=1,
        source_page_end=3,
    )
    db.add(original)
    db.commit()
    body = {
        "idempotency_key": f"recover-{uuid.uuid4().hex}",
        "expected_version": 1,
        "kind": "schedule",
        "number": "1",
        "heading": "SCHEDULE",
        "canonical_path": original.canonical_path.replace("section142", "schedule1"),
        "sort_key": "143",
        "source_page_start": 3,
        "source_page_end": 3,
        "source_spans": [
            {
                "page_number": 3,
                "text": "Schedule wording.",
                "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
            }
        ],
        "revised_text": "Schedule wording.",
        "reason": "Recovered the separate Schedule from the source scan.",
    }
    endpoint = f"{settings.API_V1_STR}/admin/review-items/{original.id}/derived-items"
    response = client.post(endpoint, headers=superuser_token_headers, json=body)
    assert response.status_code == 200
    recovered = response.json()
    assert recovered["id"] != str(original.id)
    assert recovered["status"] == "needs_review"
    assert recovered["kind"] == "schedule"
    assert recovered["raw_text"] == original.raw_text
    assert recovered["latest_revision_text"] == "Schedule wording."
    assert recovered["source_document"]["verification_status"] != "verified"
    assert (
        recovered["revisions"][0]["before_snapshot"]["canonical_path"]
        == original.canonical_path
    )
    assert recovered["revisions"][0]["changed_fields"][
        "derived_from_candidate_id"
    ] == str(original.id)
    repeated = client.post(endpoint, headers=superuser_token_headers, json=body)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == recovered["id"]
    duplicate = client.post(
        endpoint,
        headers=superuser_token_headers,
        json={**body, "idempotency_key": f"new-key-{uuid.uuid4().hex}"},
    )
    assert duplicate.status_code == 409
    db.expire_all()
    retained = db.get(ExtractionCandidate, original.id)
    assert retained and retained.lock_version == 1
    assert retained.raw_text == "Citation sentence.\nSCHEDULE\nSchedule wording."
    assert db.exec(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(recovered["id"]),
            AuditEvent.action == "review_item.derived",
        )
    ).first()


@pytest.mark.parametrize("kind", ["part", "chapter", "cross_heading", "section"])
def test_recovered_structure_does_not_inherit_origin_body(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    kind: str,
) -> None:
    source, run = _source_and_run(db)
    original = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        canonical_path=f"structural-{uuid.uuid4().hex}.section1",
        sort_key="001",
        raw_text="Original section body.",
        source_page_start=1,
        source_page_end=1,
    )
    db.add(original)
    db.commit()
    body = {
        "idempotency_key": f"recover-{uuid.uuid4().hex}",
        "expected_version": 1,
        "kind": kind,
        "heading": "PRINTED STRUCTURAL HEADING",
        "canonical_path": original.canonical_path.replace("section1", "structure"),
        "sort_key": "002",
        "source_page_start": 1,
        "source_page_end": 1,
        "source_spans": [{"page_number": 1, "text": "PRINTED STRUCTURAL HEADING"}],
        "reason": "Recover a printed structural heading without inventing body text.",
    }
    blank_heading = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{original.id}/derived-items",
        headers=superuser_token_headers,
        json={**body, "heading": "   "},
    )
    assert blank_heading.status_code == 422
    response = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{original.id}/derived-items",
        headers=superuser_token_headers,
        json=body,
    )
    if kind == "section":
        assert response.status_code == 422
        return
    assert response.status_code == 200
    recovered = response.json()
    assert recovered["raw_text"] is None
    assert recovered["latest_revision_text"] is None
    assert recovered["status"] == "needs_review"
    assert recovered["revisions"][0]["previous_text"] == original.raw_text
    assert (
        recovered["revisions"][0]["before_snapshot"]["revised_text"]
        == original.raw_text
    )


def test_review_structure_patch_preserves_raw_and_audits_nullable_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="14",
        heading="Wrong heading",
        canonical_path=f"review-{uuid.uuid4().hex}.section14",
        sort_key="0014",
        raw_text="In this Act:",
        source_page_start=1,
        source_page_end=3,
    )
    db.add(candidate)
    db.commit()
    original = candidate.canonical_path
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"structure-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "number": "141",
            "heading": "Interpretation",
            "canonical_path": original.replace("section14", "section141"),
            "source_page_start": 2,
            "source_page_end": 3,
            "reason": "Compared the section marker and heading with the original scan.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["number"] == "141"
    assert payload["heading"] == "Interpretation"
    assert payload["raw_text"] == "In this Act:"
    assert payload["latest_revision_text"] == "In this Act:"
    assert payload["revisions"][0]["before_snapshot"]["number"] == "14"
    assert payload["revisions"][0]["after_snapshot"]["number"] == "141"
    clear = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"clear-{uuid.uuid4().hex}",
            "expected_version": payload["lock_version"],
            "heading": None,
            "reason": "Remove an unsupported heading pending source review.",
        },
    )
    assert clear.status_code == 200
    assert clear.json()["heading"] is None
    parent = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.PART,
        canonical_path=f"review-parent-{uuid.uuid4().hex}",
        sort_key="0013",
        heading="Printed Part heading",
        source_page_start=2,
        source_page_end=2,
    )
    db.add(parent)
    db.commit()
    reparented = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"reparent-{uuid.uuid4().hex}",
            "expected_version": clear.json()["lock_version"],
            "parent_candidate_id": str(parent.id),
            "reason": "Recover the distinct printed parent structure.",
        },
    )
    assert reparented.status_code == 200
    assert reparented.json()["parent_candidate_id"] == str(parent.id)
    latest = max(
        reparented.json()["revisions"], key=lambda item: item["revision_number"]
    )
    assert latest["changed_fields"]["parent_candidate_id"] == str(parent.id)


@pytest.mark.parametrize(
    "invalid",
    [
        "duplicate",
        "cycle",
        "foreign_parent",
        "page_range",
        "span_range",
        "materialized",
    ],
)
def test_review_structure_patch_rejects_invalid_graph_changes(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    invalid: str,
) -> None:
    source, run = _source_and_run(db)
    other_source, other_run = _source_and_run(db)
    prefix = f"review-{uuid.uuid4().hex}"
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="1",
        canonical_path=f"{prefix}.section1",
        sort_key="001",
        raw_text="Original wording.",
        source_page_start=2,
        source_page_end=3,
    )
    sibling = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="2",
        canonical_path=f"{prefix}.section2",
        sort_key="002",
    )
    foreign = ExtractionCandidate(
        run_id=other_run.id,
        source_document_id=other_source.id,
        kind=ProvisionKind.SECTION,
        number="3",
        canonical_path=f"{prefix}.section3",
        sort_key="003",
    )
    db.add_all([candidate, sibling, foreign])
    db.commit()
    patches: dict[str, dict[str, object]] = {
        "duplicate": {"canonical_path": sibling.canonical_path},
        "cycle": {"parent_candidate_id": str(candidate.id)},
        "foreign_parent": {"parent_candidate_id": str(foreign.id)},
        "page_range": {"source_page_start": 4},
        "span_range": {"source_spans": [{"page_number": 1, "text": "outside range"}]},
        "materialized": {"heading": "Cannot alter a materialized candidate"},
    }
    if invalid == "materialized":
        candidate.status = ExtractionCandidateStatus.MATERIALIZED
        db.add(candidate)
        db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"invalid-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "reason": "Attempt invalid structure edit",
            **patches[invalid],
        },
    )
    assert response.status_code in {409, 422}
    db.expire_all()
    retained = db.get(ExtractionCandidate, candidate.id)
    assert retained
    assert retained.canonical_path == f"{prefix}.section1"
    assert retained.lock_version == 1
    assert not db.exec(
        select(CandidateRevision).where(CandidateRevision.candidate_id == candidate.id)
    ).all()


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


@pytest.mark.parametrize("source_matches", [True, False])
def test_revision_revalidates_original_coverage_without_waiving_unrelated_issues(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    source_matches: bool,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        canonical_path=f"constitution.1999.section37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Each Secretariat shall su bmit a Report.",
        source_page_start=2,
        source_page_end=2,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=2,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    coverage = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="source_span_coverage",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Source coverage",
    )
    unrelated = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="graph_numbering_gap",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Numbering gap",
    )
    db.add_all([coverage, unrelated])
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"formatting-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "Each Secretariat shall submit a Report.",
            "source_spans": [
                {
                    "text": "Each Secretariat shall su bmit a Report."
                    if source_matches
                    else "An unrelated paragraph.",
                    "page_number": 2,
                    "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                }
            ],
            "reason": "Whitespace-only source-verified revision",
        },
    )
    assert response.status_code == 200
    db.refresh(coverage)
    db.refresh(unrelated)
    db.refresh(candidate)
    assert candidate.raw_text == "Each Secretariat shall su bmit a Report."
    assert candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    assert coverage.status == (
        ReviewIssueStatus.RESOLVED if source_matches else ReviewIssueStatus.OPEN
    )
    assert unrelated.status == ReviewIssueStatus.OPEN
    assert candidate.blocking_issue_count == (1 if source_matches else 2)
    revision = db.exec(
        select(CandidateRevision).where(CandidateRevision.candidate_id == candidate.id)
    ).one()
    assert revision.previous_text == candidate.raw_text
    assert revision.diff
    if source_matches:
        assert coverage.resolution_evidence is not None
        assert coverage.resolution_evidence["exact_source_character_match"] is True


def test_formatting_revision_does_not_duplicate_original_punctuation_blocker(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        canonical_path=f"constitution.1999.section54.{uuid.uuid4().hex}",
        sort_key="054",
        raw_text="(3 The decision shall be made.",
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=1,
    )
    db.add(candidate)
    db.commit()
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="unbalanced_punctuation",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Malformed punctuation in source",
    )
    db.add(issue)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"formatting-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "(3 The decision shall be made.",
            "reason": "Preserve punctuation exactly as in source",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["blocking_issue_count"] == 1
    assert [
        item["issue_type"] for item in payload["issues"] if item["status"] == "open"
    ] == ["unbalanced_punctuation"]


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
    # A rejected duplicate scan and its open finding must not hold the run back.
    rejected = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        canonical_path=f"constitution.1999.rejected-duplicate.{uuid.uuid4().hex}",
        sort_key="999",
        raw_text="Every citizen is entitled (to privacy.",
        status=ExtractionCandidateStatus.REJECTED,
        blocking_issue_count=1,
    )
    db.add_all([run, review_step, candidate, rejected])
    db.commit()
    db.add(
        ReviewIssue(
            candidate_id=rejected.id,
            issue_type="unbalanced_punctuation",
            blocking=True,
            message="Unbalanced brackets in a rejected duplicate.",
        )
    )
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
) -> None:
    release, build = _release_bundle(db, uploader=_superuser(db))

    release.validation_report = {
        **(release.validation_report or {}),
        "corpus_legal_status": "historical",
        "source_edition_review": {"known_exceptions": "Printed 189; missing 168"},
    }
    db.add(release)
    db.commit()
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
    assert (
        validate_response.json()["validation_report"]["corpus_legal_status"]
        == "historical"
    )
    assert validate_response.json()["validation_report"]["source_edition_review"] == {
        "known_exceptions": "Printed 189; missing 168"
    }
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
    db.refresh(build)
    assert build.status == VectorIndexStatus.PROMOTED
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
    release, _build = _release_bundle(db, uploader=_superuser(db))
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
    release, _build = _release_bundle(db, uploader=_superuser(db))

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
    release, build = _release_bundle(db, uploader=uploader)
    vector_index = VectorIndex(
        release_id=release.id,
        embedding_run_id=build.embedding_run_id,
        profile_id=build.profile_id,
        collection_name=f"ng_constitution_enacted_test_{uuid.uuid4().hex}",
        alias_name="constitution_enacted",
        status=VectorIndexStatus.READY,
        point_count=1,
        vector_dimensions=1024,
        validation_report={"backend": "qdrant", "remote_point_count": 1},
    )
    db.add(vector_index)
    db.commit()
    db.refresh(vector_index)
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
    assert payload["vector_indexes"][0]["validation_report"] == {
        "backend": "qdrant",
        "remote_point_count": 1,
    }
    assert payload["vector_indexes"][0]["alias_name"] == "constitution_enacted"
    assert payload["retrieval_index_builds"][0]["id"] == str(build.id)
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
    release, _build = _release_bundle(db, uploader=_superuser(db))

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publication-evidence",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


def test_release_validation_rejects_ready_index_without_validation_evidence(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, build = _release_bundle(db, uploader=_superuser(db))
    build.validation_report = {"is_valid": True}
    db.add(build)
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
        "retrieval_index_report_dimensions_mismatch",
        "retrieval_index_lexical_validation_missing",
    ]


def test_release_validation_rejects_selected_embedding_below_recall_gate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _build = _release_bundle(db, uploader=_superuser(db))
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
    release, _build = _release_bundle(db, uploader=_superuser(db))
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
) -> tuple[CorpusRelease, RetrievalIndexBuild]:
    source, run = _source_and_run(db, created_by=uploader.id)
    source.verification_status = VerificationStatus.VERIFIED
    db.add(source)
    db.commit()
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
        model_revision="pinned-test-revision",
        vector_dimensions=1024,
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
    documents = build_retrieval_documents(
        release_version=release.version,
        entries=[entry],
        versions_by_id={version.id: version},
        provisions_by_id={provision.id: provision},
        instruments_by_id={instrument.id: instrument},
    )
    segments = write_segments(
        db, release_id=release.id, documents=documents, index_kind="enacted"
    )
    embeddings = write_embeddings(
        db,
        release_id=release.id,
        embedding_run=embedding_run,
        profile=profile,
        segments=segments,
        vectors=[[1.0] + [0.0] * 1023 for _ in segments],
    )
    build = RetrievalIndexBuild(
        release_id=release.id,
        embedding_run_id=embedding_run.id,
        profile_id=profile.id,
        profile_hash=_sha256_text("profile-config-v1"),
        status=VectorIndexStatus.READY,
        expected_segment_count=len(documents),
        stored_segment_count=len(segments),
        stored_embedding_count=len(embeddings),
        vector_dimensions=1024,
        checksum=_sha256_text("vector-checksum"),
    )
    build.validation_report = validate_index_build(
        db, build=build, expected_segment_count=len(documents)
    )
    assert build.validation_report["is_valid"]
    db.add(build)
    db.commit()
    db.refresh(release)
    db.refresh(build)
    return release, build


def test_my_roles_returns_superuser_with_all_roles(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/admin/my-roles", headers=superuser_token_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_superuser"] is True
    assert set(body["roles"]) == {
        "ingestion_uploader",
        "legal_reviewer",
        "corpus_publisher",
    }


def test_audit_events_endpoint_returns_entries(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=None,
            action="test.probe",
            entity_type="corpus_release",
            entity_id=uuid.uuid4(),
            severity=AuditSeverity.INFO,
            reason="probe",
        )
    )
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/admin/audit-events", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_ocr_benchmark_evaluate_scores_providers(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    dataset = EvaluationDataset(
        version=f"ocr-bench-{uuid.uuid4().hex}",
        name="OCR bench",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
        is_active=True,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="page-1",
            item_kind=EvaluationItemKind.OCR_PAGE,
            expected_text="Right to private and family life",
        )
    )
    db.commit()
    response = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{dataset.version}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": dataset.version,
            "samples": [
                {
                    "item_key": "page-1",
                    "provider": "google_document_ai",
                    "text": "Right to private and family life",
                },
                {
                    "item_key": "page-1",
                    "provider": "azure_document_intelligence",
                    "text": "Right to private and family live",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["winner"] == "google_document_ai"
    assert body["sample_count"] == 1


def test_my_roles_returns_scoped_roles_for_non_superuser(
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

    response = client.get(f"{settings.API_V1_STR}/admin/my-roles", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["is_superuser"] is False
    assert body["roles"] == ["legal_reviewer"]


def test_my_roles_returns_empty_roles_without_assignment(
    client: TestClient,
    db: Session,
) -> None:
    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)

    response = client.get(f"{settings.API_V1_STR}/admin/my-roles", headers=headers)

    assert response.status_code == 200
    assert response.json()["roles"] == []


def test_audit_events_filter_by_entity_and_reject_non_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    release_id = uuid.uuid4()
    other_id = uuid.uuid4()
    db.add_all(
        [
            AuditEvent(
                actor_user_id=None,
                action="corpus_release.publish",
                entity_type="corpus_release",
                entity_id=release_id,
                severity=AuditSeverity.INFO,
                reason="first",
            ),
            AuditEvent(
                actor_user_id=None,
                action="source_document.verified",
                entity_type="source_document",
                entity_id=other_id,
                severity=AuditSeverity.INFO,
                reason="second",
            ),
        ]
    )
    db.commit()

    filtered = client.get(
        f"{settings.API_V1_STR}/admin/audit-events",
        headers=superuser_token_headers,
        params={"entity_id": str(release_id)},
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["count"] == 1
    assert body["data"][0]["entity_id"] == str(release_id)

    forbidden = client.get(
        f"{settings.API_V1_STR}/admin/audit-events",
        headers=normal_user_token_headers,
    )
    assert forbidden.status_code == 403


def test_ocr_benchmark_read_reports_dataset_counts(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    version = f"ocr-read-{uuid.uuid4().hex}"
    dataset = EvaluationDataset(
        version=version,
        name="OCR read bench",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
        is_active=True,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="page-1",
            item_kind=EvaluationItemKind.OCR_PAGE,
            expected_text="Section 37",
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{version}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 1
    assert body["active_dataset_items"] == 1
    assert body["winner"] is None


def test_ocr_benchmark_evaluate_rejects_bad_requests(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    version = f"ocr-bad-{uuid.uuid4().hex}"
    dataset = EvaluationDataset(
        version=version,
        name="OCR bad bench",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
        is_active=True,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="page-1",
            item_kind=EvaluationItemKind.OCR_PAGE,
            expected_text="Section 37",
        )
    )
    db.commit()

    mismatch = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{version}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": "other-version",
            "samples": [],
        },
    )
    assert mismatch.status_code == 400

    unknown_provider = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{version}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": version,
            "samples": [
                {
                    "item_key": "page-1",
                    "provider": "mystery_ocr",
                    "text": "Section 37",
                }
            ],
        },
    )
    assert unknown_provider.status_code == 400

    missing = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/missing-{uuid.uuid4().hex}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": "missing-version",
            "samples": [],
        },
    )
    assert missing.status_code in (400, 404)
