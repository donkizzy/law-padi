import hashlib
import json
import uuid
from typing import Any, cast

from sqlmodel import Session, col, select

from app.ingestion.runtime.errors import IngestionWorkerError
from app.legal.enums import (
    IngestionArtifactType,
)
from app.legal.models import (
    IngestionArtifact,
    IngestionRun,
)


def ensure_artifact(
    session: Session,
    *,
    run_id: uuid.UUID,
    source_page_id: uuid.UUID | None = None,
    artifact_type: IngestionArtifactType,
    storage_key: str,
    sha256: str | None,
    mime_type: str | None,
    retention_policy: str = "retain_indefinitely",
    metadata: dict[str, Any],
) -> IngestionArtifact:
    existing = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run_id,
            IngestionArtifact.artifact_type == artifact_type,
            IngestionArtifact.storage_key == storage_key,
        )
    ).first()
    if existing:
        return existing
    artifact = IngestionArtifact(
        run_id=run_id,
        source_page_id=source_page_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        sha256=sha256,
        mime_type=mime_type,
        retention_policy=retention_policy,
        artifact_metadata=metadata,
    )
    session.add(artifact)
    return artifact


def sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def latest_artifact_with_metadata(
    session: Session,
    *,
    run: IngestionRun,
    artifact_type: IngestionArtifactType,
    key: str,
    value: str,
) -> IngestionArtifact | None:
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == artifact_type,
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).all()
    for artifact in artifacts:
        metadata = artifact.artifact_metadata or {}
        if str(metadata.get(key)) == value:
            return artifact
    return None


def payload_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise IngestionWorkerError(f"Ingestion artifact did not contain {key}")
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise IngestionWorkerError(f"Ingestion artifact {key} item was invalid")
        items.append(cast(dict[str, Any], item))
    return items


def float_vector(value: object) -> list[float]:
    if not isinstance(value, list):
        raise IngestionWorkerError("Dense vector was not a list")
    vector: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise IngestionWorkerError("Dense vector contained a non-number")
        vector.append(float(item))
    return vector


def json_object(content: bytes) -> dict[str, Any]:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise IngestionWorkerError("Ingestion artifact did not contain a JSON object")
    return cast(dict[str, Any], payload)
