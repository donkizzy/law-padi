import uuid
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    TokenDep,
    authenticated_user,
    get_current_active_superuser,
)
from app.core import rate_limit, sessions
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    AccountDeletion,
    EmailChangeRequest,
    EmailVerification,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    get_datetime_utc,
)
from app.utils import (
    generate_account_exists_email,
    generate_email_change_token,
    generate_email_verification_token,
    generate_new_account_email,
    generate_verify_email_email,
    send_email,
    verify_email_change_token,
    verify_email_verification_token,
)

SIGNUP_MESSAGE = "Check your email to confirm your address, then log in."


def send_verification_email(user: User, background: BackgroundTasks) -> None:
    """Queue a verification link, sent after the response so SMTP never slows it."""
    if not settings.emails_enabled:
        return
    email_data = generate_verify_email_email(
        email_to=user.email,
        token=generate_email_verification_token(user_id=user.id, email=user.email),
    )
    background.add_task(
        send_email,
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )


router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *,
    session: SessionDep,
    user_in: UserUpdateMe,
    current_user: CurrentUser,
) -> Any:
    """
    Update own user.
    """

    current_user.sqlmodel_update(user_in.model_dump(exclude_unset=True))
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.post("/me/email-change")
def request_email_change(
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
    token: TokenDep,
    body: EmailChangeRequest,
) -> Message:
    user_id = authenticated_user(session, token).id
    rate_limit.enforce(
        session, rate_limit.EMAIL_CHANGE_PER_IP, rate_limit.client_ip(request)
    )
    rate_limit.enforce(session, rate_limit.EMAIL_CHANGE_PER_USER, str(user_id))
    rate_limit.enforce(session, rate_limit.EMAIL_CHANGE_PER_ADDRESS, body.email)
    user = authenticated_user(session, token, lock=True)
    verified, _ = verify_password(body.current_password, user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if not settings.emails_enabled:
        raise HTTPException(
            status_code=503, detail="Email isn't available right now. Try again later."
        )
    if body.email != user.email:
        email_data = generate_verify_email_email(
            email_to=body.email,
            token=generate_email_change_token(user=user, email=body.email),
        )
        background.add_task(
            send_email,
            email_to=body.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    session.commit()
    return Message(message="Check the new email address to confirm the change.")


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *,
    session: SessionDep,
    response: Response,
    body: UpdatePassword,
    token: TokenDep,
) -> Any:
    """
    Update own password.
    """
    current_user = authenticated_user(session, token, lock=True)
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    # Sign out every other device, then keep this browser signed in.
    current_user.hashed_password = get_password_hash(body.new_password)
    sessions.invalidate_credentials(session, current_user)
    refresh_token = sessions.issue_refresh_token(session=session, user=current_user)
    session.commit()
    sessions.set_refresh_cookie(response, refresh_token)
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, token: TokenDep, body: AccountDeletion) -> Any:
    """
    Delete own user. A copied access token alone can't erase the account.
    """
    user_id = authenticated_user(session, token).id
    rate_limit.enforce(session, rate_limit.ACCOUNT_DELETION_PER_USER, str(user_id))
    current_user = authenticated_user(session, token, lock=True)
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=Message)
def register_user(
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
    user_in: UserRegister,
) -> Message:
    """
    Create a new account without signing in.

    The response is the same whether or not the email is already registered,
    so sign-up can't be used to discover who has an account. The owner of an
    existing address gets an email instead.
    """
    rate_limit.enforce(session, rate_limit.SIGNUP_PER_IP, rate_limit.client_ip(request))
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        # Spend the same hashing time as a real sign-up.
        get_password_hash(user_in.password)
        if settings.emails_enabled:
            email_data = generate_account_exists_email(email_to=user.email)
            background.add_task(
                send_email,
                email_to=user.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        return Message(message=SIGNUP_MESSAGE)
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    send_verification_email(user, background)
    return Message(message=SIGNUP_MESSAGE)


@router.post("/verify-email", response_model=Message)
def verify_email(
    session: SessionDep, request: Request, body: EmailVerification
) -> Message:
    """
    Confirm an email address with the token from a verification link.
    """
    rate_limit.enforce(session, rate_limit.VERIFY_PER_IP, rate_limit.client_ip(request))
    change = verify_email_change_token(body.token)
    if change is not None:
        user = session.get(
            User, change.sub, populate_existing=True, with_for_update=True
        )
        if (
            user is None
            or not user.is_active
            or user.auth_version != change.auth_version
        ):
            raise HTTPException(
                status_code=400, detail="This link is invalid or has expired"
            )
        user.email = change.email
        user.email_verified_at = get_datetime_utc()
        try:
            sessions.invalidate_credentials(session, user)
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            raise HTTPException(
                status_code=400, detail="This link is invalid or has expired"
            ) from exc
        return Message(message="Email confirmed")

    claims = verify_email_verification_token(body.token)
    user = session.get(User, claims[0], with_for_update=True) if claims else None
    if claims is None or user is None or user.email != claims[1]:
        raise HTTPException(
            status_code=400, detail="This link is invalid or has expired"
        )
    if user.email_verified_at is None:
        user.email_verified_at = get_datetime_utc()
        session.add(user)
        session.commit()
    return Message(message="Email confirmed")


@router.post("/me/verification-email", response_model=Message)
def resend_verification_email(
    session: SessionDep, background: BackgroundTasks, current_user: CurrentUser
) -> Message:
    """
    Send the signed-in user a fresh verification link.
    """
    if current_user.email_verified_at is not None:
        return Message(message="Email already confirmed")
    rate_limit.enforce(
        session, rate_limit.VERIFICATION_EMAIL_PER_USER, str(current_user.id)
    )
    if not settings.emails_enabled:
        raise HTTPException(
            status_code=503, detail="Email isn't available right now. Try again later."
        )
    send_verification_email(current_user, background)
    return Message(message="Verification email sent")


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id, populate_existing=True, with_for_update=True)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    email_changed = user_in.email is not None and user_in.email != db_user.email
    active_changed = (
        user_in.is_active is not None and user_in.is_active != db_user.is_active
    )
    role_changed = (
        user_in.is_superuser is not None
        and user_in.is_superuser != db_user.is_superuser
    )
    db_user = crud.update_user(
        session=session, db_user=db_user, user_in=user_in, commit=False
    )
    if email_changed:
        db_user.email_verified_at = None
    if user_in.password or email_changed or active_changed or role_changed:
        sessions.invalidate_credentials(session, db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
