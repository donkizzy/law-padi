from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import event, update
from sqlmodel import Session, col

from app.ingestion.runtime.errors import IngestionLeaseLost
from app.legal.enums import IngestionTaskStatus
from app.legal.models import IngestionTask


@dataclass(frozen=True)
class TaskLease:
    task_id: UUID
    worker_id: str | None
    version: int

    @classmethod
    def from_task(cls, task: IngestionTask) -> TaskLease:
        # attempt_count changes only when a task is claimed. Heartbeats and
        # status transitions can change lock_version without changing ownership.
        return cls(task.id, task.lease_owner, task.attempt_count)


def update_owned_task(
    session: Session, lease: TaskLease, values: dict[str, Any]
) -> None:
    statement = (
        update(IngestionTask)
        .where(
            col(IngestionTask.id) == lease.task_id,
            col(IngestionTask.lease_owner) == lease.worker_id,
            col(IngestionTask.attempt_count) == lease.version,
            col(IngestionTask.status).in_(
                (IngestionTaskStatus.LEASED, IngestionTaskStatus.RUNNING)
            ),
        )
        .values(**values)
        .returning(col(IngestionTask.id))
    )
    # Use the connection to avoid autoflushing untrusted stage writes before
    # the fence has locked and verified the task row in this transaction.
    if (
        lease.worker_id is None
        or session.connection().execute(statement).first() is None
    ):
        raise IngestionLeaseLost("Task lease is no longer owned by this worker")


@contextmanager
def fence_stage_writes(session: Session, lease: TaskLease) -> Iterator[None]:
    """Fence every stage flush/commit, including intermediate checkpoints."""

    def check_lease(*_args: object) -> None:
        update_owned_task(session, lease, {"id": lease.task_id})

    event.listen(session, "before_flush", check_lease)
    event.listen(session, "before_commit", check_lease)
    try:
        yield
    finally:
        event.remove(session, "before_flush", check_lease)
        event.remove(session, "before_commit", check_lease)
