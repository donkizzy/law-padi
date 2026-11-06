import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User
from app.utils import (
    generate_email_verification_token,
    generate_password_reset_token,
)
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


@pytest.fixture
def mail() -> Generator[MagicMock]:
    """Turn email on and capture what would be sent."""
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "info@example.com"),
        patch("app.api.routes.users.send_email") as send_email,
    ):
        yield send_email


@pytest.fixture
def rate_limits() -> Generator[None]:
    with patch.object(settings, "RATE_LIMIT_ENABLED", True):
        yield


def _signed_in_user(
    client: TestClient, db: Session, *, password: str | None = None
) -> tuple[User, dict[str, str]]:
    email = random_email()
    password = password or random_lower_string()
    r = client.post(f"{API}/users/signup", json={"email": email, "password": password})
    assert r.status_code == 200
    user = db.exec(select(User).where(User.email == email)).one()
    headers = user_authentication_headers(client=client, email=email, password=password)
    return user, headers


def _link_token(send_email: MagicMock) -> str:
    html = send_email.call_args.kwargs["html_content"]
    return html.split("/verify-email?token=")[1].split('"')[0]


def test_signup_sends_verification_link_that_confirms_email(
    client: TestClient, db: Session, mail: MagicMock
) -> None:
    user, _ = _signed_in_user(client, db)
    assert user.email_verified_at is None
    mail.assert_called_once()
    assert mail.call_args.kwargs["email_to"] == user.email

    r = client.post(f"{API}/users/verify-email", json={"token": _link_token(mail)})
    assert r.status_code == 200
    db.refresh(user)
    assert user.email_verified_at is not None


def test_verified_state_is_public_on_me(
    client: TestClient, db: Session, mail: MagicMock
) -> None:
    user, headers = _signed_in_user(client, db)
    assert (
        client.get(f"{API}/users/me", headers=headers).json()["email_verified_at"]
        is None
    )
    client.post(f"{API}/users/verify-email", json={"token": _link_token(mail)})
    assert client.get(f"{API}/users/me", headers=headers).json()["email_verified_at"]


def test_verification_link_for_old_address_stops_working(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    token = generate_email_verification_token(user_id=user.id, email="old@example.com")
    r = client.post(f"{API}/users/verify-email", json={"token": token})
    assert r.status_code == 400
    assert r.json()["detail"] == "This link is invalid or has expired"


def test_verification_rejects_garbage_and_unknown_users(client: TestClient) -> None:
    for token in (
        "not-a-token",
        generate_email_verification_token(user_id=uuid.uuid4(), email="a@b.com"),
    ):
        r = client.post(f"{API}/users/verify-email", json={"token": token})
        assert r.status_code == 400


def test_changing_email_requires_confirming_the_new_one(
    client: TestClient, db: Session, mail: MagicMock
) -> None:
    password = random_lower_string()
    user, headers = _signed_in_user(client, db, password=password)
    client.post(f"{API}/users/verify-email", json={"token": _link_token(mail)})
    old_email = user.email
    new_email = random_email()

    r = client.post(
        f"{API}/users/me/email-change",
        headers=headers,
        json={"email": new_email, "current_password": password},
    )
    assert r.status_code == 200
    db.refresh(user)
    assert user.email == old_email
    assert user.email_verified_at is not None
    assert mail.call_args.kwargs["email_to"] == new_email
    token = _link_token(mail)

    assert (
        client.post(f"{API}/users/verify-email", json={"token": token}).status_code
        == 200
    )
    db.refresh(user)
    assert user.email == new_email
    assert user.email_verified_at is not None
    assert client.get(f"{API}/users/me", headers=headers).status_code == 401
    assert (
        client.post(f"{API}/users/verify-email", json={"token": token}).status_code
        == 400
    )


def test_email_change_request_does_not_reveal_address_ownership(
    client: TestClient, db: Session, mail: MagicMock
) -> None:
    password = random_lower_string()
    user, headers = _signed_in_user(client, db, password=password)
    original_email = user.email
    occupied = create_random_user(db)

    existing_response = client.post(
        f"{API}/users/me/email-change",
        headers=headers,
        json={"email": occupied.email, "current_password": password},
    )
    existing_token = _link_token(mail)
    available_response = client.post(
        f"{API}/users/me/email-change",
        headers=headers,
        json={"email": random_email(), "current_password": password},
    )
    assert existing_response.status_code == available_response.status_code == 200
    assert existing_response.json() == available_response.json()

    r = client.post(f"{API}/users/verify-email", json={"token": existing_token})
    assert r.status_code == 400
    db.refresh(user)
    assert user.email == original_email


def test_email_change_rejects_incorrect_password(
    client: TestClient, db: Session, mail: MagicMock
) -> None:
    _, headers = _signed_in_user(client, db)
    mail.reset_mock()
    response = client.post(
        f"{API}/users/me/email-change",
        headers=headers,
        json={"email": random_email(), "current_password": "wrong-password"},
    )
    assert response.status_code == 400
    mail.assert_not_called()


def test_resend_verification_email(
    client: TestClient, db: Session, mail: MagicMock
) -> None:
    _, headers = _signed_in_user(client, db)
    mail.reset_mock()
    r = client.post(f"{API}/users/me/verification-email", headers=headers)
    assert r.status_code == 200
    mail.assert_called_once()


def test_resend_when_email_is_off_says_so(client: TestClient, db: Session) -> None:
    with patch("app.core.config.settings.SMTP_HOST", None):
        _, headers = _signed_in_user(client, db)
        r = client.post(f"{API}/users/me/verification-email", headers=headers)
    assert r.status_code == 503


def test_password_reset_confirms_email(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    assert user.email_verified_at is None
    r = client.post(
        f"{API}/reset-password/",
        json={
            "token": generate_password_reset_token(user),
            "new_password": "a-brand-new-password",
        },
    )
    assert r.status_code == 200
    db.refresh(user)
    assert user.email_verified_at is not None


def test_link_tokens_cannot_be_used_to_sign_in(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    for token in (
        generate_email_verification_token(user_id=user.id, email=user.email),
        generate_password_reset_token(user),
    ):
        r = client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_access_tokens_cannot_reset_passwords(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    access_token = normal_user_token_headers["Authorization"].removeprefix("Bearer ")
    r = client.post(
        f"{API}/reset-password/",
        json={"token": access_token, "new_password": "a-brand-new-password"},
    )
    assert r.status_code == 400


@pytest.mark.usefixtures("rate_limits")
def test_login_is_rate_limited_per_account(client: TestClient) -> None:
    email = random_email()
    statuses = [
        client.post(
            f"{API}/login/access-token",
            data={"username": email, "password": "wrong-password"},
        ).status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429


@pytest.mark.usefixtures("rate_limits")
def test_rate_limited_response_says_when_to_retry(client: TestClient) -> None:
    email = random_email()
    for _ in range(3):
        client.post(f"{API}/password-recovery/{email}")
    r = client.post(f"{API}/password-recovery/{email}")
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    assert r.json()["detail"].startswith("Too many attempts. Try again in ")


@pytest.mark.usefixtures("rate_limits", "mail")
def test_forwarded_ip_is_ignored_without_the_edge_proxy(client: TestClient) -> None:
    # Rotating X-Forwarded-For must not dodge the per-IP sign-up limit.
    statuses = [
        client.post(
            f"{API}/users/signup",
            headers={"X-Forwarded-For": f"198.51.100.{n}"},
            json={"email": random_email(), "password": random_lower_string()},
        ).status_code
        for n in range(11)
    ]
    assert statuses[-1] == 429
