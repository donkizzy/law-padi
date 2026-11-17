from sqlalchemy import ColumnElement
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.core.errors import DomainError, ErrorCode
from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if not is_email_conflict(exc):
            raise
        raise DomainError(
            ErrorCode.EMAIL_ALREADY_EXISTS,
            "The user with this email already exists in the system.",
        ) from exc
    session.refresh(db_obj)
    return db_obj


def update_user(
    *, session: Session, db_user: User, user_in: UserUpdate, commit: bool = True
) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    if user_data.get("email") and user_data["email"].lower() == db_user.email.lower():
        user_data["email"] = db_user.email
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    try:
        session.flush()
        if commit:
            session.commit()
            session.refresh(db_user)
    except IntegrityError as exc:
        session.rollback()
        if not is_email_conflict(exc):
            raise
        raise DomainError(
            ErrorCode.EMAIL_ALREADY_EXISTS, "User with this email already exists"
        ) from exc
    return db_user


def _email_matches(email: str) -> ColumnElement[bool]:
    """Mailbox providers ignore case, so one address is one account."""
    return func.lower(col(User.email)) == email.strip().lower()


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(_email_matches(email))
    session_user = session.exec(statement).one_or_none()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(
    *, session: Session, email: str, password: str, commit: bool = True
) -> User | None:
    statement = select(User).where(_email_matches(email))
    db_user = session.exec(
        statement.with_for_update().execution_options(populate_existing=True)
    ).one_or_none()
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
    if commit:
        session.commit()
    return db_user


def is_email_conflict(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == "23505" and getattr(
        getattr(exc.orig, "diag", None), "constraint_name", None
    ) in {"ux_user_email_lower", "ix_user_email"}
