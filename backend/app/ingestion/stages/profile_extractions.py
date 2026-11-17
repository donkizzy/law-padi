import hashlib
import json
from dataclasses import asdict
from typing import Any

from sqlmodel import Session

from app.ingestion.extraction import PageExtraction, TextSpan
from app.ingestion.stages.artifacts import (
    ensure_artifact,
    latest_artifact_with_metadata,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import IngestionArtifactType
from app.legal.models import IngestionRun


def profile_extractions(
    session: Session, run: IngestionRun, key: str
) -> list[PageExtraction] | None:
    artifact = latest_artifact_with_metadata(
        session,
        run=run,
        artifact_type=IngestionArtifactType.RAW_EXTRACTION,
        key="profile_checkpoint_key",
        value=key,
    )
    if not artifact:
        session.commit()
        return None
    storage_key, checksum = artifact.storage_key, artifact.sha256
    session.commit()
    content = get_blob_store().read_bytes(storage_key)
    if hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError("Profile extraction artifact checksum mismatch")
    pages: list[dict[str, Any]] = json.loads(content)
    return [
        PageExtraction(
            page_number=int(page["page_number"]),
            text=str(page["text"]),
            spans=[TextSpan(**span) for span in page["spans"]],
            method=str(page["method"]),
            provider_version=str(page["provider_version"]),
            confidence=float(page["confidence"]),
            timing_ms=float(page["timing_ms"]),
            quality_flags=page["quality_flags"],
            plain_text=str(page.get("plain_text", "")),
        )
        for page in pages
    ]


def retain_profile_extractions(
    session: Session, run: IngestionRun, key: str, extractions: list[PageExtraction]
) -> None:
    content = json.dumps(
        [asdict(page) for page in extractions], sort_keys=True
    ).encode()
    digest = hashlib.sha256(content).hexdigest()
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RAW_EXTRACTION.value,
        filename=f"profile-native-{key[:12]}-{digest[:12]}.json",
        content=content,
        content_type="application/json",
    )
    ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.RAW_EXTRACTION,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={"kind": "profile_native_pages", "profile_checkpoint_key": key},
    )
    session.commit()
