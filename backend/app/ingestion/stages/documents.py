import uuid
from typing import Any

from sqlmodel import Session

from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.stages.artifacts import json_object, latest_artifact_with_metadata
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionArtifactType,
)
from app.legal.models import (
    IngestionRun,
)


def retrieval_documents_payload(
    session: Session, run: IngestionRun, release_id: uuid.UUID
) -> dict[str, Any]:
    artifact = latest_artifact_with_metadata(
        session,
        run=run,
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS,
        key="release_id",
        value=str(release_id),
    )
    if not artifact:
        raise IngestionWorkerError("Run does not have retrieval document artifacts")
    return json_object(get_blob_store().read_bytes(artifact.storage_key))
