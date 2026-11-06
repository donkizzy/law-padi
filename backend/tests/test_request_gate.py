import asyncio

import pytest

from app.core.config import settings
from app.core.request_gate import MAX_GATED_REQUESTS, RequestGateMiddleware
from app.main import app

API = settings.API_V1_STR


def http_scope(path: str = f"{API}/legal/instruments") -> dict[str, object]:
    return {"type": "http", "method": "GET", "path": path, "headers": []}


async def no_body() -> dict[str, object]:
    return {"type": "http.request", "body": b""}


class Recorder:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def __call__(self, message: dict[str, object]) -> None:
        self.messages.append(message)

    @property
    def status(self) -> object:
        return self.messages[0]["status"]

    @property
    def headers(self) -> dict[bytes, bytes]:
        return dict(self.messages[0]["headers"])  # type: ignore[call-overload]


async def respond(send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"{}"})


def gate(inner, *, limit: int = 2, wait_seconds: float = 1) -> RequestGateMiddleware:
    return RequestGateMiddleware(inner, limit=limit, wait_seconds=wait_seconds)


def test_requests_beyond_the_limit_wait_their_turn() -> None:
    running = 0
    peak = 0

    async def inner(_scope, _receive, send) -> None:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        await respond(send)

    async def scenario() -> list[Recorder]:
        middleware = gate(inner)
        sends = [Recorder() for _ in range(6)]
        await asyncio.gather(
            *(middleware(http_scope(), no_body, send) for send in sends)
        )
        return sends

    sends = asyncio.run(scenario())
    assert peak == 2
    assert [send.status for send in sends] == [200] * 6


def test_request_that_waits_too_long_gets_a_quick_503() -> None:
    async def scenario() -> tuple[Recorder, Recorder]:
        release = asyncio.Event()

        async def inner(_scope, _receive, send) -> None:
            await release.wait()
            await respond(send)

        middleware = gate(inner, limit=1, wait_seconds=0.01)
        holder = Recorder()
        running = asyncio.create_task(middleware(http_scope(), no_body, holder))
        await asyncio.sleep(0)
        busy = Recorder()
        await middleware(http_scope(), no_body, busy)
        release.set()
        await running
        return holder, busy

    holder, busy = asyncio.run(scenario())
    assert holder.status == 200
    assert busy.status == 503
    assert busy.headers[b"retry-after"] == b"5"
    assert busy.headers[b"cache-control"] == b"no-store"


def test_slot_is_free_once_the_response_starts() -> None:
    async def scenario() -> Recorder:
        release = asyncio.Event()

        async def slow_reader(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await release.wait()
            await send({"type": "http.response.body", "body": b"{}"})

        calls = 0

        async def inner(scope, receive, send) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                await slow_reader(scope, receive, send)
            else:
                await respond(send)

        middleware = gate(inner, limit=1, wait_seconds=0.01)
        running = asyncio.create_task(middleware(http_scope(), no_body, Recorder()))
        await asyncio.sleep(0)
        next_request = Recorder()
        await middleware(http_scope(), no_body, next_request)
        release.set()
        await running
        return next_request

    assert asyncio.run(scenario()).status == 200


def test_slot_is_returned_when_the_route_fails() -> None:
    calls = 0

    async def inner(_scope, _receive, send) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("route failed")
        await respond(send)

    async def scenario() -> Recorder:
        middleware = gate(inner, limit=1, wait_seconds=0.01)
        with pytest.raises(RuntimeError):
            await middleware(http_scope(), no_body, Recorder())
        after = Recorder()
        await middleware(http_scope(), no_body, after)
        return after

    assert asyncio.run(scenario()).status == 200


@pytest.mark.parametrize(
    "scope",
    [
        http_scope(f"{API}/conversations/abc/events"),
        http_scope(f"{API}/admin/ingestion-runs/abc/events"),
        http_scope(f"{API}/admin/sources/uploads/abc"),
        http_scope(f"{API}/utils/health-check/"),
        http_scope("/assets/index.js"),
        {"type": "lifespan"},
    ],
)
def test_streams_uploads_and_probes_are_not_held(scope: dict[str, object]) -> None:
    called = 0

    async def inner(_scope, _receive, _send) -> None:
        nonlocal called
        called += 1

    async def scenario() -> None:
        middleware = gate(inner, limit=1, wait_seconds=0.01)
        await middleware.slots.acquire()
        await middleware(scope, no_body, Recorder())

    asyncio.run(scenario())
    assert called == 1


def test_limit_stays_below_the_worker_threads() -> None:
    async def inner(_scope, _receive, _send) -> None:
        return None

    assert gate(inner, limit=100).slots._value == MAX_GATED_REQUESTS
    assert MAX_GATED_REQUESTS < 40


def test_application_uses_the_gate() -> None:
    assert RequestGateMiddleware in [item.cls for item in app.user_middleware]
