"""Transactional Cloud Tasks publication, with crash-safe redispatch.

Only run identifiers enter the queue. The generation lease, provider reservation,
and durable events remain authoritative in PostgreSQL.
"""

import base64
import hashlib
import json
import logging
import uuid
from datetime import timedelta

import httpx
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.legal.models import GenerationRun, TransactionalOutbox, get_datetime_utc

CHAT_DISPATCH_EVENT = "chat_generation.dispatch"
_logger = logging.getLogger(__name__)
_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)


def stage_dispatch(session: Session, run: GenerationRun) -> TransactionalOutbox | None:
    """Add dispatch intent in the run's transaction; callers hold its row lock.

    An unpublished intent always keeps its task name on publication retries. A
    recovered retrieval attempt or a sufficiently old, missing delivery gets a
    fresh name because Cloud Tasks retains completed task-name tombstones.
    """
    if settings.CHAT_DISPATCH_MODE != "cloud_tasks" or run.status != "pending":
        return None
    latest = session.exec(
        select(TransactionalOutbox)
        .where(
            TransactionalOutbox.event_type == CHAT_DISPATCH_EVENT,
            TransactionalOutbox.aggregate_id == run.id,
        )
        .order_by(
            col(TransactionalOutbox.created_at).desc(),
            col(TransactionalOutbox.id).desc(),
        )
        .limit(1)
    ).first()
    now = get_datetime_utc()
    if latest and latest.payload.get("generation_attempt") == run.attempt_count:
        if latest.published_at is None or latest.published_at > now - timedelta(
            seconds=settings.CHAT_TASK_REDISPATCH_SECONDS
        ):
            return latest
    sequence = int(latest.payload.get("dispatch_attempt", 0)) + 1 if latest else 0
    outbox = TransactionalOutbox(
        aggregate_type="generation_run",
        aggregate_id=run.id,
        event_type=CHAT_DISPATCH_EVENT,
        idempotency_key=f"chat.dispatch.{run.id}.{sequence}",
        payload={
            "run_id": str(run.id),
            "generation_attempt": run.attempt_count,
            "dispatch_attempt": sequence,
        },
    )
    session.add(outbox)
    return outbox


def _enqueue(event: TransactionalOutbox) -> None:
    """Use the runtime service identity, never a long-lived credentials file."""
    parent = (
        f"projects/{settings.GCP_PROJECT_ID}/locations/{settings.GCP_TASKS_LOCATION}"
        f"/queues/{settings.GCP_CHAT_QUEUE}"
    )
    handler_origin = settings.CHAT_TASK_HANDLER_URL.rstrip("/")
    identifier = hashlib.sha256(event.idempotency_key.encode()).hexdigest()
    task = {
        "name": f"{parent}/tasks/chat-{identifier}",
        "dispatchDeadline": f"{settings.CHAT_TASK_DISPATCH_DEADLINE_SECONDS}s",
        "httpRequest": {
            "httpMethod": "POST",
            "url": f"{handler_origin}/internal/chat/run",
            "headers": {"Content-Type": "application/json"},
            "body": base64.b64encode(
                json.dumps({"run_id": str(event.aggregate_id)}).encode()
            ).decode(),
            "oidcToken": {
                "serviceAccountEmail": settings.CHAT_TASK_SERVICE_ACCOUNT,
                "audience": settings.CHAT_TASK_AUDIENCE or handler_origin,
            },
        },
    }
    with httpx.Client(timeout=5, trust_env=False) as client:
        token_response = client.get(
            _METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"}
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        response = client.post(
            f"https://cloudtasks.googleapis.com/v2/{parent}/tasks",
            headers={"Authorization": f"Bearer {token}"},
            json={"task": task},
        )
        # A task may have been created before the publisher lost its response or
        # its database transaction. Its deterministic name closes that gap.
        if (
            response.status_code == 409
            and response.json().get("error", {}).get("status") == "ALREADY_EXISTS"
        ):
            return
        response.raise_for_status()


def publish_dispatches(*, run_id: uuid.UUID | None = None, limit: int = 20) -> int:
    """Publish this event type only; failed intents remain available for retry."""
    if settings.CHAT_DISPATCH_MODE != "cloud_tasks":
        return 0
    published = 0
    # Commit each row independently: a late failure does not roll back earlier
    # successful publications and the transaction holds at most one network call.
    for _ in range(limit):
        with Session(engine) as session:
            statement = (
                select(TransactionalOutbox)
                .where(
                    TransactionalOutbox.event_type == CHAT_DISPATCH_EVENT,
                    col(TransactionalOutbox.published_at).is_(None),
                )
                .order_by(col(TransactionalOutbox.created_at))
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if run_id is not None:
                statement = statement.where(TransactionalOutbox.aggregate_id == run_id)
            event = session.exec(statement).first()
            if event is None:
                break
            run = session.get(GenerationRun, event.aggregate_id)
            if (
                run is None
                or run.status != "pending"
                or event.payload.get("generation_attempt") != run.attempt_count
            ):
                # Deleted, terminal or already claimed runs need no extra task.
                event.published_at = get_datetime_utc()
                event.error_message = None
                session.add(event)
                session.commit()
                continue
            event.attempt_count += 1
            try:
                _enqueue(event)
            except Exception as exc:
                # Do not store HTTP headers, access tokens or provider payloads.
                event.error_message = type(exc).__name__
                session.add(event)
                session.commit()
                _logger.warning("chat_task_enqueue_failed %s", type(exc).__name__)
                break
            event.published_at = get_datetime_utc()
            event.error_message = None
            session.add(event)
            session.commit()
            published += 1
    return published


def dispatch_run(run_id: uuid.UUID) -> int:
    """Best-effort post-commit publication; durable intent survives failures."""
    if settings.CHAT_DISPATCH_MODE != "cloud_tasks":
        return 0
    try:
        with Session(engine) as session:
            run = session.exec(
                select(GenerationRun)
                .where(GenerationRun.id == run_id)
                .with_for_update(skip_locked=True)
            ).first()
            if run is None:
                return 0
            stage_dispatch(session, run)
            session.commit()
        return publish_dispatches(run_id=run_id, limit=2)
    except Exception as exc:
        _logger.warning("chat_task_dispatch_deferred %s", type(exc).__name__)
        return 0


def reconcile_dispatches() -> int:
    """Recover missing publications and expired retrieval leases on demand."""
    from app.chat.worker import expire_guest_conversations, recover_expired

    recover_expired()
    expire_guest_conversations()
    if settings.CHAT_DISPATCH_MODE != "cloud_tasks":
        return 0
    with Session(engine) as session:
        runs = session.exec(
            select(GenerationRun)
            .where(GenerationRun.status == "pending")
            .order_by(col(GenerationRun.created_at))
            .with_for_update(skip_locked=True)
            .limit(settings.CHAT_TASK_RECONCILE_LIMIT)
        ).all()
        for run in runs:
            stage_dispatch(session, run)
        session.commit()
    return publish_dispatches(limit=settings.CHAT_TASK_RECONCILE_LIMIT)
