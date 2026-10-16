"""Delete guest conversations nobody has touched for the retention period.

Guests can't reach a conversation once it has been idle this long (the API
already hides it), so keeping it only holds personal questions for no purpose.
Accounts' conversations are kept until the person deletes them or the account.

The free deployment has no cron, so the API calls this now and then while
handling new conversations. ``python -m app.retention`` runs it on demand.
"""

import logging
import random
from datetime import timedelta

from sqlalchemy import exists
from sqlmodel import Session, col, delete, select

from app.core.config import settings
from app.legal.models import Conversation, GenerationRun
from app.models import get_datetime_utc

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


def purge_idle_guest_conversations(
    session: Session, *, batch_size: int = BATCH_SIZE
) -> int:
    """Delete up to ``batch_size`` idle guest conversations; return how many."""
    cutoff = get_datetime_utc() - timedelta(
        days=settings.GUEST_CONVERSATION_RETENTION_DAYS
    )
    active_run = exists().where(
        col(GenerationRun.conversation_id) == Conversation.id,
        col(GenerationRun.status).in_(["pending", "running"]),
    )
    idle = (
        select(Conversation.id)
        .where(
            col(Conversation.user_id).is_(None),
            col(Conversation.updated_at) < cutoff,
            ~active_run,
        )
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    ids = list(session.exec(idle).all())
    if ids:
        # Messages, runs and evidence cascade in the database.
        session.exec(delete(Conversation).where(col(Conversation.id).in_(ids)))
    session.commit()
    return len(ids)


def maybe_purge_idle_guest_conversations(session: Session) -> None:
    """Purge occasionally, so the cost is spread thinly across requests."""
    if random.random() < 0.02:
        purge_idle_guest_conversations(session)


def main() -> None:
    from app.core.db import engine

    total = 0
    with Session(engine) as session:
        while deleted := purge_idle_guest_conversations(session):
            total += deleted
    logger.info("Deleted %d idle guest conversation(s).", total)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
