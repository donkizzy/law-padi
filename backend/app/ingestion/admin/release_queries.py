import uuid

from sqlmodel import Session, func, select

from app.legal.models import (
    CorpusReleaseEntry,
)


def release_entry_count(session: Session, release_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(CorpusReleaseEntry)
        .where(CorpusReleaseEntry.release_id == release_id)
    ).one()
