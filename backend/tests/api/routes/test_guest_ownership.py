from uuid import UUID

from sqlmodel import Session

from app.legal.models import (
    Conversation,
    GenerationRun,
)


def test_guest_conversation_is_private(guest_conversation, db: Session) -> None:
    guest, stranger, created, conversation_id = guest_conversation
    assert created.status_code == 201
    stored = db.get(Conversation, UUID(conversation_id))
    assert stored is not None
    assert stored.anonymous_session_id is not None
    assert len(stored.anonymous_session_id) == 64
    assert "httponly" in created.headers["set-cookie"].lower()
    assert stranger.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
    assert guest.get("/api/v1/conversations").json()["count"] == 1


def test_only_the_guest_owner_can_cancel_a_run(
    submitted_guest_message, db: Session
) -> None:
    guest, stranger, conversation_id, first, _message = submitted_guest_message
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
