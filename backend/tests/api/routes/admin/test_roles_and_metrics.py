import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app import crud
from app.core.config import settings
from app.legal.enums import (
    AdminRole,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
    ProvisionKind,
    ReleasePromotionStatus,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.models import (
    AdminRoleAssignment,
    CandidateRevision,
    EmbeddingProfile,
    EmbeddingRun,
    ExtractionCandidate,
    IngestionStep,
    IngestionTask,
    ReleasePromotionAttempt,
    ReviewDecisionRecord,
    ReviewIssue,
)
from tests.api.routes.admin.conftest import (
    _release_bundle,
    _source_and_run,
    _source_upload_payload,
    _superuser,
)
from tests.factories.pdf import pdf_bytes as _pdf_bytes
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
