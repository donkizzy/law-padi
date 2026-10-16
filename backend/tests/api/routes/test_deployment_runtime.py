import asyncio
import io
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session

from app import cloud_backup
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


@pytest.mark.parametrize("role", ["api", "tasks"])
def test_cloud_runtime_cannot_use_development_cookies(role: str) -> None:
    with pytest.raises(ValidationError, match="FASTAPI_ENV=development"):
        Settings(
            _env_file=None,
            SECRET_KEY="test-secret",
            DATABASE_URL="postgresql://test:test@localhost/app_test",
            FIRST_SUPERUSER="admin@example.com",
            FIRST_SUPERUSER_PASSWORD="test-password",
            PROJECT_NAME="test",
            APP_RUNTIME_ROLE=role,
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


def test_backup_is_private_idempotent_and_does_not_export_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "metadata.google.internal":
            return httpx.Response(200, json={"access_token": "unit-test-token"})
        assert request.headers["authorization"] == "Bearer unit-test-token"
        assert request.method == "GET"
        return httpx.Response(200, json={"size": "123"})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(cloud_backup.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(settings, "GCS_BACKUP_BUCKET", "private-backups")
    monkeypatch.setattr(
        cloud_backup, "_export_database", lambda path: pytest.fail("Duplicate export")
    )
    result = cloud_backup.run_backup()
    assert result["status"] == "already_exists"
    assert result["bytes"] == 123
    assert len(requests) == 2


def test_backup_upload_requires_creation_and_verified_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def export(path: Path) -> int:
        path.write_bytes(b"PGDMP-test")
        return 10

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "metadata.google.internal":
            return httpx.Response(200, json={"access_token": "unit-test-token"})
        if request.method == "GET":
            return httpx.Response(404)
        assert request.url.params["ifGenerationMatch"] == "0"
        assert request.read() == b"PGDMP-test"
        return httpx.Response(200, json={"size": "9"})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(cloud_backup.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(settings, "GCS_BACKUP_BUCKET", "private-backups")
    monkeypatch.setattr(cloud_backup, "_export_database", export)
    with pytest.raises(cloud_backup.BackupError, match="size was not verified"):
        cloud_backup.run_backup()


def test_backup_upload_race_reads_actual_existing_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = 0

    def export(path: Path) -> int:
        path.write_bytes(b"PGDMP-test")
        return 10

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        if request.url.host == "metadata.google.internal":
            return httpx.Response(200, json={"access_token": "unit-test-token"})
        if request.method == "GET":
            reads += 1
            return (
                httpx.Response(404)
                if reads == 1
                else httpx.Response(200, json={"size": "123"})
            )
        return httpx.Response(412)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(cloud_backup.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(settings, "GCS_BACKUP_BUCKET", "private-backups")
    monkeypatch.setattr(cloud_backup, "_export_database", export)
    result = cloud_backup.run_backup()
    assert result["status"] == "already_exists"
    assert result["bytes"] == 123
    assert reads == 2


def test_backup_refuses_empty_existing_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "metadata.google.internal":
            return httpx.Response(200, json={"access_token": "unit-test-token"})
        return httpx.Response(200, json={"size": "0"})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(cloud_backup.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(settings, "GCS_BACKUP_BUCKET", "private-backups")
    with pytest.raises(cloud_backup.BackupError, match="empty"):
        cloud_backup.run_backup()


def test_backup_export_bounds_size_and_keeps_credentials_out_of_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    class Process:
        stdout = io.BytesIO(b"too-large-export")
        killed = False

        def poll(self) -> int | None:
            return -9 if self.killed else None

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: int | None = None) -> int:
            return -9 if self.killed else 0

    process = Process()

    def popen(argv: list[str], **kwargs: Any) -> Process:
        captured.update(argv=argv, **kwargs)
        return process

    monkeypatch.setattr(cloud_backup.subprocess, "Popen", popen)
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://user:secret@localhost/app_test?sslmode=verify-full&sslrootcert=system",
    )
    monkeypatch.setattr(settings, "BACKUP_MAX_BYTES", 5)
    with pytest.raises(cloud_backup.BackupError, match="size limit"):
        cloud_backup._export_database(tmp_path / "backup.dump")
    assert process.killed
    assert "secret" not in " ".join(captured["argv"])
    assert captured["env"]["PGSSLROOTCERT"] == "system"


def test_backup_export_timeout_kills_child_and_closes_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Process:
        killed = False
        stdout = io.BytesIO()

        def poll(self) -> int | None:
            return -9 if self.killed else None

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: int | None = None) -> int:
            return -9 if self.killed else 0

    class Timeout:
        daemon = False
        cancelled = False

        def __init__(self, interval: int, callback: Any) -> None:
            assert interval == settings.BACKUP_TIMEOUT_SECONDS
            self.callback = callback

        def start(self) -> None:
            self.callback()

        def cancel(self) -> None:
            self.cancelled = True

    process = Process()
    timer: Timeout | None = None

    def timeout(interval: int, callback: Any) -> Timeout:
        nonlocal timer
        timer = Timeout(interval, callback)
        return timer

    monkeypatch.setattr(cloud_backup.subprocess, "Popen", lambda *_a, **_kw: process)
    monkeypatch.setattr(cloud_backup, "Timer", timeout)
    with pytest.raises(cloud_backup.BackupError, match="export failed"):
        cloud_backup._export_database(tmp_path / "backup.dump")
    assert process.killed
    assert process.stdout.closed
    assert timer is not None and timer.daemon and timer.cancelled
