import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.worker import (
    run_once,
)
from app.ingestion.workflow import create_run_steps, enqueue_task
from app.legal.enums import (
    IngestionArtifactType,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    PageInclusionStatus,
    PageRole,
)
from app.legal.models import (
    IngestionArtifact,
    IngestionStep,
    IngestionTask,
    SourcePage,
)
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.ingestion.worker.conftest import _stored_source_and_run


def test_worker_renders_confirmed_pages_and_stores_native_extraction_artifacts(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages(
        [
            f"Official copy {uuid.uuid4().hex}",
            f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}\n"
            "37. Right to private and family life",
        ]
    )
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    create_run_steps(db, run)
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=1,
            role=PageRole.FRONT_MATTER,
            inclusion_status=PageInclusionStatus.EXCLUDED,
            inclusion_reason="Front matter excluded",
        ),
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=2,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.INCLUDED,
            inclusion_reason="Legal body confirmed",
        ),
    ]
    db.add_all(pages)
    db.commit()
    rendering_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.RENDERING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=rendering_step,
        task_type=IngestionStage.RENDERING.value,
        idempotency_key=f"{run.id}:render",
        payload={"source_document_id": str(source.id)},
    )

    rendered = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.RENDERING.value,
    )
    extracted = run_once(
        db,
        worker_id="worker-test",
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
    )

    assert rendered is not None
    assert extracted is not None
    assert rendered.stage == IngestionStage.RENDERING
    assert extracted.stage == IngestionStage.NATIVE_EXTRACTION

    db.refresh(run)
    assert run.current_stage == IngestionStage.NORMALIZING
    skipped_steps = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage.in_(
                [IngestionStage.LOCAL_OCR, IngestionStage.MANAGED_OCR]
            ),
        )
    ).all()
    assert {step.status for step in skipped_steps} == {IngestionStepStatus.SKIPPED}
    page_records = db.exec(
        select(SourcePage)
        .where(SourcePage.run_id == run.id)
        .order_by(SourcePage.page_number)
    ).all()
    assert all(page.thumbnail_key for page in page_records)
    assert page_records[1].quality_signals
    assert page_records[1].quality_signals["native_extraction"]["span_count"] >= 1

    artifacts = db.exec(
        select(IngestionArtifact)
        .where(IngestionArtifact.run_id == run.id)
        .order_by(IngestionArtifact.artifact_type)
    ).all()
    thumbnail_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.PAGE_THUMBNAIL
    ]
    raw_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.RAW_EXTRACTION
    ]
    assert len(thumbnail_artifacts) == 2
    assert len(raw_artifacts) == 1
    assert raw_artifacts[0].source_page_id == page_records[1].id

    next_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.NORMALIZING.value,
        )
    ).one()
    assert next_task.status == IngestionTaskStatus.PENDING
