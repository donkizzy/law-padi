from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api import health
from app.api.errors import register_error_handlers
from app.api.main import api_router
from app.core.config import settings
from app.core.logs import configure_logging
from app.core.request_gate import RequestGateMiddleware

FRONTEND_DIR = Path(__file__).parent / "frontend"


class OriginProxyMiddleware:
    """Check the edge credential before parsing any application requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        secret = settings.ORIGIN_PROXY_SECRET
        if scope["type"] == "http" and secret:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"x-origin-proxy-secret", b"")
            if not compare_digest(supplied, secret.encode()):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"cache-control", b"no-store"),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"detail":"Forbidden","code":"forbidden"}',
                    }
                )
                return
        await self.app(scope, receive, send)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

register_error_handlers(app)

app.add_middleware(
    RequestGateMiddleware,
    limit=settings.DATABASE_POOL_SIZE,
    wait_seconds=settings.DATABASE_GATE_WAIT_SECONDS,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(OriginProxyMiddleware)

app.include_router(health.router)
app.include_router(api_router, prefix=settings.API_V1_STR)
if settings.SERVE_FRONTEND:
    app.frontend("/", directory=FRONTEND_DIR)
