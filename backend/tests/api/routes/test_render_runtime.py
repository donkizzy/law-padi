import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.chat import pipeline
from app.chat import runs as run_lifecycle
from app.chat import runtime as chat_runtime
from app.chat.llm import budgeted
from app.chat.llm.protocol import ProviderResult
from app.core.config import settings
from app.core.request_id import RequestIdMiddleware, current_request_id
from app.deployment import render_app
from app.main import app as api_app


async def _until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0.001)

    await asyncio.wait_for(wait(), timeout=2)


def _idle_worker(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"recover": 0, "retention": 0, "claim": 0, "leases": 0}

    def count(key: str) -> Callable[..., None]:
        def call(*_args: Any) -> None:
            calls[key] += 1

        return call

    monkeypatch.setattr(run_lifecycle, "recover_expired", count("recover"))
    monkeypatch.setattr(run_lifecycle, "expire_guest_conversations", count("retention"))
    monkeypatch.setattr(run_lifecycle, "claim_run", count("claim"))
    monkeypatch.setattr(chat_runtime, "next_lease_delay", count("leases"))
    return calls


def test_worker_does_not_poll_neon_while_idle_and_wakes_on_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _idle_worker(monkeypatch)

    async def exercise() -> None:
        runtime = render_app.RequestWorker()
        runtime.start()
        try:
            await _until(lambda: calls["leases"] == 1)
            initial = dict(calls)
            await asyncio.sleep(0.55)
            assert calls == initial
            runtime.wake()
            await _until(lambda: calls["leases"] == 2)
            assert calls == {"recover": 2, "retention": 1, "claim": 2, "leases": 2}
        finally:
            await runtime.close()
        assert runtime.task is not None and runtime.task.done()

    asyncio.run(exercise())


def test_worker_drains_pending_runs_sequentially(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _idle_worker(monkeypatch)
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    runs = [uuid4(), uuid4()]
    pending = list(runs)
    completed: list[UUID] = []
    active = 0

    def claim(_identity: str) -> UUID | None:
        return pending.pop(0) if pending else None

    async def process(run_id: UUID, _identity: str) -> None:
        nonlocal active
        active += 1
        assert active == 1
        await asyncio.sleep(0)
        completed.append(run_id)
        active -= 1

    monkeypatch.setattr(run_lifecycle, "claim_run", claim)
    monkeypatch.setattr(pipeline, "process_run", process)

    async def exercise() -> None:
        runtime = render_app.RequestWorker()
        runtime.start()
        try:
            await _until(lambda: calls["leases"] == 1)
            assert completed == runs
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_known_outstanding_lease_gets_one_recovery_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _idle_worker(monkeypatch)
    deadlines: list[float | None] = [0.01, None]

    def next_lease() -> float | None:
        calls["leases"] += 1
        return deadlines.pop(0)

    monkeypatch.setattr(chat_runtime, "next_lease_delay", next_lease)

    async def exercise() -> None:
        runtime = render_app.RequestWorker()
        runtime.start()
        try:
            await _until(lambda: calls["leases"] == 2)
            await asyncio.sleep(0.05)
            assert calls["recover"] == 2
            assert calls["leases"] == 2
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_shutdown_awaits_uncertain_call_cleanup_and_never_claims_another_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _idle_worker(monkeypatch)
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    claims: list[UUID] = []
    settlements: list[bool] = []

    async def exercise() -> None:
        started = asyncio.Event()

        class Provider:
            async def complete_json(self, **_kwargs: Any) -> ProviderResult:
                started.set()
                await asyncio.Event().wait()
                raise AssertionError("The blocked provider must be cancelled")

        def claim(_identity: str) -> UUID:
            run_id = uuid4()
            claims.append(run_id)
            return run_id

        async def process(run_id: UUID, _identity: str) -> None:
            # Exercise the real charged-call cancellation path. This adapter
            # consumes the cancellation once settlement completes.
            try:
                await budgeted.call(
                    Provider(),
                    run_id,
                    "generation",
                    "system",
                    {},
                    max_tokens=1,
                )
            except asyncio.CancelledError:
                pass

        monkeypatch.setattr(run_lifecycle, "claim_run", claim)
        monkeypatch.setattr(pipeline, "process_run", process)
        monkeypatch.setattr(budgeted, "reserve_call", lambda *_args: uuid4())
        monkeypatch.setattr(
            budgeted,
            "settle_call",
            lambda *_args, uncertain: settlements.append(uncertain),
        )
        runtime = render_app.RequestWorker()
        runtime.start()
        await asyncio.wait_for(started.wait(), timeout=2)
        await runtime.close()
        assert settlements == [True]
        assert len(claims) == 1
        assert runtime.task is not None and runtime.task.done()

    asyncio.run(exercise())


def test_worker_failure_is_supervised_and_chat_and_health_report_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _idle_worker(monkeypatch)
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "a" * 32)

    def fail() -> None:
        calls["recover"] += 1
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(run_lifecycle, "recover_expired", fail)

    async def exercise() -> None:
        runtime = render_app.RequestWorker()
        wrapper = render_app.create_app(api_app, runtime)
        runtime.start()
        try:
            await _until(lambda: runtime.failure is not None)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=wrapper), base_url="http://test"
            ) as client:
                assert (await client.get("/healthz")).status_code == 503
                assert (
                    await client.get(
                        "/api/v1/conversations",
                        headers={"x-origin-proxy-secret": "a" * 32},
                    )
                ).status_code == 503
                assert (await client.get("/api/v1/conversations")).status_code == 403
            assert calls["recover"] == 1
            assert calls["claim"] == 0
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_only_successful_authorized_conversation_responses_wake_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _idle_worker(monkeypatch)
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "a" * 32)
    runtime = render_app.RequestWorker()
    wakeups: list[bool] = []
    monkeypatch.setattr(runtime, "wake", lambda: wakeups.append(True))
    application = FastAPI()

    @application.get("/api/v1/conversations/ok")
    def ok() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/v1/conversations/forbidden")
    def forbidden() -> None:
        raise HTTPException(status_code=403)

    @application.get("/api/v1/conversations/stream")
    def stream() -> StreamingResponse:
        async def events():
            # The worker must be woken before this long-lived SSE body is read.
            assert wakeups == [True]
            yield b"data: complete\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    wrapper = render_app.create_app(application, runtime)
    with TestClient(wrapper) as client:
        wakeups.clear()  # Discard the startup recovery wake-up.
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/v1/conversations/ok").status_code == 200
        assert not wakeups  # Missing edge credential cannot trigger a DB scan.
        headers = {"x-origin-proxy-secret": "a" * 32}
        assert (
            client.get("/api/v1/conversations/forbidden", headers=headers).status_code
            == 403
        )
        assert not wakeups
        assert (
            client.get("/api/v1/conversations/ok", headers=headers).status_code == 200
        )
        assert wakeups == [True]
        wakeups.clear()
        response = client.get("/api/v1/conversations/stream", headers=headers)
        assert response.status_code == 200
        assert "data: complete" in response.text
        assert wakeups == [True]


@pytest.mark.parametrize("embeddings", [False, True])
def test_runtime_metadata_is_protected_reports_worker_settings_and_never_wakes_db(
    monkeypatch: pytest.MonkeyPatch, embeddings: bool
) -> None:
    calls = _idle_worker(monkeypatch)
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "a" * 32)
    monkeypatch.setattr(settings, "BUILD_REVISION", "render-test-build")
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", embeddings)
    runtime = render_app.RequestWorker()
    wakeups: list[bool] = []
    monkeypatch.setattr(runtime, "wake", lambda: wakeups.append(True))
    wrapper = render_app.create_app(FastAPI(), runtime)
    with TestClient(wrapper) as client:
        wakeups.clear()
        path = "/api/v1/deployment/runtime"
        assert client.get(path).status_code == 403
        assert (
            client.get(path, headers={"x-origin-proxy-secret": "wrong"}).status_code
            == 403
        )
        response = client.get(path, headers={"x-origin-proxy-secret": "a" * 32})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "build_revision": "render-test-build",
            "prompt_version": render_app.EXPLANATION_PROMPT_VERSION,
            "retrieval_mode": "hybrid" if embeddings else "lexical",
            "worker_dispatch": "request_woken",
            "metadata_source": "render_worker_settings",
        }
        assert not wakeups
        assert not any(calls.values())


def test_render_liveness_reports_the_worker_and_requests_share_one_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _idle_worker(monkeypatch)
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "a" * 32)
    seen: list[str | None] = []
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)

    @application.get("/api/v1/conversations/ok")
    def ok() -> dict[str, bool]:
        seen.append(current_request_id())
        return {"ok": True}

    def fail() -> None:
        calls["recover"] += 1
        raise RuntimeError("simulated database failure")

    async def exercise() -> None:
        runtime = render_app.RequestWorker()
        wrapper = render_app.create_app(application, runtime)
        runtime.start()
        try:
            await _until(lambda: calls["leases"] == 1)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=wrapper), base_url="http://test"
            ) as client:
                for path in ("/livez", "/healthz"):
                    assert (await client.get(path)).json() == {"status": "ok"}
                response = await client.get(
                    "/api/v1/conversations/ok",
                    headers={"x-origin-proxy-secret": "a" * 32, "X-Request-ID": "one"},
                )
                assert response.headers.get_list("x-request-id") == ["one"]
                assert seen == ["one"]
                monkeypatch.setattr(run_lifecycle, "recover_expired", fail)
                runtime.wake()
                await _until(lambda: runtime.failure is not None)
                assert (await client.get("/livez")).status_code == 503
                unavailable = await client.get(
                    "/api/v1/conversations/ok",
                    headers={"x-origin-proxy-secret": "a" * 32, "X-Request-ID": "two"},
                )
                assert unavailable.status_code == 503
                assert unavailable.headers["x-request-id"] == "two"
        finally:
            await runtime.close()

    asyncio.run(exercise())
