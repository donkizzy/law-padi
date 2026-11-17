"""Metadata for instruments actually included in a selected release."""

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Concatenate, cast

from sqlmodel import Session, col, select

from app.legal.enums import LegalStatus
from app.legal.models import (
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
)


@contextmanager
def release_scope_cache(session: Session) -> Iterator[None]:
    """Reuse release metadata only for the duration of one retrieval operation."""
    if "retrieval_release_scope" in session.info:
        yield
        return
    session.info["retrieval_release_scope"] = {}
    try:
        yield
    finally:
        session.info.pop("retrieval_release_scope", None)


def with_release_scope[**P, T](
    function: Callable[Concatenate[Session, P], T],
) -> Callable[Concatenate[Session, P], T]:
    @wraps(function)
    def wrapped(session: Session, /, *args: P.args, **kwargs: P.kwargs) -> T:
        with release_scope_cache(session):
            return function(session, *args, **kwargs)

    return wrapped


def release_instruments(
    session: Session, release_id: uuid.UUID, *, index_kind: str = "enacted"
) -> dict[uuid.UUID, LegalInstrument]:
    cache = cast(
        dict[tuple[uuid.UUID, str], dict[uuid.UUID, LegalInstrument]] | None,
        session.info.get("retrieval_release_scope"),
    )
    key = (release_id, index_kind)
    if cache is not None and key in cache:
        return cache[key]
    instruments = _load_release_instruments(session, release_id, index_kind=index_kind)
    if cache is not None:
        cache[key] = instruments
    return instruments


def _load_release_instruments(
    session: Session, release_id: uuid.UUID, *, index_kind: str = "enacted"
) -> dict[uuid.UUID, LegalInstrument]:
    status = col(ProvisionVersion.legal_status)
    statement = (
        select(LegalInstrument)
        .join(Provision, col(Provision.instrument_id) == col(LegalInstrument.id))
        .join(ProvisionVersion, col(ProvisionVersion.provision_id) == col(Provision.id))
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.provision_version_id) == col(ProvisionVersion.id),
        )
        .where(
            CorpusReleaseEntry.release_id == release_id,
            status == LegalStatus.PROPOSED
            if index_kind == "proposals"
            else status != LegalStatus.PROPOSED,
        )
        .distinct()
    )
    return {instrument.id: instrument for instrument in session.exec(statement).all()}
