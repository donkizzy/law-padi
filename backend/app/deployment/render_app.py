"""One-process Render runtime whose chat worker sleeps until useful work arrives.

Run exactly one ASGI process. Durable runs, leases, event replay and provider
reservations remain in PostgreSQL; the event below is only a wake-up hint.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import compare_digest

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, col, func, select
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.chat import EXPLANATION_PROMPT_VERSION, worker
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings
from app.core.db import engine
from app.legal.models import GenerationRun, get_datetime_utc
from app.main import app as api_app

_logger = logging.getLogger(__name__)


def _next_lease_delay() -> float | None:
    """Schedule recovery only for a lease already known to be outstanding."""
    now = get_datetime_utc()
    with Session(engine) as session:
        deadline = session.exec(
            select(func.min(GenerationRun.lease_until)).where(
                GenerationRun.status == "running",
                col(GenerationRun.lease_until) > now,
            )
        ).one()
    return (deadline - now).total_seconds() + 0.1 if deadline else None


class RequestWorker:
    def __init__(self) -> None:
        self.wakeup = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.stopping = False
        self.failure: str | None = None
        self.worker_id = f"render-{uuid.uuid4()}"

    @property
    def healthy(self) -> bool:
        return (
            not self.stopping
            and self.failure is None
            and self.task is not None
            and not self.task.done()
        )

    def wake(self) -> None:
        if self.healthy:
            self.wakeup.set()

    def _completed(self, task: asyncio.Task[None]) -> None:
        if self.stopping:
            return
        if task.cancelled():
            self.failure = "worker_cancelled"
        else:
            error = task.exception()
            self.failure = type(error).__name__ if error else "worker_stopped"
        _logger.error("render_chat_worker_unavailable %s", self.failure)

    def start(self) -> None:
        self.stopping = False
        self.failure = None
        self.wakeup = asyncio.Event()
        self.task = asyncio.create_task(self._run(), name="render-chat-worker")
        self.task.add_done_callback(self._completed)
        self.wake()

    async def close(self) -> None:
        self.stopping = True
        if self.task is not None:
            self.task.cancel()
            # process_run handles cancellation by settling any dispatched call
            # as uncertain and finishing the run. Await that cleanup before exit.
            await asyncio.gather(self.task, return_exceptions=True)

    async def _run(self) -> None:
        next_delay: float | None = None
        last_retention = float("-inf")
        while not self.stopping:
            if next_delay is None:
                await self.wakeup.wait()
            else:
                try:
                    await asyncio.wait_for(self.wakeup.wait(), timeout=next_delay)
                except TimeoutError:
                    pass
            self.wakeup.clear()
            await asyncio.to_thread(worker.recover_expired)
            now = asyncio.get_running_loop().time()
            if now - last_retention >= 3600:
                await asyncio.to_thread(worker.expire_guest_conversations)
                last_retention = now
            while not self.stopping:
                run_id = await asyncio.to_thread(worker._claim_run, self.worker_id)
                if run_id is None or self.stopping:
                    break
                if (
                    not settings.CHAT_ENABLED
                    or not settings.CHAT_GENERATION_ENABLED
                    or settings.CHAT_GENERATION_KILL_SWITCH
                ):
                    await asyncio.to_thread(
                        worker._finish,
                        run_id,
                        self.worker_id,
                        ExplanationAnswer(
                            outcome="cancelled", notice=worker._NOTICE["disabled"]
                        ),
                    )
                else:
                    # One awaited generation at a time. No polling runs while
                    # idle, so the database can suspend between real requests.
                    await worker.process_run(run_id, self.worker_id)
            if self.stopping:
                return
            next_delay = await asyncio.to_thread(_next_lease_delay)


def _is_conversation(scope: Scope) -> bool:
    path = str(scope.get("path", ""))
    prefix = f"{settings.API_V1_STR}/conversations"
    return path == prefix or path.startswith(f"{prefix}/")


def _authorized_origin(scope: Scope) -> bool:
    secret = settings.ORIGIN_PROXY_SECRET
    if not secret:
        return True
    supplied = dict(scope.get("headers", [])).get(b"x-origin-proxy-secret", b"")
    return compare_digest(supplied, secret.encode())


class RequestWakeMiddleware:
    def __init__(self, app: ASGIApp, runtime: RequestWorker) -> None:
        self.app = app
        self.runtime = runtime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        conversation = scope["type"] == "http" and _is_conversation(scope)
        authorized = conversation and _authorized_origin(scope)
        if authorized and not self.runtime.healthy:
            response = JSONResponse(
                {"detail": "Explanations are temporarily unavailable"},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return

        async def send_response(message: Message) -> None:
            # This runs before an SSE body, so generation can complete while
            # the authorized stream waits. Rejected origins/owners never wake DB.
            if (
                authorized
                and message["type"] == "http.response.start"
                and message["status"] < 400
            ):
                self.runtime.wake()
            await send(message)

        await self.app(scope, receive, send_response)


def create_app(
    application: ASGIApp = api_app, runtime: RequestWorker | None = None
) -> FastAPI:
    runtime = runtime or RequestWorker()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        runtime.start()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.chat_worker = runtime

    @app.get("/healthz")
    def health() -> JSONResponse:
        # Render's health probe must not connect to Neon or require edge secrets.
        return JSONResponse(
            {"status": "ok" if runtime.healthy else "degraded"},
            status_code=200 if runtime.healthy else 503,
            headers={"Cache-Control": "no-store"},
        )

    @app.get(f"{settings.API_V1_STR}/deployment/runtime")
    def runtime_metadata(request: Request) -> JSONResponse:
        # The collector must verify the actual process's retrieval settings,
        # rather than infer them from a separate local worker or API build.
        if not _authorized_origin(request.scope):
            return JSONResponse(
                {"detail": "Forbidden"},
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            {
                "build_revision": settings.BUILD_REVISION,
                "prompt_version": EXPLANATION_PROMPT_VERSION,
                "retrieval_mode": "hybrid"
                if settings.EMBEDDING_QUERY_ENABLED
                else "lexical",
                "worker_dispatch": "request_woken",
                "metadata_source": "render_worker_settings",
            },
            headers={"Cache-Control": "no-store"},
        )

    app.add_middleware(RequestWakeMiddleware, runtime=runtime)
    app.mount("/", application)
    return app


app = create_app()
