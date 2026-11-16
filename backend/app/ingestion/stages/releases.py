import uuid

from sqlmodel import Session, col, select

from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.service import (
    _release_source_and_review_gates,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    IngestionTask,
    Provision,
    ProvisionVersion,
)


def ensure_composite_member_gates(session: Session, release: CorpusRelease) -> None:
    if (release.validation_report or {}).get("composition") is not None:
        gates = _release_source_and_review_gates(
            session, release_entries(session, release.id), release=release
        )
        if gates:
            raise IngestionWorkerError(
                f"Composite member gates do not pass: {', '.join(gates)}"
            )


def get_release_for_task(session: Session, task: IngestionTask) -> CorpusRelease:
    release_id = task.payload.get("release_id")
    if not release_id:
        raise IngestionWorkerError("Task does not identify a corpus release")
    release = session.get(CorpusRelease, uuid.UUID(str(release_id)))
    if not release:
        raise IngestionWorkerError("Corpus release was not found")
    return release


def release_entries(
    session: Session, release_id: uuid.UUID
) -> list[CorpusReleaseEntry]:
    return list(
        session.exec(
            select(CorpusReleaseEntry)
            .where(CorpusReleaseEntry.release_id == release_id)
            .order_by(col(CorpusReleaseEntry.created_at))
        ).all()
    )


def versions_by_release_entry(
    entries: list[CorpusReleaseEntry], session: Session
) -> dict[uuid.UUID, ProvisionVersion]:
    versions: dict[uuid.UUID, ProvisionVersion] = {}
    for entry in entries:
        version = session.get(ProvisionVersion, entry.provision_version_id)
        if version:
            versions[version.id] = version
    return versions


def provisions_by_versions(
    versions_by_id: dict[uuid.UUID, ProvisionVersion], session: Session
) -> dict[uuid.UUID, Provision]:
    provisions: dict[uuid.UUID, Provision] = {}
    for version in versions_by_id.values():
        provision = session.get(Provision, version.provision_id)
        if not provision:
            continue
        provisions[provision.id] = provision
        parent_id = provision.parent_id
        while parent_id and parent_id not in provisions:
            parent = session.get(Provision, parent_id)
            if not parent:
                break
            provisions[parent.id] = parent
            parent_id = parent.parent_id
    return provisions
