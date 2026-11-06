"""Rotating refresh-token sessions.

The browser keeps a short-lived access token in memory and a long-lived refresh
token in an HttpOnly cookie scoped to the login routes. Only a SHA-256 digest of
each refresh token is stored, so a database leak does not leak live sessions.
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from fastapi import Response
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, delete, select, update

from app.core.config import settings
from app.models import RefreshToken, User, get_datetime_utc

REFRESH_COOKIE = "constitution_session"
REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/login"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(
    *, session: Session, user: User, family_id: uuid.UUID | None = None
) -> str:
    """Stage a refresh token while the caller holds the user row lock."""
    now = get_datetime_utc()
    # Opportunistically drop this user's dead tokens so the table stays small.
    session.exec(
        delete(RefreshToken).where(
            col(RefreshToken.user_id) == user.id,
            col(RefreshToken.expires_at) < now - timedelta(days=1),
        )
    )
    raw = secrets.token_urlsafe(32)
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=_digest(raw),
            auth_version=user.auth_version,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return raw


def rotate_refresh_token(*, session: Session, token: str) -> tuple[User, str] | None:
    """Exchange a refresh token for a new one, or return ``None`` if it is unusable.

    A token that was already rotated is a sign it was copied. Outside a short
    grace window (two tabs refreshing at once, a lost response) that revokes
    every token from the same sign-in.
    """
    locked = _lock_refresh_token(session, token)
    if locked is None:
        return None
    user, record = locked
    now = get_datetime_utc()
    if record.auth_version != user.auth_version or not user.is_active:
        return None
    if record.revoked_at is not None:
        grace = timedelta(seconds=settings.REFRESH_TOKEN_REUSE_GRACE_SECONDS)
        if now - record.revoked_at > grace:
            _revoke(session, col(RefreshToken.family_id) == record.family_id)
        return None
    if record.expires_at <= now:
        return None
    record.revoked_at = now
    session.add(record)
    return user, issue_refresh_token(
        session=session, user=user, family_id=record.family_id
    )


def revoke_refresh_token(*, session: Session, token: str) -> None:
    """Sign out the session that owns ``token``, on every tab that shares it."""
    locked = _lock_refresh_token(session, token)
    if locked is not None:
        _revoke(session, col(RefreshToken.family_id) == locked[1].family_id)


def invalidate_credentials(session: Session, user: User) -> None:
    """Invalidate the locked user's access, refresh, and outstanding reset tokens."""
    user.auth_version += 1
    session.add(user)
    _revoke(session, col(RefreshToken.user_id) == user.id)


def _lock_refresh_token(
    session: Session, token: str
) -> tuple[User, RefreshToken] | None:
    digest = _digest(token)
    user_id = session.exec(
        select(RefreshToken.user_id).where(RefreshToken.token_hash == digest)
    ).first()
    if user_id is None:
        return None
    # Use the same lock order as password recovery and user-wide revocation.
    user = session.get(User, user_id, populate_existing=True, with_for_update=True)
    if user is None:
        return None
    record = session.exec(
        select(RefreshToken)
        .where(RefreshToken.token_hash == digest)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    return (user, record) if record is not None else None


def _revoke(session: Session, condition: ColumnElement[bool]) -> None:
    session.exec(
        update(RefreshToken)
        .where(condition, col(RefreshToken.revoked_at).is_(None))
        .values(revoked_at=get_datetime_utc())
    )


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.FASTAPI_ENV != "development",
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        httponly=True,
        secure=settings.FASTAPI_ENV != "development",
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
