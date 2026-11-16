import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.worker import (
    NORMALIZER_VERSION,
    run_until_idle,
)
from app.ingestion.workflow import enqueue_task
from app.legal.enums import (
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    ProvisionKind,
)
from app.legal.models import (
    ExtractionCandidate,
    IngestionArtifact,
    IngestionStep,
    ReviewIssue,
)
from app.legal.parser import PARSER_VERSION, legal_text_sha256, normalize_legal_text
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.ingestion.worker.conftest import (
    _clear_run_tasks,
    _create_legal_grade_dataset,
    _instrument_slug,
    _store_raw_extraction,
    _stored_source_and_run,
)


def test_worker_normalizes_parses_candidates_and_blocks_for_review(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=5)

    assert [result.stage for result in results] == [
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    ]
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW

    normalized_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.NORMALIZED_PAGES,
        )
    ).one()
    assert normalized_artifact.artifact_metadata == {
        "normalizer_version": NORMALIZER_VERSION,
        "page_count": 1,
    }

    candidates = db.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.run_id == run.id)
        .order_by(ExtractionCandidate.sort_key)
    ).all()
    instrument_slug = _instrument_slug(db, source)
    assert [candidate.canonical_path for candidate in candidates] == [
        f"{instrument_slug}.chapter4",
        f"{instrument_slug}.chapter4.part1",
        f"{instrument_slug}.chapter4.part1.section37",
        f"{instrument_slug}.chapter4.part1.section37.subsection1",
    ]
    section = candidates[2]
    assert section.raw_text == (
        "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert section.normalized_text == normalize_legal_text(section.raw_text)
    assert section.text_sha256 == legal_text_sha256(section.raw_text)
    assert section.source_spans
    assert section.source_spans[0]["bbox"]["x1"] > section.source_spans[0]["bbox"]["x0"]
    assert section.ancestor_headings == ["Fundamental Rights", "Rights"]
    assert section.parser_version == PARSER_VERSION
    assert section.extractor_confidence == 0.96
    assert section.status == ExtractionCandidateStatus.NEEDS_REVIEW
    subsection = candidates[-1]
    assert subsection.kind == ProvisionKind.SUBSECTION
    assert subsection.parent_candidate_id == section.id
    assert subsection.raw_text == (
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert subsection.ancestor_headings == [
        "Fundamental Rights",
        "Rights",
        "Right to private and family life",
    ]

    review_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.REVIEW,
        )
    ).one()
    assert review_step.status == IngestionStepStatus.BLOCKED


def test_parse_stage_auto_approves_only_with_gold_calibration_policy(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    instrument_slug = _instrument_slug(db, source)
    section_text = (
        "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    gold_dataset_version = f"ng-constitution-gold-{uuid.uuid4().hex}"
    _create_legal_grade_dataset(
        db,
        version=gold_dataset_version,
        canonical_path=f"{instrument_slug}.chapter4.part1.section37",
        section_number="37",
        text=section_text,
        source_page_start=1,
        source_page_end=1,
        source_spans=[
            {
                "page_number": 1,
                "bbox": {"x0": 36.0, "y0": 422.0, "x1": 240.0, "y1": 434.0},
            },
            {
                "page_number": 1,
                "bbox": {"x0": 36.0, "y0": 408.0, "x1": 240.0, "y1": 420.0},
            },
        ],
    )
    run.pipeline_config = {
        "instrument_parser": "constitution",
        "auto_approval_policy": {
            "enabled": True,
            "gold_dataset_version": gold_dataset_version,
        },
    }
    db.add(run)
    db.commit()
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize-auto-approval",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    ]
    candidates = db.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    assert candidates
    assert all(
        candidate.status == ExtractionCandidateStatus.AUTO_APPROVED
        for candidate in candidates
    )
    parsing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.PARSING_STRUCTURE,
        )
    ).one()
    assert parsing_step.metrics
    assert parsing_step.metrics["auto_approved_count"] == len(candidates)
    quality_metrics = parsing_step.metrics["legal_grade_quality"]
    assert quality_metrics["metrics_source"] == "computed_gold_evaluation"
    assert quality_metrics["complete_section_number_coverage"] is True
    assert quality_metrics["complete_source_coordinate_coverage"] is True
    assert quality_metrics["character_accuracy"] == 1
    assert quality_metrics["meaning_changing_token_errors"] == 0
    db.refresh(run)
    assert run.pipeline_config
    policy = run.pipeline_config["auto_approval_policy"]
    assert policy["metrics_source"] == "computed_gold_evaluation"
    assert policy["passed_legal_grade_gate"] is True
    validation_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.VALIDATING_DOCUMENT,
        )
    ).one()
    assert validation_step.metrics
    assert validation_step.metrics["source_verification_required"] is True
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW


def test_parse_stage_rejects_metrics_only_auto_approval_policy(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    instrument_slug = _instrument_slug(db, source)
    run.pipeline_config = {
        "instrument_parser": "constitution",
        "auto_approval_policy": {
            "enabled": True,
            "gold_dataset_version": "ng-constitution-gold-v1",
            "complete_section_number_coverage": True,
            "character_accuracy": 1,
            "meaning_changing_token_errors": 0,
            "gold_provisions": [
                {
                    "canonical_path": f"{instrument_slug}.chapter4.part1.section37",
                    "section_number": "37",
                    "text": (
                        "Right to private and family life\n"
                        "(1) The privacy of citizens is hereby guaranteed and protected."
                    ),
                }
            ],
        },
    }
    db.add(run)
    db.commit()
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize-metrics-only-auto-approval",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=3)

    assert [result.stage for result in results] == [
        IngestionStage.NORMALIZING,
        IngestionStage.PARSING_STRUCTURE,
        IngestionStage.VALIDATING_DOCUMENT,
    ]
    candidates = db.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    assert candidates
    assert all(
        candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
        for candidate in candidates
    )
    parsing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.PARSING_STRUCTURE,
        )
    ).one()
    assert parsing_step.metrics
    assert parsing_step.metrics["auto_approved_count"] == 0
    assert parsing_step.metrics["legal_grade_quality"] is None


def test_parse_stage_creates_blocking_issue_for_missing_source_spans(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text="CHAPTER IV - Fundamental Rights\n37. Broken text (missing close",
        spans=[],
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )

    run_until_idle(db, worker_id="worker-test", max_tasks=5)

    section = db.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == run.id,
            ExtractionCandidate.raw_text != None,  # noqa: E711
        )
    ).one()
    assert section.blocking_issue_count == 2
    issues = db.exec(
        select(ReviewIssue)
        .where(ReviewIssue.candidate_id == section.id)
        .order_by(ReviewIssue.issue_type)
    ).all()
    assert [issue.issue_type for issue in issues] == [
        "low_parser_confidence",
        "missing_source_spans",
        "unbalanced_punctuation",
    ]
    assert [issue.blocking for issue in issues] == [False, True, True]


def test_parse_stage_blocks_source_spans_that_do_not_cover_candidate_text(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "37. Right to private and family life\n"
            "The privacy of citizens is hereby guaranteed."
        ),
        spans=[
            {
                "text": "Official Gazette cover line",
                "bbox": {"x0": 36.0, "y0": 450.0, "x1": 240.0, "y1": 462.0},
                "reading_order": 1,
            }
        ],
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )

    run_until_idle(db, worker_id="worker-test", max_tasks=5)

    section = db.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == run.id,
            ExtractionCandidate.kind == ProvisionKind.SECTION,
        )
    ).one()
    issue = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == section.id,
            ReviewIssue.issue_type == "source_span_coverage",
        )
    ).one()
    assert issue.blocking is True
    assert issue.evidence
    assert issue.evidence["coverage"] == 0
    assert issue.evidence["precision"] == 0
