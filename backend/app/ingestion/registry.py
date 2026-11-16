from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.types import StageHandler
from app.ingestion.stages.embedding import (
    handle_building_retrieval_documents,
    handle_embedding,
)
from app.ingestion.stages.indexing import handle_indexing, handle_validating_index
from app.ingestion.stages.materialize import handle_materializing
from app.ingestion.stages.pages import (
    handle_local_ocr,
    handle_managed_ocr,
    handle_native_extraction,
    handle_normalizing,
    handle_profiling,
    handle_rendering,
)
from app.ingestion.stages.parsing import (
    handle_parsing_structure,
    handle_validating_document,
)
from app.ingestion.stages.upload import handle_malware_scan, handle_verifying_upload
from app.legal.enums import (
    IngestionStage,
)


def handler_for(stage: IngestionStage) -> StageHandler:
    handlers: dict[IngestionStage, StageHandler] = {
        IngestionStage.VERIFYING_UPLOAD: handle_verifying_upload,
        IngestionStage.MALWARE_SCAN: handle_malware_scan,
        IngestionStage.PROFILING: handle_profiling,
        IngestionStage.RENDERING: handle_rendering,
        IngestionStage.NATIVE_EXTRACTION: handle_native_extraction,
        IngestionStage.LOCAL_OCR: handle_local_ocr,
        IngestionStage.MANAGED_OCR: handle_managed_ocr,
        IngestionStage.NORMALIZING: handle_normalizing,
        IngestionStage.PARSING_STRUCTURE: handle_parsing_structure,
        IngestionStage.VALIDATING_DOCUMENT: handle_validating_document,
        IngestionStage.MATERIALIZING: handle_materializing,
        IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS: handle_building_retrieval_documents,
        IngestionStage.EMBEDDING: handle_embedding,
        IngestionStage.INDEXING: handle_indexing,
        IngestionStage.VALIDATING_INDEX: handle_validating_index,
    }
    try:
        return handlers[stage]
    except KeyError:
        raise IngestionWorkerError(f"No worker handler is registered for {stage.value}")
