from typing import Any

from sqlmodel import Session, select

from app.ingestion.extraction import NATIVE_PDF_EXTRACTOR_VERSION
from app.ingestion.ocr import (
    AZURE_DOCUMENT_INTELLIGENCE_PROVIDER_VERSION,
    GOOGLE_DOCUMENT_AI_PROVIDER_VERSION,
    LOCAL_LAYOUT_OCR_PROVIDER_VERSION,
    LOCAL_OCR_PROVIDER_VERSION,
)
from app.ingestion.stages.artifacts import sha256_json
from app.legal.enums import IngestionArtifactType, IngestionStage
from app.legal.models import IngestionArtifact, IngestionRun, SourceDocument


def page_checkpoint_key(
    source: SourceDocument, stage: IngestionStage, provider: object | None = None
) -> str:
    configuration = {
        name: getattr(provider, name, None)
        for name in (
            "processor_name",
            "endpoint",
            "endpoint_url",
            "model_id",
            "api_version",
            "language",
            "preserve_lines",
        )
    }
    return sha256_json(
        {
            "source_sha256": source.sha256,
            "stage": stage.value,
            "provider": type(provider).__qualname__,
            "configuration": configuration,
            "versions": [
                "page-checkpoint-v1",
                "poppler-thumbnail-v1",
                NATIVE_PDF_EXTRACTOR_VERSION,
                LOCAL_OCR_PROVIDER_VERSION,
                LOCAL_LAYOUT_OCR_PROVIDER_VERSION,
                GOOGLE_DOCUMENT_AI_PROVIDER_VERSION,
                AZURE_DOCUMENT_INTELLIGENCE_PROVIDER_VERSION,
            ],
        }
    )


def completed_pages(
    session: Session, run: IngestionRun, artifact_type: IngestionArtifactType, key: str
) -> dict[int, dict[str, Any]]:
    artifacts = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == artifact_type,
        )
    ).all()
    return {
        int(metadata["page_number"]): dict(metadata)
        for artifact in artifacts
        if (metadata := artifact.artifact_metadata or {}).get("checkpoint_key") == key
    }
