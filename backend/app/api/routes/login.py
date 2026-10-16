from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security, sessions
from app.core.config import settings
from app.models import Message, NewPassword, Token, User, UserPublic, UserUpdate
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


RefreshCookie = Annotated[str | None, Cookie(alias=sessions.REFRESH_COOKIE)]


def _access_token(user: User) -> Token:
    return Token(
        access_token=security.create_access_token(
            user.id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    )


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    OAuth2 compatible token login. Returns a short-lived access token and sets
    the HttpOnly refresh cookie that renews it.
    """
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    sessions.set_refresh_cookie(
        response, sessions.issue_refresh_token(session=session, user=user)
    )
    return _access_token(user)


@router.post(
    "/login/refresh",
    response_model=Token,
    responses={401: {"model": Message, "description": "No usable session"}},
)
def refresh_access_token(
    session: SessionDep, response: Response, refresh_token: RefreshCookie = None
) -> Token | JSONResponse:
    """
    Exchange the refresh cookie for a new access token, rotating the cookie.
    """
    rotated = (
        sessions.rotate_refresh_token(session=session, token=refresh_token)
        if refresh_token
        else None
    )
    if rotated is None:
        expired = JSONResponse(
            {"detail": "Session expired"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        sessions.clear_refresh_cookie(expired)
        return expired
    user, new_refresh_token = rotated
    sessions.set_refresh_cookie(response, new_refresh_token)
    return _access_token(user)


@router.post("/login/logout")
def logout(
    session: SessionDep, response: Response, refresh_token: RefreshCookie = None
) -> Message:
    """
    End this browser's session. Safe to call when already signed out.
    """
    if refresh_token:
        sessions.revoke_refresh_token(session=session, token=refresh_token)
    sessions.clear_refresh_cookie(response)
    return Message(message="Signed out")


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    user = crud.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    user_in_update = UserUpdate(password=body.new_password)
    crud.update_user(
        session=session,
        db_user=user,
        user_in=user_in_update,
    )
    sessions.revoke_user_sessions(session=session, user_id=user.id)
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
