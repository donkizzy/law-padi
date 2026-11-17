"""A reader's stop request and a stopping worker are different events."""

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.chat import pipeline, runs
from app.chat.llm import budgeted
from app.chat.llm.protocol import ProviderResult
from app.chat.notices import NOTICE
from app.chat.pipeline_state import RunState
from app.core.config import settings
from app.languages.codes import Language
from app.legal.models import ConversationMessage, GenerationReservation, GenerationRun
from app.main import app


class BlockedProvider:
    """Blocks inside the drafting call until it is cancelled."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False
        self.on_start: Any = None

    async def complete_json(self, **_kwargs: Any) -> ProviderResult:
        self.started.set()
        if self.on_start is not None:
            await asyncio.to_thread(self.on_start)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("The blocked call must be cancelled")


@contextmanager
def _claimed_run(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str, UUID]]:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_LANGUAGES_ENABLED", [Language.ENGLISH])
    with TestClient(app) as client:
        conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
        accepted = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": "Section 37", "idempotency_key": "cancel"},
        )
        assert accepted.status_code == 202
        run_id = UUID(accepted.json()["run_id"])
        assert runs.claim_run("cancel-test") == run_id
        yield client, conversation_id, run_id


def _stop_worker_once(
    provider_started: asyncio.Event, run_id: UUID, worker: Any
) -> None:
    async def exercise() -> None:
        task = asyncio.create_task(pipeline.process_run(run_id, "cancel-test", worker))
        await asyncio.wait_for(provider_started.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())


@pytest.mark.usefixtures("corpus")
def test_a_reader_cancel_stops_the_call_in_flight(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(budgeted, "CANCEL_POLL_SECONDS", 0.01)
    provider = BlockedProvider()
    with _claimed_run(monkeypatch) as (client, conversation_id, run_id):
        provider.on_start = lambda: client.post(
            f"/api/v1/conversations/{conversation_id}/runs/{run_id}/cancel"
        ).raise_for_status()
        started = time.perf_counter()
        asyncio.run(
            asyncio.wait_for(
                pipeline.process_run(run_id, "cancel-test", provider), timeout=5
            )
        )
        assert time.perf_counter() - started < 5
    assert provider.cancelled
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None and run.outcome == "cancelled"
    message = db.get(ConversationMessage, run.assistant_message_id)
    assert message is not None and message.answer_content is not None
    assert message.answer_content["notice"] == NOTICE["cancelled"]
    reservation = db.exec(
        select(GenerationReservation).where(GenerationReservation.run_id == run_id)
    ).one()
    # The call was dispatched, so it may still be charged.
    assert reservation.status == "uncertain"


@pytest.mark.usefixtures("corpus")
def test_a_stopping_worker_requeues_a_run_that_has_not_paid_for_a_call(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    retrieving = asyncio.Event()

    async def retrieve(_run_id: UUID, _state: RunState) -> None:
        retrieving.set()
        await asyncio.sleep(30)

    monkeypatch.setattr(pipeline, "retrieve_run", retrieve)
    with _claimed_run(monkeypatch) as (_client, _conversation_id, run_id):
        _stop_worker_once(retrieving, run_id, BlockedProvider())
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None
    assert (run.status, run.outcome, run.lease_owner, run.lease_until) == (
        "pending",
        None,
        None,
        None,
    )
    assert run.assistant_message_id is None
    # The next worker claims it again.
    assert runs.claim_run("next-worker") == run_id


@pytest.mark.usefixtures("corpus")
def test_a_stopping_worker_finishes_a_possibly_charged_run_as_stalled(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = BlockedProvider()
    with _claimed_run(monkeypatch) as (_client, _conversation_id, run_id):
        _stop_worker_once(provider.started, run_id, provider)
    assert provider.cancelled
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None
    assert (run.status, run.outcome) == ("failed", "provider_failure")
    message = db.get(ConversationMessage, run.assistant_message_id)
    assert message is not None and message.answer_content is not None
    assert message.answer_content["notice_code"] == "stalled"
    assert message.answer_content["notice"] == NOTICE["stalled"]
    assert message.answer_content["evidence"][0]["citation"] == "Section 37"
    assert message.validation_result is not None
    assert message.validation_result["failure_stage"] == "interrupted"
    reservation = db.exec(
        select(GenerationReservation).where(GenerationReservation.run_id == run_id)
    ).one()
    assert reservation.status == "uncertain"
