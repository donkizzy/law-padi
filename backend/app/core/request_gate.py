"""Admit only as many database requests as can finish, and queue the rest here.

A synchronous route keeps its pooled connection until the response is sent, and
needs a worker thread again to validate that response. When more requests arrive
than the pool holds, the newest ones fill every thread waiting for a connection
while the requests holding connections wait for a thread. Nothing moves until the
pool times out. Requests held here wait on the event loop and take neither.
"""

import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

# Below AnyIO's 40 worker threads, so a thread is always free to finish a request.
MAX_GATED_REQUESTS = 30


def _gated(path: str) -> bool:
    """Skip streams and uploads, which stay open, and the health probe."""
    return (
        path.startswith(f"{settings.API_V1_STR}/")
        and not path.startswith(f"{settings.API_V1_STR}/admin/")
        and not path.startswith(f"{settings.API_V1_STR}/utils/health-check")
        and not path.endswith("/events")
    )


class RequestGateMiddleware:
    def __init__(self, app: ASGIApp, *, limit: int, wait_seconds: float) -> None:
        self.app = app
        self.slots = asyncio.Semaphore(min(limit, MAX_GATED_REQUESTS))
        self.wait_seconds = wait_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _gated(scope["path"]):
            await self.app(scope, receive, send)
            return
        try:
            async with asyncio.timeout(self.wait_seconds):
                await self.slots.acquire()
        except TimeoutError:
            response = JSONResponse(
                {"detail": "The service is busy. Please try again shortly."},
                status_code=503,
                headers={"Cache-Control": "no-store", "Retry-After": "5"},
            )
            await response(scope, receive, send)
            return

        released = False

        def release() -> None:
            nonlocal released
            if not released:
                released = True
                self.slots.release()

        async def send_response(message: Message) -> None:
            # Validation is over by now, so a slow reader cannot hold a slot.
            if message["type"] == "http.response.start":
                release()
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        finally:
            release()
