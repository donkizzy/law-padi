import hashlib
import json
from typing import cast

from sqlmodel import Session, select

from app.ingestion.embedding import (
    DenseEmbeddingProvider,
    EmbeddingBatch,
)
from app.ingestion.runtime.control import check_stage_continue
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.stages.artifacts import (
    ensure_artifact,
    float_vector,
    json_object,
    sha256_json,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionArtifactType,
)
from app.legal.models import (
    EmbeddingProfile,
    EmbeddingRun,
    IngestionArtifact,
    IngestionRun,
)


def embed_with_checkpoints(
    session: Session,
    *,
    run: IngestionRun,
    profile: EmbeddingProfile,
    embedding_run: EmbeddingRun,
    provider: DenseEmbeddingProvider,
    texts: list[str],
    batch_size: int,
    kind: str,
) -> EmbeddingBatch:
    size = max(1, batch_size)
    if len(texts) <= size:
        session.commit()
        check_stage_continue(session)
        return provider.embed(texts)
    artifacts = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.EMBEDDINGS,
        )
    ).all()
    checkpoints = {
        item.artifact_metadata.get("checkpoint_key"): item
        for item in artifacts
        if item.artifact_metadata and item.artifact_metadata.get("checkpoint_key")
    }
    vectors: list[list[float]] = []
    first: EmbeddingBatch | None = None
    costs: list[float | None] = []
    for offset in range(0, len(texts), size):
        check_stage_continue(session)
        inputs = texts[offset : offset + size]
        key = sha256_json(
            {
                "profile_id": str(profile.id),
                "model_name": profile.model_name,
                "model_revision": profile.model_revision,
                "provider": str(profile.provider),
                "vector_dimensions": profile.vector_dimensions,
                "configuration": profile.configuration,
                "kind": kind,
                "offset": offset,
                "inputs": inputs,
            }
        )
        cached = checkpoints.get(key)
        session.commit()
        if cached:
            content = get_blob_store().read_bytes(cached.storage_key)
            if hashlib.sha256(content).hexdigest() != cached.sha256:
                raise IngestionWorkerError("Embedding checkpoint hash mismatch")
            payload = json_object(content)
            raw_vectors = payload["vectors"]
            batch = EmbeddingBatch(
                provider=str(payload["provider"]),
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[float_vector(value) for value in raw_vectors],
                cost_usd=payload.get("cost_usd"),
                metrics=payload.get("metrics"),
            )
        else:
            batch = provider.embed(inputs)
            if len(batch.vectors) != len(inputs) or any(
                len(vector) != profile.vector_dimensions for vector in batch.vectors
            ):
                raise IngestionWorkerError(
                    "Embedding batch count or dimensions mismatch"
                )
            content = json.dumps(
                {
                    "provider": batch.provider,
                    "vectors": batch.vectors,
                    "cost_usd": batch.cost_usd,
                    "metrics": batch.metrics,
                },
                sort_keys=True,
            ).encode()
            content_hash = hashlib.sha256(content).hexdigest()
            blob = get_blob_store().put_artifact(
                run_id=str(run.id),
                artifact_type=IngestionArtifactType.EMBEDDINGS.value,
                filename=f"batch-{key}-{content_hash}.json",
                content=content,
                content_type="application/json",
            )
            ensure_artifact(
                session,
                run_id=run.id,
                artifact_type=IngestionArtifactType.EMBEDDINGS,
                storage_key=blob.key,
                sha256=blob.sha256,
                mime_type=blob.content_type,
                metadata={
                    "checkpoint_key": key,
                    "profile_id": str(profile.id),
                    "kind": kind,
                    "offset": offset,
                    "input_count": len(inputs),
                },
            )
        if len(batch.vectors) != len(inputs) or any(
            len(vector) != profile.vector_dimensions for vector in batch.vectors
        ):
            raise IngestionWorkerError(
                "Embedding checkpoint count or dimensions mismatch"
            )
        first = first or batch
        vectors.extend(batch.vectors)
        costs.append(batch.cost_usd)
        embedding_run.metrics = {
            **(embedding_run.metrics or {}),
            f"{kind}_progress": {
                "completed": len(vectors),
                "total": len(texts),
                "batch_size": size,
            },
        }
        session.add(embedding_run)
        session.commit()
    assert first is not None
    return EmbeddingBatch(
        provider=first.provider,
        model_name=first.model_name,
        model_revision=first.model_revision,
        vectors=vectors,
        cost_usd=(
            sum(cast(list[float], costs))
            if all(cost is not None for cost in costs)
            else None
        ),
        metrics={**(first.metrics or {}), "batched_batches": len(costs)},
    )
