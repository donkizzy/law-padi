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
    """Store a new refresh token for ``user`` and return its raw value."""
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
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    session.commit()
    return raw


def rotate_refresh_token(*, session: Session, token: str) -> tuple[User, str] | None:
    """Exchange a refresh token for a new one, or return ``None`` if it is unusable.

    A token that was already rotated is a sign it was copied. Outside a short
    grace window (two tabs refreshing at once, a lost response) that revokes
    every token from the same sign-in.
    """
    record = session.exec(
        select(RefreshToken)
        .where(RefreshToken.token_hash == _digest(token))
        .with_for_update()
    ).first()
    if record is None:
        return None
    now = get_datetime_utc()
    if record.revoked_at is not None:
        grace = timedelta(seconds=settings.REFRESH_TOKEN_REUSE_GRACE_SECONDS)
        if now - record.revoked_at > grace:
            _revoke(session, col(RefreshToken.family_id) == record.family_id)
        session.commit()
        return None
    if record.expires_at <= now:
        return None
    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        _revoke(session, col(RefreshToken.family_id) == record.family_id)
        session.commit()
        return None
    record.revoked_at = now
    session.add(record)
    return user, issue_refresh_token(
        session=session, user=user, family_id=record.family_id
    )


def revoke_refresh_token(*, session: Session, token: str) -> None:
    """Sign out the session that owns ``token``, on every tab that shares it."""
    record = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == _digest(token))
    ).first()
    if record is not None:
        _revoke(session, col(RefreshToken.family_id) == record.family_id)
        session.commit()


def revoke_user_sessions(*, session: Session, user_id: uuid.UUID) -> None:
    """Sign a user out everywhere, for example after a password change."""
    _revoke(session, col(RefreshToken.user_id) == user_id)
    session.commit()


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
