import uuid

from sqlmodel import Session, select

from app.core.errors import DomainError, ErrorCode
from app.legal.enums import (
    IngestionStage,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    ExtractionCandidate,
    IngestionRun,
    IngestionStep,
    SourceDocument,
)


def get_run(session: Session, run_id: uuid.UUID) -> IngestionRun:
    run = session.get(IngestionRun, run_id)
    if not run:
        raise DomainError(ErrorCode.NOT_FOUND, "Ingestion run not found")
    return run


def release_id_for_run(session: Session, run: IngestionRun) -> uuid.UUID:
    composed_id = (run.pipeline_config or {}).get("composition_release_id")
    if composed_id:
        release = get_release(session, uuid.UUID(str(composed_id)))
        if ((release.validation_report or {}).get("composition") or {}).get(
            "run_id"
        ) != str(run.id):
            raise DomainError(
                ErrorCode.CONFLICT, "Composite run identity differs from its release"
            )
        return release.id
    original = session.exec(
        select(CorpusRelease).where(CorpusRelease.version == f"draft-{run.id.hex[:12]}")
    ).first()
    if original:
        return original.id
    release_ids = session.exec(
        select(CorpusReleaseEntry.release_id)
        .where(CorpusReleaseEntry.ingestion_run_id == run.id)
        .distinct()
    ).all()
    originals = [
        item
        for release_id in release_ids
        if (item := session.get(CorpusRelease, release_id))
        and not (item.validation_report or {}).get("composition")
    ]
    if len(originals) != 1:
        raise DomainError(
            ErrorCode.CONFLICT,
            "Ingestion run does not identify a single original corpus release",
        )
    return originals[0].id


def get_source_document(
    session: Session, source_document_id: uuid.UUID
) -> SourceDocument:
    source = session.get(SourceDocument, source_document_id)
    if not source:
        raise DomainError(ErrorCode.NOT_FOUND, "Source document not found")
    return source


def get_run_step(
    session: Session, run_id: uuid.UUID, stage: IngestionStage
) -> IngestionStep:
    step = session.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run_id,
            IngestionStep.stage == stage,
        )
    ).first()
    if not step:
        raise DomainError(ErrorCode.NOT_FOUND, f"{stage.value} step not found")
    return step


def get_candidate(session: Session, candidate_id: uuid.UUID) -> ExtractionCandidate:
    candidate = session.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.id == candidate_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if not candidate:
        raise DomainError(ErrorCode.NOT_FOUND, "Review item not found")
    return candidate


def get_release(session: Session, release_id: uuid.UUID) -> CorpusRelease:
    release = session.get(CorpusRelease, release_id)
    if not release:
        raise DomainError(ErrorCode.NOT_FOUND, "Corpus release not found")
    return release


def check_expected_version(actual_version: int, expected_version: int) -> None:
    if actual_version != expected_version:
        raise DomainError(
            ErrorCode.CONFLICT, "The record was modified by another operation"
        )
