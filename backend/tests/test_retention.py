from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.legal.enums import MessageRole
from app.legal.models import Conversation, ConversationMessage, GenerationRun
from app.models import get_datetime_utc
from app.retention import purge_idle_guest_conversations
from tests.utils.user import create_random_user


def _conversation(
    db: Session, *, days_idle: int, guest: bool = True, run_status: str | None = None
) -> Conversation:
    when = get_datetime_utc() - timedelta(days=days_idle)
    owner = (
        {"anonymous_session_id": uuid4().hex}
        if guest
        else {"user_id": create_random_user(db).id}
    )
    conversation = Conversation(created_at=when, updated_at=when, **owner)
    db.add(conversation)
    db.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Can police search my phone?",
    )
    db.add(message)
    db.flush()
    if run_status:
        db.add(
            GenerationRun(
                conversation_id=conversation.id,
                user_message_id=message.id,
                idempotency_key=uuid4().hex,
                status=run_status,
            )
        )
    db.commit()
    return conversation


def _exists(db: Session, conversation_id: UUID) -> bool:
    db.expire_all()
    return db.get(Conversation, conversation_id) is not None


def test_purges_only_idle_guest_conversations(db: Session) -> None:
    retention = settings.GUEST_CONVERSATION_RETENTION_DAYS
    idle_guest = _conversation(db, days_idle=retention + 1).id
    recent_guest = _conversation(db, days_idle=retention - 1).id
    idle_account = _conversation(db, days_idle=retention + 30, guest=False).id
    idle_but_running = _conversation(
        db, days_idle=retention + 1, run_status="running"
    ).id

    while purge_idle_guest_conversations(db):
        pass

    assert not _exists(db, idle_guest)
    assert _exists(db, recent_guest)
    assert _exists(db, idle_account)
    assert _exists(db, idle_but_running)


def test_purge_works_in_batches(db: Session) -> None:
    retention = settings.GUEST_CONVERSATION_RETENTION_DAYS
    for _ in range(3):
        _conversation(db, days_idle=retention + 2)
    assert purge_idle_guest_conversations(db, batch_size=2) == 2
    assert purge_idle_guest_conversations(db, batch_size=2) >= 1


def test_account_export_contains_everything_the_account_holds(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    user.email_verified_at = get_datetime_utc()
    db.add(user)
    db.commit()
    headers = {
        "Authorization": "Bearer "
        + security.create_access_token(user.id, timedelta(minutes=5))
    }
    conversation = Conversation(user_id=user.id, title="Phone searches")
    db.add(conversation)
    db.flush()
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Can police search my phone?",
        )
    )
    db.commit()
    client.put(
        f"{settings.API_V1_STR}/account/saved-provisions",
        headers=headers,
        json={"canonical_path": "chapter-iv/section-37", "release_version": "2024"},
    )

    r = client.get(f"{settings.API_V1_STR}/account/export", headers=headers)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["account"]["email"] == user.email
    assert [s["canonical_path"] for s in data["saved_sections"]] == [
        "chapter-iv/section-37"
    ]
    assert data["preferences"] is None
    assert data["conversations"][0]["title"] == "Phone searches"
    assert data["conversations"][0]["messages"] == [
        {
            "role": "user",
            "content": "Can police search my phone?",
            "created_at": data["conversations"][0]["messages"][0]["created_at"],
        }
    ]


def test_export_needs_sign_in_but_not_a_confirmed_email(
    client: TestClient, db: Session
) -> None:
    assert client.get(f"{settings.API_V1_STR}/account/export").status_code == 401
    user = create_random_user(db)
    token = security.create_access_token(user.id, timedelta(minutes=5))
    r = client.get(
        f"{settings.API_V1_STR}/account/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["account"]["email_verified_at"] is None
