from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"

# Every token this app signs names its purpose, so a password-reset or
# email-verification link can never be replayed as a sign-in.
ACCESS_TOKEN_TYPE = "access"
PASSWORD_RESET_TOKEN_TYPE = "password-reset"
EMAIL_VERIFICATION_TOKEN_TYPE = "email-verification"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject), "type": ACCESS_TOKEN_TYPE}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str, *, token_type: str) -> dict[str, Any]:
    """Decode a signed token, raising ``InvalidTokenError`` for the wrong purpose."""
    payload: dict[str, Any] = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[ALGORITHM]
    )
    if payload.get("type") != token_type:
        raise jwt.InvalidTokenError("Token has the wrong purpose")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, token_type=ACCESS_TOKEN_TYPE)


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
