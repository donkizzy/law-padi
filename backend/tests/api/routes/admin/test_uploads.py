import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import crud
from app.core.config import settings
from app.ingestion.runtime.runner import run_until_idle
from app.legal.enums import (
    AdminRole,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    SourceUploadStatus,
)
from app.legal.models import (
    AdminRoleAssignment,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    SourceDocument,
    SourceUpload,
)
from tests.api.routes.admin.conftest import (
    _complete_pdf_upload,
    _ManagedLocalBlobStore,
    _source_upload_payload,
)
from tests.factories.pdf import pdf_bytes as _pdf_bytes
from tests.factories.pdf import sha256 as _sha256
from tests.factories.pdf import unique_pdf as _unique_pdf_bytes
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email


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
        monkeypatch.setattr("app.ingestion.admin.uploads.get_blob_store", lambda: store)
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


def test_r2_pdf_upload_session_uses_presigned_quarantine_put_and_completion(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _ManagedLocalBlobStore(tmp_path)
    monkeypatch.setattr(settings, "INGESTION_STORAGE_BACKEND", "r2")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "law-padi-ingestion")
    monkeypatch.setattr("app.ingestion.admin.uploads.get_blob_store", lambda: store)
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
    monkeypatch.setattr("app.ingestion.admin.uploads.get_blob_store", lambda: store)
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
