"""Independent guest conversation, pending-run and claim setup."""

from collections.abc import Generator
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.legal.models import GenerationRun, get_datetime_utc
from app.main import app
from app.models import User


@pytest.fixture
def guest_conversation(
    corpus,  # noqa: ARG001 - rebuild the corpus before creating the conversation
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, TestClient, object, str]]:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    with TestClient(app) as guest, TestClient(app) as stranger:
        created = guest.post("/api/v1/conversations", json={})
        conversation_id = created.json()["id"]
        yield guest, stranger, created, conversation_id


@pytest.fixture
def submitted_guest_message(guest_conversation):
    guest, stranger, _created, conversation_id = guest_conversation
    message = {"question": "What does Section 37 say?", "idempotency_key": "once"}
    first = guest.post(
        f"/api/v1/conversations/{conversation_id}/messages", json=message
    )
    return guest, stranger, conversation_id, first, message


@pytest.fixture
def guest_claim_account(submitted_guest_message, db: Session):
    guest, stranger, conversation_id, first, _message = submitted_guest_message
    run = db.get(GenerationRun, UUID(first.json()["run_id"]))
    guest.post(f"/api/v1/conversations/{conversation_id}/runs/{run.id}/cancel")
    user = User(email="claim@example.test", hashed_password="unused")
    db.add(user)
    db.commit()
    token = security.create_access_token(user.id, timedelta(hours=1))
    headers = {"Authorization": f"Bearer {token}"}
    return guest, stranger, conversation_id, user, headers


@pytest.fixture
def claimed_guest_conversation(guest_claim_account, db: Session):
    guest, stranger, conversation_id, user, headers = guest_claim_account
    guest.post("/api/v1/conversations/claim", headers=headers)
    user.email_verified_at = get_datetime_utc()
    db.add(user)
    db.commit()
    claimed = guest.post("/api/v1/conversations/claim", headers=headers)
    return guest, stranger, conversation_id, headers, claimed
