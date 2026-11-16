import uuid
from typing import Any

from sqlmodel import Session, col, select

from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    ExtractionCandidate,
    IngestionRun,
    Provision,
    ProvisionVersion,
    SourceDocument,
)


def materialized_run_ids_by_version(
    session: Session, version_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    if not version_ids:
        return {}
    candidates = session.exec(
        select(ExtractionCandidate)
        .where(col(ExtractionCandidate.materialized_version_id).in_(version_ids))
        .order_by(col(ExtractionCandidate.updated_at))
    ).all()
    run_ids_by_version: dict[uuid.UUID, uuid.UUID] = {}
    for candidate in candidates:
        if candidate.materialized_version_id:
            run_ids_by_version[candidate.materialized_version_id] = candidate.run_id
    return run_ids_by_version


def release_manifest(
    session: Session,
    *,
    release: CorpusRelease,
    run: IngestionRun,
    source: SourceDocument,
    entries: list[CorpusReleaseEntry],
) -> dict[str, Any]:
    manifest_entries = []
    source_document_ids: set[uuid.UUID] = {source.id}
    ingestion_run_ids: set[uuid.UUID] = {run.id}
    for entry in entries:
        version = session.get(ProvisionVersion, entry.provision_version_id)
        if not version:
            continue
        provision = session.get(Provision, version.provision_id)
        if not provision:
            continue
        if entry.source_document_id:
            source_document_ids.add(entry.source_document_id)
        if entry.ingestion_run_id:
            ingestion_run_ids.add(entry.ingestion_run_id)
        manifest_entries.append(
            {
                "canonical_path": provision.canonical_path,
                "provision_id": str(provision.id),
                "provision_version_id": str(version.id),
                "text_sha256": version.text_sha256,
                "source_document_id": str(version.source_document_id),
                "source_page_start": version.source_page_start,
                "source_page_end": version.source_page_end,
            }
        )
    source_documents = manifest_source_documents(session, source_document_ids)
    return {
        "manifest_version": 1,
        "release_id": str(release.id),
        "release_version": release.version,
        "materialized_run_id": str(run.id),
        "ingestion_run_ids": sorted(str(run_id) for run_id in ingestion_run_ids),
        "source_document_ids": sorted(
            str(source_document_id) for source_document_id in source_document_ids
        ),
        "source_documents": source_documents,
        "entries": sorted(
            manifest_entries, key=lambda item: str(item["canonical_path"])
        ),
    }


def manifest_source_documents(
    session: Session, source_document_ids: set[uuid.UUID]
) -> list[dict[str, object]]:
    if not source_document_ids:
        return []
    sources = session.exec(
        select(SourceDocument)
        .where(col(SourceDocument.id).in_(source_document_ids))
        .order_by(col(SourceDocument.created_at), col(SourceDocument.id))
    ).all()
    return [
        {
            "source_document_id": str(source.id),
            "title": source.title,
            "authority": source.authority,
            "source_url": source.source_url,
            "sha256": source.sha256,
            "storage_key": source.storage_key,
            "published_at": source.published_at.isoformat(),
            "retrieved_at": source.retrieved_at.isoformat(),
            "verification_status": str(source.verification_status),
            "is_legal_revision": source.is_legal_revision,
            "legal_revision_effective_at": source.legal_revision_effective_at.isoformat()
            if source.legal_revision_effective_at
            else None,
        }
        for source in sources
    ]
