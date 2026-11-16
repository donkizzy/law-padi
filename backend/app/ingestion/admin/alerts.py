from datetime import datetime

from sqlmodel import Session, col, select

from app.ingestion.common import enum_value, get_datetime_utc
from app.legal.enums import (
    AuditSeverity,
    EmbeddingRunStatus,
    IngestionRunStatus,
    IngestionTaskStatus,
    ReleasePromotionStatus,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.models import (
    EmbeddingRun,
    ExtractionCandidate,
    IngestionRun,
    IngestionTask,
    ReleasePromotionAttempt,
    ReviewIssue,
)
from app.legal.schemas import (
    AdminOperationalAlertPublic,
)

OPERATIONAL_ALERT_LIMIT = 100


def read_admin_operational_alerts(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int = OPERATIONAL_ALERT_LIMIT,
) -> list[AdminOperationalAlertPublic]:
    detected_now = now or get_datetime_utc()
    alerts: list[AdminOperationalAlertPublic] = []

    failed_runs = session.exec(
        select(IngestionRun)
        .where(IngestionRun.status == IngestionRunStatus.FAILED)
        .order_by(col(IngestionRun.updated_at).desc())
        .limit(limit)
    ).all()
    for run in failed_runs:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"run-failed:{run.id}",
                alert_type="terminal_failure",
                severity=AuditSeverity.HIGH,
                title="Terminal ingestion failure",
                message=alert_error_message(
                    run.error_details,
                    f"{enum_value(run.current_stage)} ended in a failed run.",
                ),
                detected_at=alert_time(detected_now, run.completed_at, run.updated_at),
                run_id=run.id,
                evidence={
                    "status": enum_value(run.status),
                    "stage": enum_value(run.current_stage),
                    "error_details": run.error_details,
                },
            )
        )

    stalled_tasks = session.exec(
        select(IngestionTask)
        .where(
            col(IngestionTask.status).in_(
                [IngestionTaskStatus.LEASED, IngestionTaskStatus.RUNNING]
            ),
            col(IngestionTask.leased_until) != None,  # noqa: E711
            col(IngestionTask.leased_until) < detected_now,
        )
        .order_by(col(IngestionTask.leased_until))
        .limit(limit)
    ).all()
    for task in stalled_tasks:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"stalled-lease:{task.id}",
                alert_type="stalled_lease",
                severity=AuditSeverity.WARNING,
                title="Stalled worker lease",
                message=(
                    f"{task.task_type} lease expired for "
                    f"{task.lease_owner or 'an unknown worker'}."
                ),
                detected_at=alert_time(detected_now, task.leased_until),
                run_id=task.run_id,
                step_id=task.step_id,
                task_id=task.id,
                evidence={
                    "task_type": task.task_type,
                    "status": enum_value(task.status),
                    "lease_owner": task.lease_owner,
                    "leased_until": task.leased_until.isoformat()
                    if task.leased_until
                    else None,
                    "heartbeat_at": task.heartbeat_at.isoformat()
                    if task.heartbeat_at
                    else None,
                },
            )
        )

    blocking_issues = session.exec(
        select(ReviewIssue)
        .where(
            ReviewIssue.status == ReviewIssueStatus.OPEN,
            ReviewIssue.blocking == True,  # noqa: E712
        )
        .order_by(col(ReviewIssue.created_at).desc())
        .limit(limit)
    ).all()
    for issue in blocking_issues:
        candidate = session.get(ExtractionCandidate, issue.candidate_id)
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"blocking-review-issue:{issue.id}",
                alert_type="unresolved_blocking_issue",
                severity=AuditSeverity.HIGH
                if issue.severity == ReviewIssueSeverity.BLOCKING
                else AuditSeverity.WARNING,
                title="Unresolved blocking review issue",
                message=issue.message,
                detected_at=issue.created_at,
                run_id=candidate.run_id if candidate else None,
                candidate_id=issue.candidate_id,
                issue_id=issue.id,
                evidence={
                    "issue_type": issue.issue_type,
                    "severity": enum_value(issue.severity),
                    "candidate_path": candidate.canonical_path if candidate else None,
                    "evidence": issue.evidence,
                },
            )
        )

    failed_embedding_runs = session.exec(
        select(EmbeddingRun)
        .where(EmbeddingRun.status == EmbeddingRunStatus.FAILED)
        .order_by(col(EmbeddingRun.created_at).desc())
        .limit(limit)
    ).all()
    for embedding_run in failed_embedding_runs:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"embedding-provider-outage:{embedding_run.id}",
                alert_type="embedding_provider_outage",
                severity=AuditSeverity.HIGH,
                title="Embedding provider outage",
                message=alert_error_message(
                    embedding_run.error_details,
                    "An embedding benchmark or indexing run failed.",
                ),
                detected_at=alert_time(
                    detected_now,
                    embedding_run.completed_at,
                    embedding_run.created_at,
                ),
                release_id=embedding_run.release_id,
                embedding_run_id=embedding_run.id,
                evidence={
                    "profile_id": str(embedding_run.profile_id),
                    "benchmark_dataset_version": (
                        embedding_run.benchmark_dataset_version
                    ),
                    "error_details": embedding_run.error_details,
                },
            )
        )

    failed_promotions = session.exec(
        select(ReleasePromotionAttempt)
        .where(ReleasePromotionAttempt.status == ReleasePromotionStatus.FAILED)
        .order_by(col(ReleasePromotionAttempt.created_at).desc())
        .limit(limit)
    ).all()
    for promotion in failed_promotions:
        alerts.append(
            AdminOperationalAlertPublic(
                id=f"publication-failed:{promotion.id}",
                alert_type="publication_failure",
                severity=AuditSeverity.HIGH,
                title="Publication failure",
                message=alert_error_message(
                    promotion.error_details,
                    "Corpus release publication failed before promotion completed.",
                ),
                detected_at=alert_time(
                    detected_now,
                    promotion.completed_at,
                    promotion.created_at,
                ),
                release_id=promotion.release_id,
                promotion_attempt_id=promotion.id,
                evidence={
                    "vector_index_id": str(promotion.vector_index_id)
                    if promotion.vector_index_id
                    else None,
                    "previous_release_id": str(promotion.previous_release_id)
                    if promotion.previous_release_id
                    else None,
                    "target_collection_name": promotion.target_collection_name,
                    "rollback_completed": promotion.rollback_completed,
                    "error_details": promotion.error_details,
                },
            )
        )

    alerts.sort(key=lambda alert: alert.detected_at, reverse=True)
    return alerts[:limit]


def alert_time(fallback: datetime, *values: datetime | None) -> datetime:
    for value in values:
        if value is not None:
            return value
    return fallback


def alert_error_message(
    error_details: dict[str, object] | None,
    fallback: str,
) -> str:
    if not error_details:
        return fallback
    for key in ("message", "error", "detail", "reason"):
        value = error_details.get(key)
        if isinstance(value, str) and value.strip():
            return value
    code = error_details.get("code")
    if isinstance(code, str) and code.strip():
        return f"{fallback} ({code})"
    return fallback
