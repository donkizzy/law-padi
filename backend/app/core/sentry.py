"""Error reporting that never sends request bodies, emails or reader questions.

Everything here is a no-op unless `SENTRY_DSN` is set outside development.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import sentry_sdk

from app.core.config import settings

FILTERED = "[Filtered]"
# Field names whose values are personal data, reader text or credentials.
_SENSITIVE_KEY = re.compile(
    r"email|username|question|^content$|^body$|password|secret|token|authorization"
    r"|cookie",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: FILTERED
            if isinstance(key, str) and _SENSITIVE_KEY.search(key)
            else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        return _EMAIL.sub(FILTERED, value)
    return value


def scrub_event(event: Any, _hint: Any = None) -> Any:
    """Drop request bodies and cookies, then filter sensitive fields anywhere.

    Email addresses also appear in URLs (password recovery) and database error
    messages, so every string is searched for them, not only named fields.
    """
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
    return _scrub(event)


def scrub_breadcrumb(crumb: Any, _hint: Any = None) -> Any:
    return _scrub(crumb)


def init_sentry(component: str) -> bool:
    """Start error reporting for one process; return whether it is enabled."""
    if not settings.SENTRY_DSN or settings.FASTAPI_ENV == "development":
        return False
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        release=settings.BUILD_REVISION,
        environment=settings.SENTRY_ENVIRONMENT,
        send_default_pii=False,
        max_request_body_size="never",
        # Frame locals hold questions, request bodies and passwords.
        include_local_variables=False,
        before_send=scrub_event,
        before_send_transaction=scrub_event,
        before_breadcrumb=scrub_breadcrumb,
    )
    sentry_sdk.set_tag("component", component)
    return True


@contextmanager
def tagged_scope(**tags: str | None) -> Iterator[None]:
    """Attach identifiers to errors reported inside, without leaking outside."""
    with sentry_sdk.isolation_scope() as scope:
        for key, value in tags.items():
            if value is not None:
                scope.set_tag(key, value)
        yield
