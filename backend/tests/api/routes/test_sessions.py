from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.sessions import REFRESH_COOKIE
from app.main import app
from app.models import RefreshToken, User, get_datetime_utc
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string

LOGIN = f"{settings.API_V1_STR}/login/access-token"
REFRESH = f"{settings.API_V1_STR}/login/refresh"
LOGOUT = f"{settings.API_V1_STR}/login/logout"
ME = f"{settings.API_V1_STR}/users/me"


@pytest.fixture
def browser() -> Generator[TestClient]:
    """A client with its own cookie jar, over HTTPS so Secure cookies flow."""
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _sign_in(browser: TestClient, db: Session) -> tuple[str, str, User]:
    user = create_random_user(db)
    password = random_lower_string()
    user.hashed_password = get_password_hash(password)
    db.add(user)
    db.commit()
    r = browser.post(LOGIN, data={"username": user.email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"], password, user


def _tokens(db: Session, user: User) -> list[RefreshToken]:
    db.expire_all()
    return list(
        db.exec(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
    )


def _cookie(browser: TestClient) -> str:
    value = browser.cookies.get(REFRESH_COOKIE)
    assert value
    return value


def test_login_sets_httponly_refresh_cookie(browser: TestClient, db: Session) -> None:
    _sign_in(browser, db)
    header = next(
        h
        for h in browser.cookies.jar
        if h.name == REFRESH_COOKIE  # type: ignore[attr-defined]
    )
    assert header.path == f"{settings.API_V1_STR}/login"
    assert header.has_nonstandard_attr("HttpOnly")


def test_access_tokens_are_short_lived(browser: TestClient, db: Session) -> None:
    import jwt

    access_token, _, _ = _sign_in(browser, db)
    payload = jwt.decode(access_token, options={"verify_signature": False})
    lifetime = payload["exp"] - get_datetime_utc().timestamp()
    assert lifetime <= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 5


def test_refresh_rotates_cookie_and_returns_working_token(
    browser: TestClient, db: Session
) -> None:
    _sign_in(browser, db)
    first = _cookie(browser)

    r = browser.post(REFRESH)
    assert r.status_code == 200
    second = _cookie(browser)
    assert second != first

    me = browser.get(
        ME, headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    )
    assert me.status_code == 200


def test_refresh_without_cookie_is_unauthorized(browser: TestClient) -> None:
    r = browser.post(REFRESH)
    assert r.status_code == 401
    assert r.json() == {"detail": "Session expired"}


def test_reused_refresh_token_inside_grace_window_keeps_session(
    browser: TestClient, db: Session
) -> None:
    _sign_in(browser, db)
    stale = _cookie(browser)
    assert browser.post(REFRESH).status_code == 200
    fresh = _cookie(browser)

    # A second tab racing with the stale cookie is refused but not punished.
    browser.cookies.set(REFRESH_COOKIE, stale, path=f"{settings.API_V1_STR}/login")
    assert browser.post(REFRESH).status_code == 401

    browser.cookies.clear()
    browser.cookies.set(REFRESH_COOKIE, fresh, path=f"{settings.API_V1_STR}/login")
    assert browser.post(REFRESH).status_code == 200


def test_reused_refresh_token_after_grace_revokes_the_family(
    browser: TestClient, db: Session
) -> None:
    _, _, user = _sign_in(browser, db)
    stale = _cookie(browser)
    assert browser.post(REFRESH).status_code == 200
    fresh = _cookie(browser)

    # Backdate the rotation so the reuse looks like a stolen token.
    for record in _tokens(db, user):
        if record.revoked_at is not None:
            record.revoked_at = get_datetime_utc() - timedelta(minutes=5)
            db.add(record)
    db.commit()

    browser.cookies.clear()
    browser.cookies.set(REFRESH_COOKIE, stale, path=f"{settings.API_V1_STR}/login")
    assert browser.post(REFRESH).status_code == 401

    browser.cookies.clear()
    browser.cookies.set(REFRESH_COOKIE, fresh, path=f"{settings.API_V1_STR}/login")
    assert browser.post(REFRESH).status_code == 401


def test_expired_refresh_token_is_refused(browser: TestClient, db: Session) -> None:
    _, _, user = _sign_in(browser, db)
    for record in _tokens(db, user):
        record.expires_at = get_datetime_utc() - timedelta(seconds=1)
        db.add(record)
    db.commit()
    assert browser.post(REFRESH).status_code == 401


def test_logout_revokes_session(browser: TestClient, db: Session) -> None:
    _sign_in(browser, db)
    cookie = _cookie(browser)

    r = browser.post(LOGOUT)
    assert r.status_code == 200
    assert browser.cookies.get(REFRESH_COOKIE) is None

    browser.cookies.set(REFRESH_COOKIE, cookie, path=f"{settings.API_V1_STR}/login")
    assert browser.post(REFRESH).status_code == 401


def test_logout_without_session_succeeds(browser: TestClient) -> None:
    assert browser.post(LOGOUT).status_code == 200


def test_password_change_signs_out_other_devices_only(db: Session) -> None:
    with (
        TestClient(app, base_url="https://testserver") as laptop,
        TestClient(app, base_url="https://testserver") as phone,
    ):
        access_token, password, user = _sign_in(laptop, db)
        phone_login = phone.post(
            LOGIN, data={"username": user.email, "password": password}
        )
        assert phone_login.status_code == 200

        r = laptop.patch(
            f"{ME}/password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"current_password": password, "new_password": "a-new-password-1"},
        )
        assert r.status_code == 200

        assert laptop.post(REFRESH).status_code == 200
        assert phone.post(REFRESH).status_code == 401


def test_invalid_access_token_is_unauthorized(client: TestClient) -> None:
    r = client.get(ME, headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
