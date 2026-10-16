"""Queue failure/recovery regressions, using an isolated PostgreSQL test DB."""

import asyncio
import base64
import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.chat import worker
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings
from app.core.db import engine
from app.deployment import chat_dispatch, worker_app
from app.legal.models import (
    ConversationMessage,
    GenerationRun,
    TransactionalOutbox,
    get_datetime_utc,
)
from app.main import app

pytest_plugins = ["tests.api.routes.test_legal_search"]


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_DISPATCH_MODE", "cloud_tasks")
    deliveries: list[UUID] = []

    def enqueue(event: TransactionalOutbox) -> None:
        # The publication must see the committed run/message/intent from a
        # separate transaction, not race an uncommitted API submission.
        with Session(engine) as observer:
            run = observer.get(GenerationRun, event.aggregate_id)
            assert run is not None
            assert observer.get(ConversationMessage, run.user_message_id) is not None
            assert observer.get(TransactionalOutbox, event.id) is not None
        deliveries.append(event.id)

    monkeypatch.setattr(chat_dispatch, "_enqueue", enqueue)
    return deliveries


def _submit(client: TestClient) -> tuple[str, UUID]:
    response = client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    conversation = response.json()["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"question": "Section 37", "idempotency_key": "submission"},
    )
    assert response.status_code == 202
    return conversation, UUID(response.json()["run_id"])


def _outbox(db: Session, run_id: UUID) -> list[TransactionalOutbox]:
    db.expire_all()
    return list(
        db.exec(
            select(TransactionalOutbox)
            .where(
                TransactionalOutbox.aggregate_id == run_id,
                TransactionalOutbox.event_type == chat_dispatch.CHAT_DISPATCH_EVENT,
            )
            .order_by(TransactionalOutbox.created_at)
        ).all()
    )


def test_submission_stages_and_commits_before_publication(corpus, db, queue) -> None:
    assert corpus
    with TestClient(app) as client:
        _, run_id = _submit(client)
    events = _outbox(db, run_id)
    assert len(events) == 1
    assert queue == [events[0].id]
    assert events[0].published_at is not None
    assert events[0].payload["generation_attempt"] == 0


@pytest.mark.parametrize("recovery", ["status", "retry", "reconcile"])
def test_lost_enqueue_recovers_the_same_durable_intent(
    corpus,
    db: Session,
    queue: list[UUID],
    monkeypatch: pytest.MonkeyPatch,
    recovery: str,
) -> None:
    assert corpus
    real_enqueue = chat_dispatch._enqueue

    def unavailable(event: TransactionalOutbox) -> None:
        queue.append(event.id)
        raise httpx.ConnectError("fake unavailable task service")

    monkeypatch.setattr(chat_dispatch, "_enqueue", unavailable)
    with TestClient(app) as client:
        conversation, run_id = _submit(client)
        original = _outbox(db, run_id)[0]
        assert original.published_at is None
        assert original.error_message == "ConnectError"
        monkeypatch.setattr(chat_dispatch, "_enqueue", real_enqueue)
        if recovery == "status":
            assert (
                client.get(f"/api/v1/conversations/{conversation}").status_code == 200
            )
        elif recovery == "retry":
            response = client.post(
                f"/api/v1/conversations/{conversation}/messages",
                json={"question": "Section 37", "idempotency_key": "submission"},
            )
            assert response.status_code == 202
            assert response.json()["run_id"] == str(run_id)
        else:
            assert chat_dispatch.reconcile_dispatches() == 1
    events = _outbox(db, run_id)
    assert len(events) == 1
    assert queue == [events[0].id, events[0].id]
    assert events[0].attempt_count == 2
    assert events[0].published_at is not None
    assert events[0].error_message is None


def test_dispatch_intent_rolls_back_with_run_transaction(corpus, db, queue) -> None:
    assert corpus
    assert not queue
    with TestClient(app) as client:
        _, run_id = _submit(client)
    original_count = len(_outbox(db, run_id))
    # Recovered retrieval attempts require new intent. Its insertion belongs to
    # the same transaction rather than surviving a failed run update.
    run = db.get(GenerationRun, run_id)
    assert run is not None
    run.attempt_count += 1
    db.add(run)
    chat_dispatch.stage_dispatch(db, run)
    db.flush()
    db.rollback()
    assert len(_outbox(db, run_id)) == original_count
    run = db.get(GenerationRun, run_id)
    assert run is not None and run.attempt_count == 0


def test_chat_publisher_leaves_ingestion_events_untouched(corpus, db, queue) -> None:
    assert corpus
    ingestion = TransactionalOutbox(
        aggregate_type="ingestion_run",
        aggregate_id=uuid4(),
        event_type="ingestion_task.enqueued",
        idempotency_key=f"ingestion.{uuid4()}",
    )
    db.add(ingestion)
    db.commit()
    with TestClient(app) as client:
        _submit(client)
    assert chat_dispatch.publish_dispatches() == 0
    db.refresh(ingestion)
    assert ingestion.published_at is None
    assert ingestion.attempt_count == 0
    assert len(queue) == 1


def test_stale_delivery_gets_a_new_name_without_provider_attempt(
    corpus, db, queue
) -> None:
    assert corpus
    with TestClient(app) as client:
        _, run_id = _submit(client)
    original = _outbox(db, run_id)[0]
    assert chat_dispatch.dispatch_run(run_id) == 0
    original.published_at = get_datetime_utc() - timedelta(
        seconds=settings.CHAT_TASK_REDISPATCH_SECONDS + 1
    )
    db.add(original)
    db.commit()
    assert chat_dispatch.dispatch_run(run_id) == 1
    events = _outbox(db, run_id)
    assert len(events) == 2
    assert events[1].idempotency_key != events[0].idempotency_key
    assert [row.payload["dispatch_attempt"] for row in events] == [0, 1]
    run = db.get(GenerationRun, run_id)
    assert run is not None and run.attempt_count == 0
    assert queue == [events[0].id, events[1].id]


@pytest.mark.parametrize("provider_started", [False, True])
def test_expired_lease_recovery_never_repeats_uncertain_provider_dispatch(
    corpus, db: Session, queue: list[UUID], provider_started: bool
) -> None:
    assert corpus
    with TestClient(app) as client:
        _, run_id = _submit(client)
    assert worker._claim_run("crashed", run_id=run_id) == run_id
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None
    run.lease_until = get_datetime_utc() - timedelta(seconds=1)
    if provider_started:
        run.provider_started_at = get_datetime_utc() - timedelta(seconds=2)
    db.add(run)
    db.commit()
    assert chat_dispatch.reconcile_dispatches() == (0 if provider_started else 1)
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None and run.attempt_count == 1
    assert run.status == ("failed" if provider_started else "pending")
    assert len(queue) == (1 if provider_started else 2)
    if not provider_started:
        events = _outbox(db, run_id)
        assert events[-1].payload["generation_attempt"] == 1


def test_active_task_delivery_remains_retryable(corpus, queue) -> None:
    assert corpus
    assert not queue
    with TestClient(app) as client:
        _, run_id = _submit(client)
    assert worker._claim_run("still-running", run_id=run_id) == run_id
    with TestClient(worker_app.app) as client:
        response = client.post("/internal/chat/run", json={"run_id": str(run_id)})
    assert response.status_code == 503


def test_handler_awaits_completion_and_acknowledges_terminal_duplicate(
    corpus, queue, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    assert not queue
    calls: list[UUID] = []

    async def finish(run_id: UUID, identity: str) -> None:
        await asyncio.sleep(0)
        calls.append(run_id)
        await asyncio.to_thread(
            worker._finish,
            run_id,
            identity,
            ExplanationAnswer(outcome="insufficient_evidence"),
        )

    monkeypatch.setattr(worker, "process_run", finish)
    with TestClient(app) as client:
        _, run_id = _submit(client)
    with TestClient(worker_app.app) as client:
        response = client.post("/internal/chat/run", json={"run_id": str(run_id)})
        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        duplicate = client.post("/internal/chat/run", json={"run_id": str(run_id)})
        assert duplicate.status_code == 200
        assert duplicate.json() == response.json()
        assert client.post(
            "/internal/chat/run", json={"run_id": str(uuid4())}
        ).json() == {"status": "deleted"}
    assert calls == [run_id]


def test_disabled_generation_finishes_without_provider(
    corpus, queue, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    assert not queue
    with TestClient(app) as client:
        _, run_id = _submit(client)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", False)

    async def forbidden(run_id: UUID, identity: str) -> None:
        raise AssertionError(f"Disabled run {run_id} dispatched by {identity}")

    monkeypatch.setattr(worker, "process_run", forbidden)
    with TestClient(worker_app.app) as client:
        response = client.post("/internal/chat/run", json={"run_id": str(run_id)})
    assert response.status_code == 200


def test_rest_task_has_oidc_run_only_payload_and_deterministic_dedup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "GCP_PROJECT_ID", "example-project")
    monkeypatch.setattr(settings, "GCP_TASKS_LOCATION", "us-east1")
    monkeypatch.setattr(settings, "GCP_CHAT_QUEUE", "chat")
    monkeypatch.setattr(settings, "CHAT_TASK_HANDLER_URL", "https://worker.run.app")
    monkeypatch.setattr(
        settings, "CHAT_TASK_SERVICE_ACCOUNT", "tasks@example.iam.gserviceaccount.com"
    )
    monkeypatch.setattr(settings, "CHAT_TASK_AUDIENCE", "")
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "metadata.google.internal":
            assert request.headers["Metadata-Flavor"] == "Google"
            return httpx.Response(200, json={"access_token": "temporary-test-token"})
        assert request.url.host == "cloudtasks.googleapis.com"
        assert request.headers["Authorization"] == "Bearer temporary-test-token"
        requests.append(json.loads(request.content))
        return httpx.Response(409, json={"error": {"status": "ALREADY_EXISTS"}})

    original_client = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    event = TransactionalOutbox(
        aggregate_type="generation_run",
        aggregate_id=uuid4(),
        event_type=chat_dispatch.CHAT_DISPATCH_EVENT,
        idempotency_key="fixed-intent",
    )
    chat_dispatch._enqueue(event)
    chat_dispatch._enqueue(event)
    assert requests[0] == requests[1]
    task = requests[0]["task"]
    assert (
        task["dispatchDeadline"] == f"{settings.CHAT_TASK_DISPATCH_DEADLINE_SECONDS}s"
    )
    assert task["httpRequest"]["url"] == "https://worker.run.app/internal/chat/run"
    assert task["httpRequest"]["oidcToken"]["audience"] == "https://worker.run.app"
    assert json.loads(base64.b64decode(task["httpRequest"]["body"])) == {
        "run_id": str(event.aggregate_id)
    }
