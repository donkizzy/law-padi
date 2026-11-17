import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import conversations
from app.chat.budget import reserve, settle
from app.chat.events import emit_event
from app.chat.runs import claim_run, expire_guest_conversations
from app.core import security, sessions
from app.core.config import settings
from app.legal.enums import MessageRole
from app.legal.models import (
    Conversation,
    ConversationMessage,
    GenerationAdmission,
    GenerationBudgetDay,
    GenerationCapacity,
    GenerationReservation,
    GenerationRun,
    get_datetime_utc,
)
from app.main import app
from app.models import User

ROOT = Path(__file__).resolve().parents[4]


def _render_setting(name: str) -> int:
    match = re.search(
        rf'- key: {name}\n\s+value: "?(\d+)"?', (ROOT / "render.yaml").read_text()
    )
    assert match is not None, name
    return int(match.group(1))


def _submit(client: TestClient, key: str) -> tuple[str, UUID]:
    conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
    accepted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"question": "Section 37", "idempotency_key": key},
    )
    assert accepted.status_code == 202, accepted.text
    return conversation_id, UUID(accepted.json()["run_id"])


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


@pytest.mark.usefixtures("corpus")
def test_guest_burst_limit_counts_cancelled_runs_and_preserves_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


@pytest.mark.usefixtures("corpus")
@pytest.mark.parametrize(
    ("limit_name", "expected"),
    [
        ("CHAT_GUEST_DAILY_LIMIT", "Daily explanation allowance reached"),
        ("CHAT_GUEST_BURST_LIMIT", "Too many explanations in one minute"),
        ("CHAT_ACCOUNT_DAILY_LIMIT", "Daily explanation allowance reached"),
        ("CHAT_ACCOUNT_BURST_LIMIT", "Too many explanations in one minute"),
    ],
)
def test_conversation_deletion_does_not_reset_allowance(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    expected: str,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "poll")
    monkeypatch.setattr(settings, limit_name, 1)
    now = get_datetime_utc()
    monkeypatch.setattr(conversations, "get_datetime_utc", lambda: now)
    user = User(
        email="quota@example.test", hashed_password="unused", email_verified_at=now
    )
    db.add(user)
    db.commit()
    headers = (
        {
            "Authorization": f"Bearer {security.create_access_token(user.id, timedelta(hours=1))}"
        }
        if "ACCOUNT" in limit_name
        else {}
    )
    with TestClient(app, base_url="https://testserver", headers=headers) as reader:
        chat = reader.post("/api/v1/conversations", json={}).json()["id"]
        accepted = reader.post(
            f"/api/v1/conversations/{chat}/messages",
            json={"question": "Section 37", "idempotency_key": "quota-first"},
        )
        assert accepted.status_code == 202
        assert reader.delete(f"/api/v1/conversations/{chat}").status_code == 204
        assert db.get(GenerationRun, UUID(accepted.json()["run_id"])) is None

        replacement = reader.post("/api/v1/conversations", json={}).json()["id"]
        rejected = reader.post(
            f"/api/v1/conversations/{replacement}/messages",
            json={"question": "Section 33", "idempotency_key": "quota-second"},
        )
        assert rejected.status_code == 429
        assert rejected.json()["detail"] == expected


@pytest.mark.usefixtures("corpus")
def test_claim_counts_admissions_for_account_and_original_guest(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "poll")
    monkeypatch.setattr(settings, "CHAT_GUEST_DAILY_LIMIT", 1)
    monkeypatch.setattr(settings, "CHAT_ACCOUNT_DAILY_LIMIT", 1)
    now = get_datetime_utc()
    monkeypatch.setattr(conversations, "get_datetime_utc", lambda: now)
    user = User(
        email="claim-quota@example.test",
        hashed_password="unused",
        email_verified_at=now,
    )
    db.add(user)
    db.commit()
    headers = {
        "Authorization": f"Bearer {security.create_access_token(user.id, timedelta(hours=1))}"
    }
    with TestClient(app, base_url="https://testserver") as reader:
        chat = reader.post("/api/v1/conversations", json={}).json()["id"]
        guest_token = reader.cookies.get("law_padi_guest")
        accepted = reader.post(
            f"/api/v1/conversations/{chat}/messages",
            json={"question": "Section 37", "idempotency_key": "guest-quota"},
        )
        assert accepted.status_code == 202
        assert reader.post("/api/v1/conversations/claim", headers=headers).json() == {
            "claimed_count": 1
        }
        assert (
            reader.delete(f"/api/v1/conversations/{chat}", headers=headers).status_code
            == 204
        )
        for identity in (headers, {"Cookie": f"law_padi_guest={guest_token}"}):
            replacement = reader.post(
                "/api/v1/conversations", headers=identity, json={}
            ).json()["id"]
            rejected = reader.post(
                f"/api/v1/conversations/{replacement}/messages",
                headers=identity,
                json={"question": "Section 33", "idempotency_key": "claim-quota"},
            )
            assert rejected.status_code == 429
            assert rejected.json()["detail"] == "Daily explanation allowance reached"


def test_lagos_day_and_rolling_minute_have_independent_boundaries(db: Session) -> None:
    midnight = datetime(2026, 10, 10, 23, tzinfo=UTC)
    owner = conversations.Owner(user_id=uuid4())
    db.add(
        GenerationAdmission(
            run_id=uuid4(),
            user_id=owner.user_id,
            created_at=midnight - timedelta(seconds=30),
        )
    )
    try:
        assert conversations._admission_counts(db, owner, midnight) == (0, 1)
        assert conversations._admission_counts(
            db, owner, midnight + timedelta(seconds=31)
        ) == (0, 0)
    finally:
        db.rollback()


@pytest.mark.usefixtures("corpus")
def test_open_event_stream_stops_reading_after_credentials_change(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    user = User(email=f"{uuid4()}@example.test", hashed_password="unused")
    db.add(user)
    db.commit()
    owner = conversations.Owner(user_id=user.id, auth_version=user.auth_version)
    token = security.create_access_token(user.id, timedelta(hours=1))
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        created = client.post("/api/v1/conversations", headers=headers, json={})
        assert created.status_code == 201
        conversation_id = UUID(created.json()["id"])
        accepted = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"question": "Section 37", "idempotency_key": "revocation"},
        )
        assert accepted.status_code == 202
        run_id = UUID(accepted.json()["run_id"])
        assert conversations._read_events(conversation_id, owner, 0, run_id).events

        user = db.get(User, user.id, with_for_update=True)
        assert user is not None
        sessions.invalidate_credentials(db, user)
        db.commit()

        assert conversations._read_events(
            conversation_id, owner, 0, run_id
        ) == conversations.EventBatch([])
        db.delete(user)
        db.commit()


@pytest.mark.usefixtures("corpus")
@pytest.mark.parametrize("admin_delete", [False, True])
def test_account_deletion_does_not_strand_shared_generation_capacity(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    admin_delete: bool,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "poll")
    monkeypatch.setattr(settings, "CHAT_MAX_ACTIVE_GENERATIONS", 1)
    user = User(
        email="delete-capacity@example.test",
        hashed_password=security.get_password_hash("capacity-password"),
    )
    admin = User(
        email="capacity-admin@example.test", hashed_password="unused", is_superuser=True
    )
    db.add_all([user, admin])
    db.commit()
    user_id = user.id
    user_headers = {
        "Authorization": f"Bearer {security.create_access_token(user_id, timedelta(hours=1))}"
    }
    with TestClient(app, base_url="https://testserver") as client:
        chat = client.post(
            "/api/v1/conversations", headers=user_headers, json={}
        ).json()["id"]
        accepted = client.post(
            f"/api/v1/conversations/{chat}/messages",
            headers=user_headers,
            json={"question": "Section 37", "idempotency_key": "capacity-held"},
        )
        assert accepted.status_code == 202
        run_id = UUID(accepted.json()["run_id"])
        if admin_delete:
            assert claim_run("test-worker", run_id=run_id) == run_id
            admin_headers = {
                "Authorization": f"Bearer {security.create_access_token(admin.id, timedelta(hours=1))}"
            }
            deleted = client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
        else:
            deleted = client.request(
                "DELETE",
                "/api/v1/users/me",
                headers=user_headers,
                json={"current_password": "capacity-password"},
            )
        assert deleted.status_code == 200
        db.expire_all()
        assert db.get(GenerationRun, run_id) is None

        next_chat = client.post("/api/v1/conversations", json={}).json()["id"]
        replacement = client.post(
            f"/api/v1/conversations/{next_chat}/messages",
            json={"question": "Section 33", "idempotency_key": "capacity-reused"},
        )
        assert replacement.status_code == 202


@pytest.mark.usefixtures("corpus")
def test_expired_guest_history_removes_runs_and_capacity(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
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


@pytest.mark.usefixtures("corpus")
def test_deleting_active_conversation_keeps_spend_reservation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
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


@pytest.mark.usefixtures("corpus")
def test_message_history_uses_owned_stable_cursor(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def _ask(reader: TestClient, key: str) -> int:
    chat = reader.post("/api/v1/conversations", json={}).json()["id"]
    response = reader.post(
        f"/api/v1/conversations/{chat}/messages",
        json={"question": "Section 37", "idempotency_key": key},
    )
    if response.status_code == 429:
        assert response.json()["detail"] == "Daily explanation allowance reached"
    return response.status_code


@pytest.mark.usefixtures("corpus")
def test_fresh_guest_cookies_share_their_network_allowance(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "poll")
    monkeypatch.setattr(settings, "CHAT_GUEST_IP_DAILY_LIMIT", 2)
    statuses = []
    for index in range(3):
        # Each client is a new guest cookie from the same address.
        with TestClient(app, base_url="https://testserver") as guest:
            statuses.append(_ask(guest, f"network-{index}"))
    assert statuses == [202, 202, 429]
    admissions = db.exec(select(GenerationAdmission)).all()
    assert len(admissions) == 2
    assert all(row.client_digest and len(row.client_digest) == 64 for row in admissions)
    assert admissions[0].client_digest == admissions[1].client_digest

    user = User(
        email=f"{uuid4()}@example.test",
        hashed_password="unused",
        email_verified_at=get_datetime_utc(),
    )
    db.add(user)
    db.commit()
    token = security.create_access_token(
        user.id, timedelta(hours=1), auth_version=user.auth_version
    )
    with TestClient(
        app,
        base_url="https://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as account:
        assert _ask(account, "network-account") == 202
    account_row = db.exec(
        select(GenerationAdmission).where(GenerationAdmission.user_id == user.id)
    ).one()
    assert account_row.client_digest is None


@pytest.mark.usefixtures("corpus")
def test_fresh_guest_cookies_share_their_network_burst(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "poll")
    monkeypatch.setattr(settings, "CHAT_GUEST_IP_BURST_LIMIT", 1)
    with TestClient(app, base_url="https://testserver") as first:
        assert _ask(first, "burst-network-first") == 202
    with TestClient(app, base_url="https://testserver") as second:
        chat = second.post("/api/v1/conversations", json={}).json()["id"]
        blocked = second.post(
            f"/api/v1/conversations/{chat}/messages",
            json={"question": "Section 37", "idempotency_key": "burst-network-next"},
        )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many explanations in one minute"


@pytest.mark.usefixtures("corpus")
def test_unconfirmed_accounts_get_the_guest_allowance(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "poll")
    monkeypatch.setattr(settings, "CHAT_GUEST_DAILY_LIMIT", 1)
    monkeypatch.setattr(settings, "CHAT_ACCOUNT_DAILY_LIMIT", 5)
    for verified_at, expected in ((None, [202, 429]), (get_datetime_utc(), [202, 202])):
        user = User(
            email=f"{uuid4()}@example.test",
            hashed_password="unused",
            email_verified_at=verified_at,
        )
        db.add(user)
        db.commit()
        token = security.create_access_token(
            user.id, timedelta(hours=1), auth_version=user.auth_version
        )
        with TestClient(
            app,
            base_url="https://testserver",
            headers={"Authorization": f"Bearer {token}"},
        ) as reader:
            statuses = [_ask(reader, f"tier-{user.id}-{index}") for index in range(2)]
        assert statuses == expected


@pytest.mark.usefixtures("corpus")
def test_production_capacity_queues_a_reader_while_another_answer_is_generated(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    concurrency = _render_setting("CHAT_WORKER_CONCURRENCY")
    depth = _render_setting("CHAT_MAX_ACTIVE_GENERATIONS")
    monkeypatch.setattr(settings, "CHAT_WORKER_CONCURRENCY", concurrency)
    monkeypatch.setattr(settings, "CHAT_MAX_ACTIVE_GENERATIONS", depth)
    # One answer is generated at a time; the rest of the admitted runs wait.
    assert concurrency == 1 < depth
    with TestClient(app) as first, TestClient(app) as second:
        _conversation, running = _submit(first, "generating")
        assert claim_run("capacity-test") == running
        _conversation, waiting = _submit(second, "queued")
    run = db.get(GenerationRun, waiting)
    assert run is not None and run.status == "pending"


@pytest.mark.usefixtures("corpus")
def test_a_waiting_run_streams_its_place_in_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_MAX_ACTIVE_GENERATIONS", 5)
    monkeypatch.setattr(conversations, "_QUEUED_POLL_SECONDS", 0.01)
    read_events = conversations._read_events
    reads = 0

    with TestClient(app) as first, TestClient(app) as second:
        _conversation, ahead = _submit(first, "ahead")
        conversation_id, waiting = _submit(second, "waiting")

        def read(
            conversation: UUID,
            owner: conversations.Owner,
            after_id: int,
            run_id: UUID | None = None,
        ) -> conversations.EventBatch:
            nonlocal reads
            reads += 1
            if reads == 2:
                # The run ahead starts, so this one is next.
                assert claim_run("queue-test", run_id=ahead) == ahead
            if reads == 3:
                with Session(conversations.engine) as session:
                    run = session.get(GenerationRun, waiting)
                    assert run is not None
                    run.status = "cancelled"
                    run.outcome = "cancelled"
                    emit_event(
                        session, run, "answer.complete", {"outcome": "cancelled"}
                    )
                    session.add(run)
                    session.commit()
            return read_events(conversation, owner, after_id, run_id)

        monkeypatch.setattr(conversations, "_read_events", read)
        with second.stream(
            "GET",
            f"/api/v1/conversations/{conversation_id}/events",
            params={"run_id": str(waiting)},
        ) as response:
            assert response.status_code == 200
            body = response.read().decode()
    frames = [
        dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        for frame in body.split("\n\n")
        if "event: " in frame
    ]
    assert [frame["event"] for frame in frames] == [
        "message.started",
        "run.queued",
        "run.queued",
        "answer.complete",
    ]
    queued = [frame for frame in frames if frame["event"] == "run.queued"]
    assert [json.loads(frame["data"]) for frame in queued] == [
        {"run_id": str(waiting), "position": 2},
        {"run_id": str(waiting), "position": 1},
    ]
    # Positions are derived, so they carry no ID and are never replayed.
    assert all("id" not in frame for frame in queued)
