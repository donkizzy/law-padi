from sqlmodel import Session, select

from app.core.errors import DomainError, ErrorCode
from app.legal.enums import (
    AdminRole,
)
from app.legal.models import (
    AdminRoleAssignment,
)
from app.models import User


def user_has_admin_role(session: Session, user: User, role: AdminRole) -> bool:
    if user.is_superuser:
        return True
    assignment = session.exec(
        select(AdminRoleAssignment).where(
            AdminRoleAssignment.user_id == user.id,
            AdminRoleAssignment.role == role,
            AdminRoleAssignment.revoked_at == None,  # noqa: E711
        )
    ).first()
    return assignment is not None


def require_admin_role(session: Session, user: User, role: AdminRole) -> None:
    if user_has_admin_role(session, user, role):
        return
    raise DomainError(
        ErrorCode.FORBIDDEN, "The user does not have the required admin role"
    )
