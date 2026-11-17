import uuid
from datetime import datetime
from typing import Any

from sqlmodel import SQLModel

from app.legal.enums import AdminRole, AuditSeverity


class AdminMetrics(SQLModel):
    active_runs: int
    blocked_runs: int
    failed_runs: int
    queue_depth: int
    worker_heartbeat: datetime | None = None
    pages_processed: int
    ocr_fallback_rate: float
    review_issues: int
    auto_approval_rate: float
    embedding_progress: float
    current_production_release: str | None = None


class AdminOperationalAlertPublic(SQLModel):
    id: str
    alert_type: str
    severity: AuditSeverity
    title: str
    message: str
    detected_at: datetime
    run_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    issue_id: uuid.UUID | None = None
    release_id: uuid.UUID | None = None
    embedding_run_id: uuid.UUID | None = None
    promotion_attempt_id: uuid.UUID | None = None
    evidence: dict[str, Any] | None = None


class AdminOperationalAlertsPublic(SQLModel):
    data: list[AdminOperationalAlertPublic]
    count: int


class MyAdminRolesPublic(SQLModel):
    user_id: uuid.UUID
    is_superuser: bool
    roles: list[AdminRole]


class AuditEventPublic(SQLModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    severity: AuditSeverity
    reason: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class AuditEventsPublic(SQLModel):
    data: list[AuditEventPublic]
    count: int
