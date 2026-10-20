"""Reuse only unchanged pgvector documents from frozen composite members."""

import hashlib
import json
import struct
import uuid
from typing import Any

from sqlmodel import Session, col, select

from app.ingestion.pgvector_repository import embedding_sha256, validate_vector
from app.legal.models import (
    CorpusRelease,
    EmbeddingProfile,
    EmbeddingRun,
    IngestionArtifact,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
)


def profile_fingerprint(profile: EmbeddingProfile) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "provider": str(profile.provider),
                "model_name": profile.model_name,
                "model_revision": profile.model_revision,
                "dimensions": profile.vector_dimensions,
                "configuration": profile.configuration,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def member_document_vectors(
    session: Session,
    release: CorpusRelease,
    profile: EmbeddingProfile,
    documents: list[dict[str, Any]],
) -> dict[int, list[float]]:
    composition = (release.validation_report or {}).get("composition")
    if not composition:
        return {}
    member_ids = [uuid.UUID(member["release_id"]) for member in composition["members"]]
    runs = session.exec(
        select(EmbeddingRun).where(
            col(EmbeddingRun.release_id).in_(member_ids),
            EmbeddingRun.profile_id == profile.id,
            EmbeddingRun.status == "succeeded",
            col(EmbeddingRun.selected_for_release).is_(True),
        )
    ).all()
    run_ids = {
        run.id
        for run in runs
        if (run.metrics or {}).get("profile_fingerprint")
        == profile_fingerprint(profile)
    }
    builds = (
        session.exec(
            select(RetrievalIndexBuild).where(
                col(RetrievalIndexBuild.embedding_run_id).in_(run_ids),
                RetrievalIndexBuild.backend == "pgvector",
                col(RetrievalIndexBuild.status).in_(["ready", "promoted"]),
            )
        ).all()
        if run_ids
        else []
    )
    ready_ids = {
        build.embedding_run_id
        for build in builds
        if (build.validation_report or {}).get("is_valid") is True
    }
    if not ready_ids:
        return {}
    # PostgreSQL stores float32 vectors; the original checksum describes the
    # provider's float64 JSON. Verify both against the retained hashed artifact
    # rather than treating harmless storage rounding as corruption.
    from app.ingestion.service import get_blob_store

    originals: dict[tuple[uuid.UUID, str], list[float]] = {}
    artifacts = session.exec(
        select(IngestionArtifact).where(IngestionArtifact.artifact_type == "embeddings")
    ).all()
    for artifact in artifacts:
        key = (artifact.artifact_metadata or {}).get("embedding_run_id")
        if key not in {str(value) for value in ready_ids}:
            continue
        try:
            raw = get_blob_store().read_bytes(artifact.storage_key)
        except FileNotFoundError:
            continue
        if hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise ValueError("Member embedding artifact checksum mismatch")
        payload = json.loads(raw)
        for document, vector in zip(
            payload["documents"], payload["dense_vectors"], strict=True
        ):
            originals[
                (uuid.UUID(key), document["payload"]["retrieval_text_sha256"])
            ] = [float(value) for value in vector]
    rows = session.exec(
        select(RetrievalSegment, RetrievalEmbedding)
        .join(
            RetrievalEmbedding,
            col(RetrievalEmbedding.segment_id) == col(RetrievalSegment.id),
        )
        .where(
            col(RetrievalEmbedding.embedding_run_id).in_(ready_ids),
            col(RetrievalSegment.release_id).in_(member_ids),
        )
    ).all()
    by_hash: dict[str, tuple[str, list[float]]] = {}
    for segment, embedding in rows:
        vector = originals.get(
            (embedding.embedding_run_id, segment.retrieval_text_sha256)
        )
        if vector is None:
            continue
        validate_vector(vector, dimensions=profile.vector_dimensions)
        if embedding_sha256(vector) != embedding.embedding_sha256:
            raise ValueError(
                "Member embedding checksum mismatch; rebuild its index before reuse"
            )
        if struct.pack(f"{len(vector)}f", *vector) != struct.pack(
            f"{len(vector)}f", *embedding.embedding
        ):
            raise ValueError("Member stored vector differs from its retained artifact")
        by_hash.setdefault(
            segment.retrieval_text_sha256, (segment.retrieval_text, vector)
        )
    reusable: dict[int, list[float]] = {}
    for index, document in enumerate(documents):
        text = str(document["retrieval_text"])
        digest = hashlib.sha256(text.encode()).hexdigest()
        cached = by_hash.get(digest)
        if cached and cached[0] == text:
            reusable[index] = cached[1]
    return reusable
