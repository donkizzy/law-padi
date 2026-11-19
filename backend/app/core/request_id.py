"""Give every request an identifier that logs, errors and chat runs carry.

An inbound `X-Request-ID` is kept only when it is a short token of safe
characters, so a caller cannot inject log lines or oversized values; anything
else is replaced by a generated identifier. The identifier is echoed on the
response so a reader's error report can be matched to the server's logs.
"""

import re
import uuid

import sentry_sdk
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logs import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def accept_request_id(value: str | None) -> str:
    if value is not None and _SAFE_REQUEST_ID.fullmatch(value):
        return value
    return uuid.uuid4().hex


def current_request_id() -> str | None:
    return request_id_var.get()


def scope_request_id(scope: Scope) -> str | None:
    state = scope.get("state")
    value = state.get("request_id") if isinstance(state, dict) else None
    return value if isinstance(value, str) else None


class RequestIdMiddleware:
    """Bind the request identifier for logs and Sentry, and echo it.

    When an outer application has already bound one, the inner middleware
    reuses it, so a request has one identifier.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        request_id = current_request_id() or accept_request_id(
            Headers(scope=scope).get(REQUEST_ID_HEADER)
        )
        # Exception handlers run outside this middleware, after the context
        # variable is reset, so they read the identifier from the scope.
        scope.setdefault("state", {})["request_id"] = request_id
        if sentry_sdk.is_initialized():
            # Sentry's ASGI integration gives each request its own scope; an
            # uninitialised SDK has only the shared one, which must stay clean.
            sentry_sdk.get_isolation_scope().set_tag("request_id", request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if REQUEST_ID_HEADER not in headers:
                    headers.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        token = request_id_var.set(request_id)
        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)
