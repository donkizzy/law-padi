from datetime import timedelta
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import rate_limit, security, sessions
from app.core.config import settings
from app.models import (
    Message,
    NewPassword,
    Token,
    User,
    UserPublic,
    get_datetime_utc,
)
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
            auth_version=user.auth_version,
        )
    )


def require_trusted_browser_origin(request: Request) -> None:
    """Keep browser forms from changing sessions outside the trusted frontend."""
    origins = request.headers.getlist("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    if origins == [settings.FRONTEND_HOST.rstrip("/")]:
        return
    if fetch_site == "same-origin" and (
        not origins or origins == [f"{request.url.scheme}://{request.url.netloc}"]
    ):
        return
    if not origins and fetch_site is None:
        # OAuth clients and other non-browser API callers send neither header.
        return
    raise HTTPException(status_code=403, detail="Untrusted request origin")


@router.post(
    "/login/access-token", dependencies=[Depends(require_trusted_browser_origin)]
)
def login_access_token(
    session: SessionDep,
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    OAuth2 compatible token login. Returns a short-lived access token and sets
    the HttpOnly refresh cookie that renews it.
    """
    ip = rate_limit.client_ip(request)
    rate_limit.enforce(session, rate_limit.LOGIN_PER_IP, ip)
    rate_limit.enforce(
        session, rate_limit.LOGIN_PER_ACCOUNT, f"{ip}|{form_data.username}"
    )
    user = crud.authenticate(
        session=session,
        email=form_data.username,
        password=form_data.password,
        commit=False,
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    refresh_token = sessions.issue_refresh_token(session=session, user=user)
    access_token = _access_token(user)
    session.commit()
    sessions.set_refresh_cookie(response, refresh_token)
    return access_token


@router.post(
    "/login/refresh",
    response_model=Token,
    responses={401: {"model": Message, "description": "No usable session"}},
    dependencies=[Depends(require_trusted_browser_origin)],
)
def refresh_access_token(
    session: SessionDep,
    request: Request,
    response: Response,
    refresh_token: RefreshCookie = None,
) -> Token | JSONResponse:
    """
    Exchange the refresh cookie for a new access token, rotating the cookie.
    """
    rate_limit.enforce(
        session, rate_limit.REFRESH_PER_IP, rate_limit.client_ip(request)
    )
    rotated = (
        sessions.rotate_refresh_token(session=session, token=refresh_token)
        if refresh_token
        else None
    )
    if rotated is None:
        session.commit()
        expired = JSONResponse(
            {"detail": "Session expired"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        sessions.clear_refresh_cookie(expired)
        return expired
    user, new_refresh_token = rotated
    access_token = _access_token(user)
    session.commit()
    sessions.set_refresh_cookie(response, new_refresh_token)
    return access_token


@router.post("/login/logout", dependencies=[Depends(require_trusted_browser_origin)])
def logout(
    session: SessionDep, response: Response, refresh_token: RefreshCookie = None
) -> Message:
    """
    End this browser's session. Safe to call when already signed out.
    """
    if refresh_token:
        sessions.revoke_refresh_token(session=session, token=refresh_token)
        session.commit()
    sessions.clear_refresh_cookie(response)
    return Message(message="Signed out")


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(
    email: str, session: SessionDep, request: Request, background: BackgroundTasks
) -> Message:
    """
    Password Recovery
    """
    rate_limit.enforce(
        session, rate_limit.RECOVERY_PER_IP, rate_limit.client_ip(request)
    )
    rate_limit.enforce(session, rate_limit.RECOVERY_PER_EMAIL, email)
    user = crud.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user and settings.emails_enabled:
        password_reset_token = generate_password_reset_token(user)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        # Sent after the response, so timing doesn't reveal registered emails.
        background.add_task(
            send_email,
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(session: SessionDep, request: Request, body: NewPassword) -> Message:
    """
    Reset password
    """
    rate_limit.enforce(session, rate_limit.RESET_PER_IP, rate_limit.client_ip(request))
    claims = verify_password_reset_token(token=body.token)
    user = (
        session.get(User, claims.sub, populate_existing=True, with_for_update=True)
        if claims
        else None
    )
    if (
        claims is None
        or user is None
        or user.email != claims.email
        or user.auth_version != claims.auth_version
    ):
        raise HTTPException(status_code=400, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    user.hashed_password = security.get_password_hash(body.new_password)
    if user.email_verified_at is None:
        # Following the reset link proves the person controls this inbox.
        user.email_verified_at = get_datetime_utc()
    sessions.invalidate_credentials(session, user)
    session.commit()
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
    password_reset_token = generate_password_reset_token(user)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
