"""Metadata for instruments actually included in a selected release."""

import uuid

from sqlmodel import Session, col, select

from app.legal.enums import LegalStatus
from app.legal.models import (
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
)


def release_instruments(
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
