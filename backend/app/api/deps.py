from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def authenticated_user(session: Session, token: str, *, lock: bool = False) -> User:
    try:
        token_data = TokenPayload(**security.decode_access_token(token))
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = session.get(
        User,
        token_data.sub,
        populate_existing=True,
        with_for_update=True if lock else None,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if token_data.auth_version != user.auth_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    return authenticated_user(session, token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_verified_user(current_user: CurrentUser) -> User:
    """A signed-in user whose email is confirmed; account syncing needs one."""
    if current_user.email_verified_at is None:
        raise HTTPException(
            status_code=403,
            detail="Confirm your email address to keep your research in your account.",
        )
    return current_user


VerifiedUser = Annotated[User, Depends(get_verified_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
