import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.legal.enums import (
    AuditSeverity,
)
from app.legal.models import (
    AuditEvent,
)


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
