"""Fixed-window request limits kept in Postgres.

Each limited action counts hits per key (an IP address, an email, a user) in a
window of ``window_seconds``. One atomic upsert per check keeps this correct
across API instances without adding Redis.
"""

import hashlib
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, delete

from app.core.config import settings
from app.core.errors import DomainError, ErrorCode
from app.models import RateLimitCounter


@dataclass(frozen=True)
class Limit:
    name: str
    limit: int
    window_seconds: int


LOGIN_PER_IP = Limit("login-ip", 50, 15 * 60)
LOGIN_PER_ACCOUNT = Limit("login-ip-email", 10, 15 * 60)
# Bounds guessing against one account spread across many addresses.
LOGIN_PER_EMAIL = Limit("login-email", 30, 15 * 60)
REFRESH_PER_IP = Limit("refresh-ip", 120, 15 * 60)
SIGNUP_PER_IP = Limit("signup-ip", 10, 60 * 60)
RECOVERY_PER_IP = Limit("recovery-ip", 10, 60 * 60)
RECOVERY_PER_EMAIL = Limit("recovery-email", 3, 60 * 60)
RESET_PER_IP = Limit("reset-ip", 10, 60 * 60)
VERIFY_PER_IP = Limit("verify-ip", 20, 60 * 60)
VERIFICATION_EMAIL_PER_USER = Limit("verification-email-user", 3, 60 * 60)
EMAIL_CHANGE_PER_IP = Limit("email-change-ip", 10, 60 * 60)
EMAIL_CHANGE_PER_USER = Limit("email-change-user", 3, 60 * 60)
EMAIL_CHANGE_PER_ADDRESS = Limit("email-change-address", 3, 60 * 60)
ACCOUNT_DELETION_PER_USER = Limit("account-deletion-user", 5, 60 * 60)
# Public search is anonymous; these keep one client from exhausting the shared
# database pool and the paid query-understanding budget.
SEARCH_PER_IP = Limit("search-ip", 60, 60)
SEARCH_TRANSLATION_PER_IP = Limit("search-translation-ip", 20, 60 * 60)


def client_ip(request: Request) -> str:
    """The caller's IP address.

    Behind the Cloudflare worker (``ORIGIN_PROXY_SECRET`` set), every request
    has passed the worker, which replaces ``X-Forwarded-For`` with the
    connecting IP, so its first entry is trustworthy. Otherwise the header is
    client-controlled and ignored.
    """
    if settings.ORIGIN_PROXY_SECRET:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _key(limit: Limit, subject: str) -> str:
    # Hash subjects so emails and IPs are not stored in the clear.
    digest = hashlib.sha256(subject.strip().lower().encode()).hexdigest()
    return f"{limit.name}:{digest}"


def _window_start(limit: Limit, now: datetime) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - epoch % limit.window_seconds, tz=UTC)


def _hit(session: Session, limit: Limit, subject: str, now: datetime) -> int:
    """Count one hit against ``subject`` and return the window's total."""
    window_start = _window_start(limit, now)
    statement = (
        insert(RateLimitCounter)
        .values(key=_key(limit, subject), window_start=window_start, count=1)
        .on_conflict_do_update(
            index_elements=["key", "window_start"],
            set_={"count": col(RateLimitCounter.count) + 1},
        )
        .returning(col(RateLimitCounter.count))
    )
    count = session.exec(statement).scalar_one()
    if random.random() < 0.01:
        # Occasionally sweep windows that ended more than a day ago.
        session.exec(
            delete(RateLimitCounter).where(
                col(RateLimitCounter.window_start) < func.now() - timedelta(days=1)
            )
        )
    session.commit()
    return int(count)


def allow(session: Session, limit: Limit, subject: str) -> bool:
    """Count one hit against ``subject``; ``False`` once over the limit.

    For callers with a graceful fallback instead of a 429.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return True
    return _hit(session, limit, subject, datetime.now(UTC)) <= limit.limit


def enforce(session: Session, limit: Limit, subject: str) -> None:
    """Count one hit against ``subject``; raise 429 once over the limit."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    now = datetime.now(UTC)
    count = _hit(session, limit, subject, now)
    if count > limit.limit:
        window_end = _window_start(limit, now) + timedelta(seconds=limit.window_seconds)
        retry_after = max(1, math.ceil((window_end - now).total_seconds()))
        minutes = math.ceil(retry_after / 60)
        raise DomainError(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            detail=(
                "Too many attempts. Try again in "
                f"{minutes} minute{'s' if minutes != 1 else ''}."
            ),
            retry_after=retry_after,
        )
