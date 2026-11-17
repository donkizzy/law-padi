import json
import uuid
from typing import cast

from sqlmodel import Session, col, select

from app.core.errors import DomainError, ErrorCode
from app.ingestion.admin.queries import get_release
from app.ingestion.blob_store import (
    BlobStoreError,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionArtifactType,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    AuditEvent,
    CorpusRelease,
    CorpusReleaseEntry,
    IngestionArtifact,
    ReleasePromotionAttempt,
    RetrievalIndexBuild,
    SourceDocument,
    VectorIndex,
)


def read_corpus_release_manifest(
    session: Session, release_id: uuid.UUID
) -> tuple[CorpusRelease, IngestionArtifact, dict[str, object]]:
    release = get_release(session, release_id)
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.artifact_type == IngestionArtifactType.RELEASE_MANIFEST
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).all()
    artifact = next(
        (
            item
            for item in artifacts
            if str((item.artifact_metadata or {}).get("release_id")) == str(release.id)
        ),
        None,
    )
    if not artifact:
        raise DomainError(
            ErrorCode.NOT_FOUND, "Release manifest artifact was not found"
        )
    try:
        manifest = json.loads(get_blob_store().read_bytes(artifact.storage_key))
    except (BlobStoreError, json.JSONDecodeError) as exc:
        raise DomainError(
            ErrorCode.BAD_GATEWAY, "Release manifest artifact could not be read"
        ) from exc
    if not isinstance(manifest, dict):
        raise DomainError(ErrorCode.BAD_GATEWAY, "Release manifest artifact is invalid")
    return release, artifact, cast(dict[str, object], manifest)


def read_corpus_release_publication_evidence(
    session: Session, release_id: uuid.UUID
) -> tuple[
    CorpusRelease,
    list[VectorIndex],
    list[RetrievalIndexBuild],
    list[ReleasePromotionAttempt],
    list[uuid.UUID],
    list[AuditEvent],
    list[ActiveRetrievalTarget],
]:
    release = get_release(session, release_id)
    vector_indexes = list(
        session.exec(
            select(VectorIndex)
            .where(VectorIndex.release_id == release.id)
            .order_by(col(VectorIndex.updated_at).desc())
        ).all()
    )
    retrieval_index_builds = list(
        session.exec(
            select(RetrievalIndexBuild)
            .where(RetrievalIndexBuild.release_id == release.id)
            .order_by(col(RetrievalIndexBuild.updated_at).desc())
        ).all()
    )
    promotion_attempts = list(
        session.exec(
            select(ReleasePromotionAttempt)
            .where(ReleasePromotionAttempt.release_id == release.id)
            .order_by(col(ReleasePromotionAttempt.created_at).desc())
        ).all()
    )
    release_entries = list(
        session.exec(
            select(CorpusReleaseEntry).where(
                CorpusReleaseEntry.release_id == release.id
            )
        ).all()
    )
    source_ids = [
        entry.source_document_id
        for entry in release_entries
        if entry.source_document_id
    ]
    sources = (
        list(
            session.exec(
                select(SourceDocument).where(col(SourceDocument.id).in_(source_ids))
            ).all()
        )
        if source_ids
        else []
    )
    source_uploader_ids = sorted(
        {source.created_by for source in sources if source.created_by},
        key=str,
    )
    override_events = list(
        session.exec(
            select(AuditEvent)
            .where(
                AuditEvent.action == "corpus_release.publish_override",
                AuditEvent.entity_id == release.id,
            )
            .order_by(col(AuditEvent.created_at).desc())
        ).all()
    )
    active_targets = list(
        session.exec(
            select(ActiveRetrievalTarget)
            .where(ActiveRetrievalTarget.release_id == release.id)
            .order_by(ActiveRetrievalTarget.index_kind)
        ).all()
    )
    return (
        release,
        vector_indexes,
        retrieval_index_builds,
        promotion_attempts,
        source_uploader_ids,
        override_events,
        active_targets,
    )
