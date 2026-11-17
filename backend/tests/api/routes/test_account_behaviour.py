import html
import re
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app import crud
from app.core import rate_limit
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User, UserCreate
from app.utils import generate_email_change_token, verify_password_reset_token
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email

API = settings.API_V1_STR


def test_admin_sends_a_password_link_after_the_response(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "test@example.test")
    email, password = random_email(), "Original-Password-123"
    with (
        patch("app.api.routes.users.send_email") as send,
        patch.object(BackgroundTasks, "add_task") as queue,
    ):
        response = client.post(
            f"{API}/users/",
            headers=superuser_token_headers,
            json={"email": email, "password": password},
        )
    assert response.status_code == 200
    send.assert_not_called()
    queue.assert_called_once()
    args = queue.call_args
    assert args.args == (send,)
    assert args.kwargs["email_to"] == email
    content = html.unescape(args.kwargs["html_content"])
    assert password not in content
    match = re.search(r"/reset-password\?token=([^\"\s<]+)", content)
    assert match
    token = match[1]
    claims = verify_password_reset_token(token)
    assert claims and claims.email == email
    assert response.json()["email_verified_at"] is None
    reset = client.post(
        f"{API}/reset-password/",
        json={"token": token, "new_password": "Chosen-Password-456"},
    )
    assert reset.status_code == 200
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    db.refresh(user)
    assert user.email_verified_at is not None
    assert crud.authenticate(
        session=db, email=email.upper(), password="Chosen-Password-456"
    )
    assert not crud.authenticate(session=db, email=email, password=password)


def test_database_rejects_case_duplicate_accounts(db: Session) -> None:
    email = random_email()
    user = crud.create_user(
        session=db, user_create=UserCreate(email=email, password="Password-123")
    )
    user_id = user.id
    db.add(
        User(
            email=email.upper(), hashed_password=get_password_hash("Other-Password-123")
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert crud.get_user_by_email(session=db, email=email.upper()).id == user_id


def test_signup_race_keeps_the_generic_response(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    crud.create_user(
        session=db, user_create=UserCreate(email=email, password="Password-123")
    )
    with patch("app.api.routes.users.crud.get_user_by_email", return_value=None):
        response = client.post(
            f"{API}/users/signup",
            json={"email": email.upper(), "password": "Other-Password-123"},
        )
    assert response.status_code == 200
    from app.api.routes.users import SIGNUP_MESSAGE

    assert response.json() == {"message": SIGNUP_MESSAGE}
    assert (
        db.exec(
            select(func.count())
            .select_from(User)
            .where(func.lower(User.email) == email)
        ).one()
        == 1
    )


def test_case_duplicate_email_cannot_be_verified(
    client: TestClient, db: Session
) -> None:
    existing = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="Password-123"),
    )
    other = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="Password-123"),
    )
    original_email, original_version = other.email, other.auth_version
    token = generate_email_change_token(user=other, email=existing.email.upper())
    response = client.post(f"{API}/users/verify-email", json={"token": token})
    assert response.status_code == 400
    assert response.json() == {
        "detail": "This link is invalid or has expired",
        "code": "invalid_token",
    }
    db.refresh(other)
    assert other.email == original_email
    assert other.auth_version == original_version


def test_case_only_admin_update_preserves_verification_and_sessions(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    from app.models import get_datetime_utc

    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="Password-123"),
    )
    user.email_verified_at = get_datetime_utc()
    db.add(user)
    db.commit()
    version = user.auth_version
    headers = user_authentication_headers(
        client=client, email=user.email, password="Password-123"
    )
    response = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"email": user.email.upper()},
    )
    assert response.status_code == 200
    db.refresh(user)
    assert user.email_verified_at is not None
    assert user.auth_version == version
    assert client.get(f"{API}/users/me", headers=headers).status_code == 200


@pytest.mark.parametrize(
    "path,payload,status,detail,code",
    [
        (
            "/login/access-token",
            {"username": "unknown@example.test", "password": "wrong"},
            400,
            "Incorrect email or password",
            "invalid_credentials",
        ),
        (
            "/reset-password/",
            {"token": "invalid", "new_password": "Password-123"},
            400,
            "Invalid token",
            "invalid_token",
        ),
        ("/users/me", None, 401, "Not authenticated", "not_authenticated"),
    ],
)
def test_errors_include_stable_codes(
    client: TestClient,
    path: str,
    payload: dict | None,
    status: int,
    detail: str,
    code: str,
) -> None:
    if payload is None:
        response = client.get(f"{API}{path}")
    elif path.startswith("/login"):
        response = client.post(f"{API}{path}", data=payload)
    else:
        response = client.post(f"{API}{path}", json=payload)
    assert response.status_code == status
    assert response.json() == {"detail": detail, "code": code}
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def test_refresh_error_has_a_code_and_clears_the_cookie(client: TestClient) -> None:
    client.cookies.clear()
    response = client.post(f"{API}/login/refresh")
    assert response.status_code == 401
    assert response.json() == {"detail": "Session expired", "code": "session_expired"}
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_validation_error_keeps_details_and_adds_code(client: TestClient) -> None:
    response = client.post(
        f"{API}/users/signup", json={"email": "bad", "password": "short"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_rate_limit_domain_error_maps_to_http(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(
        rate_limit, "LOGIN_PER_IP", rate_limit.Limit(f"test-{random_email()}", 0, 60)
    )
    response = client.post(
        f"{API}/login/access-token",
        data={"username": random_email(), "password": "wrong"},
    )
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limit_exceeded"
    assert response.json()["detail"].startswith("Too many attempts. Try again in ")
    assert int(response.headers["retry-after"]) > 0


@pytest.mark.parametrize("operation,status", [("create", 400), ("update", 409)])
def test_admin_duplicate_races_have_stable_errors(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    operation: str,
    status: int,
) -> None:
    existing = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="Password-123"),
    )
    other = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="Password-123"),
    )
    existing_email, other_id = existing.email, other.id
    with patch("app.api.routes.users.crud.get_user_by_email", return_value=None):
        if operation == "create":
            response = client.post(
                f"{API}/users/",
                headers=superuser_token_headers,
                json={"email": existing_email.upper(), "password": "Password-456"},
            )
        else:
            response = client.patch(
                f"{API}/users/{other_id}",
                headers=superuser_token_headers,
                json={"email": existing_email.upper()},
            )
    assert response.status_code == status
    assert response.json() == {
        "detail": (
            "The user with this email already exists in the system."
            if operation == "create"
            else "User with this email already exists"
        ),
        "code": "email_already_exists",
    }
    db.refresh(other)
    assert other.email != existing_email


def test_case_only_email_change_does_not_send_another_confirmation(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="Password-123"),
    )
    email = user.email
    headers = user_authentication_headers(
        client=client, email=email, password="Password-123"
    )
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "test@example.test")
    with patch("app.api.routes.users.send_email") as send:
        response = client.post(
            f"{API}/users/me/email-change",
            headers=headers,
            json={"email": email.upper(), "current_password": "Password-123"},
        )
    assert response.status_code == 200
    send.assert_not_called()
    db.refresh(user)
    assert user.email == email
