import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.legal.enums import AdminRole, AuditSeverity
from app.legal.models.common import get_datetime_utc


class AdminRoleAssignment(SQLModel, table=True):
    __tablename__ = "admin_role_assignment"
    __table_args__ = (
        Index(
            "ix_admin_role_assignment_active_unique",
            "user_id",
            "role",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        index=True,
        ondelete="CASCADE",
    )
    role: AdminRole = Field(
        sa_column=Column(String(length=64), nullable=False, index=True)
    )
    assigned_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
        ondelete="SET NULL",
    )
    action: str = Field(max_length=128, index=True)
    entity_type: str = Field(max_length=128, index=True)
    entity_id: uuid.UUID | None = Field(default=None, index=True)
    severity: AuditSeverity = Field(
        default=AuditSeverity.INFO,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
