from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.chat.budget import reserve, settle
from app.chat.worker import expire_guest_conversations
from app.core import security
from app.core.config import settings
from app.legal.enums import MessageRole
from app.legal.models import (
    Conversation,
    ConversationMessage,
    GenerationBudgetDay,
    GenerationCapacity,
    GenerationReservation,
    GenerationRun,
    get_datetime_utc,
)
from app.main import app
from app.models import User

pytest_plugins = ["tests.api.routes.test_legal_search"]


def test_guest_ownership_idempotency_and_claim(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    with TestClient(app) as guest, TestClient(app) as stranger:
        created = guest.post("/api/v1/conversations", json={})
        assert created.status_code == 201
        conversation_id = created.json()["id"]
        stored = db.get(Conversation, UUID(conversation_id))
        assert stored is not None
        assert stored.anonymous_session_id is not None
        assert len(stored.anonymous_session_id) == 64
        assert "httponly" in created.headers["set-cookie"].lower()
        assert (
            stranger.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
        )
        assert guest.get("/api/v1/conversations").json()["count"] == 1

        message = {"question": "What does Section 37 say?", "idempotency_key": "once"}
        first = guest.post(
            f"/api/v1/conversations/{conversation_id}/messages", json=message
        )
        assert first.status_code == 202
        second = guest.post(
            f"/api/v1/conversations/{conversation_id}/messages", json=message
        )
        assert second.status_code == 202
        assert second.json()["run_id"] == first.json()["run_id"]
        assert (
            guest.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={"question": "Section 33", "idempotency_key": "once"},
            ).status_code
            == 409
        )
        assert (
            guest.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={"question": "Section 33", "idempotency_key": "twice"},
            ).status_code
            == 409
        )
        run = db.get(GenerationRun, UUID(first.json()["run_id"]))
        assert run is not None and run.status == "pending"
        assert (
            stranger.post(
                f"/api/v1/conversations/{conversation_id}/runs/{run.id}/cancel"
            ).status_code
            == 404
        )
        cancelled = guest.post(
            f"/api/v1/conversations/{conversation_id}/runs/{run.id}/cancel"
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        user = User(email="claim@example.test", hashed_password="unused")
        db.add(user)
        db.commit()
        token = security.create_access_token(user.id, timedelta(hours=1))
        headers = {"Authorization": f"Bearer {token}"}
        assert guest.get("/api/v1/conversations", headers=headers).json()["count"] == 0
        claimed = guest.post("/api/v1/conversations/claim", headers=headers)
        assert claimed.status_code == 200
        assert claimed.json()["claimed_count"] == 1
        assert (
            guest.get(
                f"/api/v1/conversations/{conversation_id}", headers=headers
            ).status_code
            == 200
        )
        assert guest.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
        assert (
            stranger.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
        )


def test_pinned_release_and_no_generation_when_disabled(
    corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, _source, _nodes, _pdf = corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", False)
    with TestClient(app) as guest:
        created = guest.post(
            "/api/v1/conversations", json={"release_version": release.version}
        )
        assert created.status_code == 201
        assert created.json()["release_version"] == release.version
        conversation_id = created.json()["id"]
        assert (
            guest.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={"question": "Section 37", "idempotency_key": "disabled"},
            ).status_code
            == 503
        )
        assert (
            guest.delete(f"/api/v1/conversations/{conversation_id}").status_code == 204
        )
        assert guest.get(f"/api/v1/conversations/{conversation_id}").status_code == 404


def test_guest_burst_limit_counts_cancelled_runs_and_preserves_idempotency(
    corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GUEST_BURST_LIMIT", 2)
    with TestClient(app) as guest:
        conversation_id = guest.post("/api/v1/conversations", json={}).json()["id"]
        for index in range(2):
            body = {"question": "Section 37", "idempotency_key": f"burst-{index}"}
            accepted = guest.post(
                f"/api/v1/conversations/{conversation_id}/messages", json=body
            )
            assert accepted.status_code == 202
            assert (
                guest.post(
                    f"/api/v1/conversations/{conversation_id}/runs/{accepted.json()['run_id']}/cancel"
                ).status_code
                == 200
            )
            repeated = guest.post(
                f"/api/v1/conversations/{conversation_id}/messages", json=body
            )
            assert repeated.status_code == 202
            assert repeated.json()["run_id"] == accepted.json()["run_id"]
        blocked = guest.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": "Section 33", "idempotency_key": "burst-blocked"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["detail"] == "Too many explanations in one minute"


def test_expired_guest_history_removes_runs_and_capacity(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    with TestClient(app) as guest:
        created = guest.post("/api/v1/conversations", json={}).json()
        conversation_id = UUID(created["id"])
        accepted = guest.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": "Section 37", "idempotency_key": "expire"},
        ).json()
        conversation = db.get(Conversation, conversation_id)
        assert conversation is not None
        conversation.updated_at = get_datetime_utc() - timedelta(days=31)
        db.add(conversation)
        db.commit()
        assert expire_guest_conversations() == 1
        db.expire_all()
        assert db.get(Conversation, conversation_id) is None
        assert db.get(GenerationRun, UUID(accepted["run_id"])) is None
        capacity = db.get(GenerationCapacity, 1)
        assert capacity is not None and capacity.active_count == 0


def test_deleting_active_conversation_keeps_spend_reservation(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    with TestClient(app) as guest:
        conversation_id = guest.post("/api/v1/conversations", json={}).json()["id"]
        accepted = guest.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": "Section 37", "idempotency_key": "spend-delete"},
        )
        assert accepted.status_code == 202
        run_id = UUID(accepted.json()["run_id"])
        reservation = reserve(
            db,
            run_id=run_id,
            purpose="generation",
            prompt_chars=1000,
            max_output_tokens=1000,
        )
        reservation_id = reservation.id
        day = reservation.day
        db.commit()

        assert (
            guest.delete(f"/api/v1/conversations/{conversation_id}").status_code == 204
        )
        db.expire_all()
        retained = db.get(GenerationReservation, reservation_id)
        assert retained is not None and retained.run_id is None
        ledger = db.get(GenerationBudgetDay, day)
        assert ledger is not None and ledger.reserved_micro_usd > 0

        settle(db, reservation_id, prompt_tokens=100, completion_tokens=40)
        db.commit()
        db.expire_all()
        retained = db.get(GenerationReservation, reservation_id)
        ledger = db.get(GenerationBudgetDay, day)
        assert retained is not None and retained.status == "settled"
        assert ledger is not None and ledger.reserved_micro_usd == 0
        assert ledger.spent_micro_usd == retained.actual_micro_usd


def test_message_history_uses_owned_stable_cursor(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    with TestClient(app) as guest:
        conversation_id = UUID(
            guest.post("/api/v1/conversations", json={}).json()["id"]
        )
        other_id = UUID(guest.post("/api/v1/conversations", json={}).json()["id"])
        messages = [
            ConversationMessage(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=f"Question {index}",
                created_at=get_datetime_utc() + timedelta(seconds=index),
            )
            for index in range(5)
        ]
        db.add_all(messages)
        foreign = ConversationMessage(
            conversation_id=other_id, role=MessageRole.USER, content="Other"
        )
        db.add(foreign)
        db.commit()

        base = f"/api/v1/conversations/{conversation_id}"
        first = guest.get(base, params={"limit": 2}).json()
        assert [row["content"] for row in first["messages"]] == [
            "Question 3",
            "Question 4",
        ]
        assert first["has_more_messages"] is True
        second = guest.get(
            base, params={"limit": 2, "before": first["next_before"]}
        ).json()
        assert [row["content"] for row in second["messages"]] == [
            "Question 1",
            "Question 2",
        ]
        third = guest.get(
            base, params={"limit": 2, "before": second["next_before"]}
        ).json()
        assert [row["content"] for row in third["messages"]] == ["Question 0"]
        assert third["has_more_messages"] is False
        assert third["next_before"] is None
        assert guest.get(base, params={"before": str(foreign.id)}).status_code == 404
        assert guest.get(base, params={"before": str(uuid4())}).status_code == 404
