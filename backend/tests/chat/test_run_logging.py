"""A run's logs carry the request that created it, and never the question."""

import asyncio
import json
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.chat import pipeline, runs, runtime
from app.chat.llm.protocol import ProviderError, ProviderResult
from app.core.config import settings
from app.core.heartbeat import Heartbeat, heartbeat_age
from app.core.logs import JsonFormatter, TextFormatter
from app.languages.codes import Language
from app.legal.models import GenerationRun
from app.main import app
from tests.utils.logs import captured_logs

QUESTION = "Can my landlord evict me for keeping a zebra called Quillfeather?"


class UnavailableProvider:
    async def complete_json(self, **_kwargs: Any) -> ProviderResult:
        raise ProviderError("DeepSeek is temporarily unavailable", retryable=True)


def _submit(monkeypatch: pytest.MonkeyPatch, request_id: str) -> UUID:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_LANGUAGES_ENABLED", [Language.ENGLISH])
    with TestClient(app) as client:
        conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
        accepted = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": QUESTION, "idempotency_key": request_id},
            headers={"X-Request-ID": request_id},
        )
    assert accepted.status_code == 202
    assert accepted.headers["X-Request-ID"] == request_id
    return UUID(accepted.json()["run_id"])


@pytest.mark.usefixtures("corpus")
def test_a_run_records_the_request_that_created_it(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _submit(monkeypatch, "req-run-1")
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None and run.request_id == "req-run-1"


@pytest.mark.usefixtures("corpus")
def test_worker_logs_carry_request_and_run_but_not_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = _submit(monkeypatch, "req-run-2")
    assert runs.claim_run("log-test") == run_id
    monkeypatch.setattr(pipeline, "DeepSeekClient", UnavailableProvider)
    with captured_logs("app") as records:
        asyncio.run(runs.execute(run_id, "log-test", disabled=False))
    chat_records = [r for r in records if r.name.startswith("app.chat")]
    assert {r.getMessage() for r in chat_records} >= {"chat_run_finished"}
    for record in chat_records:
        assert record.__dict__["request_id"] == "req-run-2"
        assert record.__dict__["run_id"] == str(run_id)
    for record in records:
        for line in (JsonFormatter().format(record), TextFormatter().format(record)):
            assert "Quillfeather" not in line
            assert "landlord" not in line
    finished = next(r for r in chat_records if r.getMessage() == "chat_run_finished")
    metrics = json.loads(JsonFormatter().format(finished))["metrics"]
    assert metrics["run_id"] == str(run_id)


def test_the_standalone_loop_beats_on_every_iteration_while_idle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", False)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    beats: list[None] = []
    iterations = 0

    class CountingHeartbeat(Heartbeat):
        def beat(self) -> None:
            beats.append(None)
            super().beat()

    async def sleep(_delay: float) -> None:
        nonlocal iterations
        iterations += 1

    monkeypatch.setattr(runs, "claim_run", lambda _worker: None)
    monkeypatch.setattr(runs, "expire_guest_conversations", lambda: 0)
    monkeypatch.setattr(runs, "recover_expired", lambda: None)
    monkeypatch.setattr(runtime.asyncio, "sleep", sleep)
    path = tmp_path / "chat-worker.heartbeat"
    asyncio.run(
        runtime.run_worker(
            "beat-test",
            stopping=lambda: iterations >= 3,
            heartbeat=CountingHeartbeat(path),
        )
    )
    assert len(beats) == 3
    age = heartbeat_age(path)
    assert age is not None and age < 5
