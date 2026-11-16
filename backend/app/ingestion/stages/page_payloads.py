from typing import Any

from sqlmodel import Session, col, select

from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.stages.artifacts import json_object
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    IngestionArtifactType,
)
from app.legal.models import (
    IngestionArtifact,
    IngestionRun,
)


def raw_extraction_payloads(
    session: Session, run: IngestionRun
) -> list[dict[str, Any]]:
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.RAW_EXTRACTION,
        )
        .order_by(col(IngestionArtifact.storage_key))
    ).all()
    payloads = [
        json_object(get_blob_store().read_bytes(artifact.storage_key))
        for artifact in artifacts
    ]
    return sorted(payloads, key=lambda payload: int(payload["page_number"]))


def ocr_output_payloads(session: Session, run: IngestionRun) -> list[dict[str, Any]]:
    artifacts = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.OCR_OUTPUT,
        )
        .order_by(col(IngestionArtifact.storage_key))
    ).all()
    payloads = [
        json_object(get_blob_store().read_bytes(artifact.storage_key))
        for artifact in artifacts
    ]
    return sorted(payloads, key=lambda payload: int(payload["page_number"]))


def best_extraction_payloads(
    session: Session, run: IngestionRun
) -> list[dict[str, Any]]:
    ocr_by_page = {
        int(payload["page_number"]): payload
        for payload in ocr_output_payloads(session, run)
    }
    selected_payloads: list[dict[str, Any]] = []
    for raw_payload in raw_extraction_payloads(session, run):
        page_number = int(raw_payload["page_number"])
        flags = raw_payload.get("quality_flags")
        quality_flags = flags if isinstance(flags, dict) else {}
        should_use_ocr = (
            quality_flags.get("needs_ocr")
            or not str(raw_payload.get("text") or "").strip()
        )
        selected_payloads.append(
            ocr_by_page[page_number]
            if should_use_ocr and page_number in ocr_by_page
            else raw_payload
        )
    return sorted(selected_payloads, key=lambda payload: int(payload["page_number"]))


def normalized_pages_payload(session: Session, run: IngestionRun) -> dict[str, Any]:
    artifact = session.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.NORMALIZED_PAGES,
        )
        .order_by(col(IngestionArtifact.created_at).desc())
    ).first()
    if not artifact:
        raise IngestionWorkerError("Run does not have normalized page artifacts")
    return json_object(get_blob_store().read_bytes(artifact.storage_key))
