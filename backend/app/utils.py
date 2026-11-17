import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import emails
import jwt
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr, ValidationError

from app.core import security
from app.core.config import settings
from app.models import TokenPayload, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-templates" / template_name
    ).read_text()
    html_content = Template(template_str).render(context)
    return html_content


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    assert settings.EMAILS_FROM_EMAIL  # For type checker
    message = emails.message.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": settings.PROJECT_NAME, "email": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_verify_email_email(*, email_to: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Confirm your email address"
    link = f"{settings.FRONTEND_HOST}/verify-email?token={token}"
    html_content = render_email_template(
        template_name="verify_email.html",
        context={
            "project_name": project_name,
            "email": email_to,
            "valid_hours": settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_account_exists_email(*, email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - You already have an account"
    html_content = render_email_template(
        template_name="account_exists.html",
        context={
            "project_name": project_name,
            "email": email_to,
            "login_link": f"{settings.FRONTEND_HOST}/login",
            "reset_link": f"{settings.FRONTEND_HOST}/recover-password",
        },
    )
    return EmailData(html_content=html_content, subject=subject)


class AccountLink(TokenPayload):
    email: EmailStr


def _generate_account_link(
    *, user: User, email: str, token_type: str, lifetime_hours: int
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "exp": now + timedelta(hours=lifetime_hours),
            "nbf": now,
            "sub": str(user.id),
            "email": email,
            "auth_version": user.auth_version,
            "type": token_type,
        },
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def _verify_account_link(token: str, *, token_type: str) -> AccountLink | None:
    try:
        return AccountLink.model_validate(
            security.decode_token(token, token_type=token_type)
        )
    except InvalidTokenError, ValidationError:
        return None


def generate_password_reset_token(user: User) -> str:
    return _generate_account_link(
        user=user,
        email=user.email,
        token_type=security.PASSWORD_RESET_TOKEN_TYPE,
        lifetime_hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
    )


def verify_password_reset_token(token: str) -> AccountLink | None:
    return _verify_account_link(token, token_type=security.PASSWORD_RESET_TOKEN_TYPE)


def generate_email_change_token(*, user: User, email: str) -> str:
    return _generate_account_link(
        user=user,
        email=email,
        token_type=security.EMAIL_CHANGE_TOKEN_TYPE,
        lifetime_hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
    )


def verify_email_change_token(token: str) -> AccountLink | None:
    return _verify_account_link(token, token_type=security.EMAIL_CHANGE_TOKEN_TYPE)


def generate_email_verification_token(*, user_id: uuid.UUID, email: str) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {
            "exp": expires.timestamp(),
            "nbf": now,
            "sub": str(user_id),
            # Bind the link to the address it was sent to, so it stops working
            # if the account's email changes before it is used.
            "email": email,
            "type": security.EMAIL_VERIFICATION_TOKEN_TYPE,
        },
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def verify_email_verification_token(token: str) -> tuple[uuid.UUID, str] | None:
    try:
        decoded = security.decode_token(
            token, token_type=security.EMAIL_VERIFICATION_TOKEN_TYPE
        )
        return uuid.UUID(str(decoded["sub"])), str(decoded["email"])
    except InvalidTokenError, KeyError, ValueError:
        return None
