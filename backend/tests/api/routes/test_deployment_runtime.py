import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session

from app.chat import events
from app.core.config import Settings, settings
from app.ingestion.workflow import drain_outbox_batch
from app.legal.models import TransactionalOutbox


def test_cloud_origin_requires_proxy_credential(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "a" * 32)
    path = f"{settings.API_V1_STR}/utils/health-check/"
    assert client.get(path).status_code == 403
    assert (
        client.get(path, headers={"x-origin-proxy-secret": "wrong"}).status_code == 403
    )
    assert (
        client.get(path, headers={"x-origin-proxy-secret": "a" * 32}).status_code == 200
    )


def test_cloud_api_cannot_start_without_origin_credential() -> None:
    with pytest.raises(ValidationError, match="ORIGIN_PROXY_SECRET"):
        Settings(
            _env_file=None,
            SECRET_KEY="test-secret",
            DATABASE_URL="postgresql://test:test@localhost/app_test",
            FIRST_SUPERUSER="admin@example.com",
            FIRST_SUPERUSER_PASSWORD="test-password",
            PROJECT_NAME="test",
            APP_RUNTIME_ROLE="api",
        )


def test_hosted_runtime_cannot_use_development_cookies() -> None:
    with pytest.raises(ValidationError, match="FASTAPI_ENV=development"):
        Settings(
            _env_file=None,
            SECRET_KEY="test-secret",
            DATABASE_URL="postgresql://test:test@localhost/app_test",
            FIRST_SUPERUSER="admin@example.com",
            FIRST_SUPERUSER_PASSWORD="test-password",
            PROJECT_NAME="test",
            APP_RUNTIME_ROLE="api",
            ORIGIN_PROXY_SECRET="a" * 32,
            FASTAPI_ENV="development",
        )


def test_listener_stops_when_the_last_stream_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uuid

    async def exercise() -> None:
        async def listen() -> None:
            await asyncio.Event().wait()

        monkeypatch.setattr(events, "_listen", listen)
        monkeypatch.setattr(events, "_listener_task", None)
        monkeypatch.setattr(events, "_listeners", events.defaultdict(set))
        first_id, second_id = uuid.uuid4(), uuid.uuid4()
        first = events.subscribe(first_id)
        second = events.subscribe(second_id)
        task = events._listener_task
        assert task is not None
        await asyncio.sleep(0)
        events.unsubscribe(first_id, first)
        assert not task.done()
        events.unsubscribe(second_id, second)
        await asyncio.sleep(0)
        assert task.cancelled()
        assert events._listener_task is None

    asyncio.run(exercise())


def test_ingestion_publisher_does_not_consume_chat_dispatch(db: Session) -> None:
    import uuid

    row = TransactionalOutbox(
        aggregate_type="generation_run",
        aggregate_id=uuid.uuid4(),
        event_type="chat_generation.dispatch",
        idempotency_key=f"chat-test:{uuid.uuid4()}",
        payload={},
    )
    db.add(row)
    db.commit()
    published: list[str] = []
    drain_outbox_batch(db, publisher=lambda event: published.append(event.event_type))
    db.refresh(row)
    assert row.published_at is None
    assert "chat_generation.dispatch" not in published
    db.delete(row)
    db.commit()
