"""Regression tests for the November 2026 security audit's smaller fixes."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import crud
from app.core import rate_limit
from app.core.config import settings
from app.main import app
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


def test_one_account_is_throttled_across_many_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "p" * 32)
    monkeypatch.setattr(
        rate_limit, "LOGIN_PER_EMAIL", rate_limit.Limit("login-email-test", 2, 900)
    )
    email = random_email()
    statuses = []
    with TestClient(app) as client:
        for address in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
            statuses.append(
                client.post(
                    f"{API}/login/access-token",
                    data={"username": email, "password": "wrong-password"},
                    headers={
                        "x-origin-proxy-secret": "p" * 32,
                        "x-forwarded-for": address,
                    },
                ).status_code
            )
    assert statuses == [400, 400, 429]


def test_public_health_check_reports_readiness_only(client: TestClient) -> None:
    response = client.get(f"{API}/utils/health-check/")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.usefixtures("corpus")
def test_guest_cookie_stays_on_same_site_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    with TestClient(app, base_url="https://testserver") as guest:
        created = guest.post(f"{API}/conversations", json={})
    assert created.status_code == 201
    cookie = created.headers["set-cookie"].lower()
    assert "samesite=lax" in cookie


def test_email_case_does_not_create_or_hide_an_account(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    password = random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    shouted = email.upper()

    signed_in = client.post(
        f"{API}/login/access-token", data={"username": shouted, "password": password}
    )
    assert signed_in.status_code == 200

    signup = client.post(
        f"{API}/users/signup",
        json={"email": shouted, "password": random_lower_string()},
    )
    assert signup.status_code == 200
    count = db.exec(
        select(func.count()).select_from(User).where(func.lower(User.email) == email)
    ).one()
    assert count == 1
