import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


def retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status < 600


def retry_delay(attempt: int, *, base: float = 1, cap: float = 30) -> float:
    return min(
        cap, base * 2.0 ** min(max(attempt - 1, 0), 16) * random.uniform(0.8, 1.2)
    )


def retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            return max(0, (date - datetime.now(UTC)).total_seconds())
        except ValueError, TypeError, OverflowError:
            return None


def request_with_retries(
    send: Callable[[float], httpx.Response],
    *,
    max_attempts: int = 5,
    deadline_seconds: float = 120,
    sleep: Callable[[float], None] | None = None,
) -> httpx.Response:
    """Retry request dispatch within one deadline; never replay a response body."""
    deadline = time.monotonic() + deadline_seconds
    for attempt in range(1, max(1, max_attempts) + 1):
        remaining = max(0.001, deadline - time.monotonic())
        response = None
        try:
            response = send(remaining)
        except httpx.TransportError:
            delay = retry_delay(attempt)
            if attempt >= max_attempts or delay >= deadline - time.monotonic():
                raise
        else:
            response.extensions["ingestion_attempts"] = attempt
            if not retryable_status(response.status_code) or attempt >= max_attempts:
                return response
            header_delay = retry_after(response)
            delay = retry_delay(attempt) if header_delay is None else header_delay
            if delay >= deadline - time.monotonic():
                return response
            response.close()
        (sleep or time.sleep)(delay)
    raise AssertionError("Retry loop must return or raise")
