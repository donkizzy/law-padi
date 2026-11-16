"""Stage approved offline OCR artifacts in the existing human review workflow.

This imports provisional page boundaries and unverified text. It never marks a
source verified, approves a candidate, embeds text, or publishes a release.
Only tasks belonging to the imported run are executed.
"""

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.ingestion.service import get_blob_store
from app.ingestion.worker import _ensure_artifact, run_leased_task
from app.ingestion.workflow import append_run_event, create_run_steps, enqueue_task
from app.legal.act_parser import ACT_PARSER_VERSION
from app.legal.enums import (
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    InstrumentType,
    PageInclusionStatus,
    PageRole,
    ReviewIssueSeverity,
)
from app.legal.models import (
    ExtractionCandidate,
    IngestionRun,
    IngestionTask,
    LegalInstrument,
    ReviewIssue,
    SourceDocument,
    SourcePage,
)

REVIEW_IMPORTER_VERSION = "statute-review-import-v2-explicit-roles"


def page_role_proposals(
    pages: list[dict[str, Any]],
) -> dict[int, tuple[PageRole, str]] | None:
    """Validate explicit provisional roles before any import writes.

    Older artifacts may omit roles entirely. Once an artifact supplies a role
    or reason, every page must supply both; never silently mix explicit evidence
    with the legacy enactment-caption heuristic. These are proposals, not page
    inclusion decisions or acceptance of legal wording.
    """
    if not any("role" in page or "role_reason" in page for page in pages):
        return None
    proposals: dict[int, tuple[PageRole, str]] = {}
    for page in pages:
        number = page["page_number"]
        if number in proposals:
            raise ValueError("Each explicit page role must occur exactly once")
        raw_role = page.get("role")
        if not isinstance(raw_role, str):
            raise ValueError(f"Page {number} requires a valid explicit PageRole")
        try:
            role = PageRole(raw_role)
        except ValueError:
            raise ValueError(f"Page {number} requires a valid explicit PageRole")
        reason = page.get("role_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"Page {number} requires an explicit role reason")
        proposals[number] = (role, reason)
    return proposals


def stage_source(
    session: Session,
    source: SourceDocument,
    instrument: LegalInstrument,
    payload: dict[str, Any],
    artifact_sha256: str,
) -> IngestionRun:
    if "act" not in settings.INGESTION_ALLOWED_INSTRUMENT_TYPES:
        raise ValueError(
            "Enable act in INGESTION_ALLOWED_INSTRUMENT_TYPES for this review operation"
        )
    if (
        instrument.instrument_type != InstrumentType.ACT
        or payload["source_sha256"] != source.sha256
    ):
        raise ValueError("OCR source identity differs from the registered Act")
    pages = payload["pages"]
    if sorted(page["page_number"] for page in pages) != list(
        range(1, (source.page_count or 0) + 1)
    ):
        raise ValueError("Every source page must be retained exactly once for review")
    explicit_roles = page_role_proposals(pages)
    runs = session.exec(
        select(IngestionRun).where(IngestionRun.source_document_id == source.id)
    ).all()
    run = next(
        (
            item
            for item in runs
            if (item.pipeline_config or {}).get("review_import_sha256")
            == artifact_sha256
            and (item.pipeline_config or {}).get("review_import_parser_version")
            == ACT_PARSER_VERSION
        ),
        None,
    )
    if run and (run.pipeline_config or {}).get("review_import_complete"):
        return run
    if run is None:
        run = IngestionRun(
            source_document_id=source.id,
            status=IngestionRunStatus.QUEUED,
            current_stage=IngestionStage.NORMALIZING,
            expected_page_count=source.page_count,
            pipeline_config={
                "instrument_parser": "act",
                "corpus_legal_status": "historical",
                "review_import_sha256": artifact_sha256,
                "review_import_parser_version": ACT_PARSER_VERSION,
                "review_importer_version": REVIEW_IMPORTER_VERSION,
                "review_import_page_role_strategy": (
                    "explicit_provisional_roles"
                    if explicit_roles is not None
                    else "legacy_enactment_heuristic"
                ),
                "review_import_complete": False,
                "provisional_page_boundaries": True,
                "auto_approval_policy": {"enabled": False},
                "auto_start_embedding": False,
            },
        )
        session.add(run)
        session.commit()
        session.refresh(run)
    steps = create_run_steps(session, run)
    for step in steps:
        if step.stage == IngestionStage.NORMALIZING:
            break
        step.status = IngestionStepStatus.SKIPPED
        step.metrics = {
            "reason": "Offline coordinate OCR imported for human review; page boundaries are provisional"
        }
        session.add(step)
    store = get_blob_store()
    body_started = False
    for page in sorted(pages, key=lambda item: item["page_number"]):
        if "ENACTED by" in page["text"]:
            body_started = True
        row = session.exec(
            select(SourcePage).where(
                SourcePage.run_id == run.id,
                SourcePage.page_number == page["page_number"],
            )
        ).first()
        if row is None:
            row = SourcePage(
                run_id=run.id,
                source_document_id=source.id,
                page_number=page["page_number"],
            )
        row.role = (
            explicit_roles[page["page_number"]][0]
            if explicit_roles is not None
            else PageRole.LEGAL_BODY
            if body_started
            else PageRole.TABLE_OF_CONTENTS
            if page["page_number"] > 1
            else PageRole.FRONT_MATTER
        )
        row.inclusion_status = PageInclusionStatus.SUGGESTED_INCLUDE
        row.inclusion_reason = (
            "Provisional OCR import; reviewer must confirm page boundaries"
        )
        row.quality_signals = {
            "preview_text": page["text"][:4000],
            "preview_provisional": True,
            "coordinate_space": page.get("coordinate_space"),
            "ocr_confidence": page["confidence"],
            **(
                {
                    "role_provisional": True,
                    "role_source": "explicit_import_proposal",
                    "role_reason": explicit_roles[page["page_number"]][1],
                }
                if explicit_roles is not None
                else {}
            ),
        }
        session.add(row)
        session.flush()
        blob = store.put_artifact(
            run_id=str(run.id),
            artifact_type=IngestionArtifactType.RAW_EXTRACTION.value,
            filename=f"page-{page['page_number']:04d}-review-ocr.json",
            content=json.dumps(page, sort_keys=True).encode(),
            content_type="application/json",
            metadata={"source_sha256": source.sha256, "review_status": "needs_review"},
        )
        _ensure_artifact(
            session,
            run_id=run.id,
            source_page_id=row.id,
            artifact_type=IngestionArtifactType.RAW_EXTRACTION,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            metadata={
                "page_number": page["page_number"],
                "provider_version": payload["version"],
                "review_importer_version": REVIEW_IMPORTER_VERSION,
                "review_status": "needs_review",
            },
        )
    run.pipeline_config = {**run.pipeline_config, "review_import_complete": True}
    session.add(run)
    session.commit()
    normalize = next(step for step in steps if step.stage == IngestionStage.NORMALIZING)
    enqueue_task(
        session,
        run=run,
        step=normalize,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalizing",
        payload={"source_document_id": str(source.id)},
    )
    append_run_event(
        session,
        run,
        event_type="statute_review_imported",
        message="Coordinate OCR imported with source verification and extraction approval pending",
        payload={
            "artifact_sha256": artifact_sha256,
            "source_sha256": source.sha256,
            "provisional_page_boundaries": True,
        },
    )
    return run


def run_to_review(session: Session, run: IngestionRun) -> None:
    for _index in range(3):
        task = session.exec(
            select(IngestionTask)
            .where(
                IngestionTask.run_id == run.id,
                IngestionTask.status == IngestionTaskStatus.PENDING,
                col(IngestionTask.task_type).in_(
                    ["normalizing", "parsing_structure", "validating_document"]
                ),
            )
            .with_for_update()
        ).first()
        if task is None:
            break
        task.status = IngestionTaskStatus.LEASED
        task.lease_owner = "statute-review-import"
        task.leased_until = datetime.now(UTC) + timedelta(seconds=900)
        task.attempt_count += 1
        session.add(task)
        session.commit()
        outcome = run_leased_task(session, task, worker_id="statute-review-import")
        if outcome.task_status != IngestionTaskStatus.SUCCEEDED:
            raise RuntimeError(f"Review task failed: {outcome}")
    candidates = session.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.run_id == run.id)
        .order_by(ExtractionCandidate.sort_key)
    ).all()
    if candidates:
        first = candidates[0]
        existing = session.exec(
            select(ReviewIssue).where(
                ReviewIssue.candidate_id == first.id,
                ReviewIssue.issue_type == "provisional_page_boundaries",
            )
        ).first()
        if existing is None:
            session.add(
                ReviewIssue(
                    candidate_id=first.id,
                    issue_type="provisional_page_boundaries",
                    severity=ReviewIssueSeverity.BLOCKING,
                    blocking=True,
                    message="Confirm the imported page boundaries against the original PDF before materialization.",
                    evidence={"run_id": str(run.id), "review_import": True},
                )
            )
            first.blocking_issue_count += 1
            session.add(first)
            session.commit()


def stage_previews(session: Session, run: IngestionRun, folder: Path) -> None:
    previews = {
        int(path.stem.removeprefix("page-")): path
        for path in (folder / "review-previews").glob("page-*.png")
    }
    store = get_blob_store()
    for page in session.exec(
        select(SourcePage).where(SourcePage.run_id == run.id)
    ).all():
        if page.thumbnail_key or page.page_number not in previews:
            continue
        blob = store.put_artifact(
            run_id=str(run.id),
            artifact_type=IngestionArtifactType.PAGE_THUMBNAIL.value,
            filename=f"page-{page.page_number:04d}.png",
            content=previews[page.page_number].read_bytes(),
            content_type="image/png",
            metadata={
                "source_document_id": str(run.source_document_id),
                "review_status": "needs_review",
            },
        )
        _ensure_artifact(
            session,
            run_id=run.id,
            source_page_id=page.id,
            artifact_type=IngestionArtifactType.PAGE_THUMBNAIL,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            retention_policy="expire_after_90_days",
            metadata={"page_number": page.page_number},
        )
        page.thumbnail_key = blob.key
        session.add(page)
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {"sources": []}
    with Session(engine) as session:
        for item in json.loads(args.manifest.read_text())["sources"]:
            source = session.get(SourceDocument, uuid.UUID(item["source_document_id"]))
            if source is None or source.sha256 != item["sha256"]:
                raise ValueError(
                    "Registered source does not match the approved manifest"
                )
            instrument = session.get(LegalInstrument, source.legal_instrument_id)
            if instrument is None or instrument.slug != item["instrument_slug"]:
                raise ValueError("Registered instrument identity differs")
            root = args.source_root / instrument.slug
            pdf = root / item["filename"]
            if (
                hashlib.sha256(pdf.read_bytes()).hexdigest() != source.sha256
                or len(PdfReader(pdf).pages) != source.page_count
            ):
                raise ValueError("Original PDF identity or page count differs")
            raw = (root / "ocr-layout-pages-v2.json").read_bytes()
            run = stage_source(
                session,
                source,
                instrument,
                json.loads(raw),
                hashlib.sha256(raw).hexdigest(),
            )
            run_to_review(session, run)
            stage_previews(session, run, root)
            session.refresh(run)
            candidates = session.exec(
                select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
            ).all()
            issues = session.exec(
                select(ReviewIssue).where(
                    col(ReviewIssue.candidate_id).in_(
                        [candidate.id for candidate in candidates]
                    )
                )
            ).all()
            report["sources"].append(
                {
                    "instrument_slug": instrument.slug,
                    "source_document_id": str(source.id),
                    "source_sha256": source.sha256,
                    "verification_status": str(source.verification_status),
                    "run_id": str(run.id),
                    "run_status": str(run.status),
                    "stage": str(run.current_stage),
                    "candidate_count": len(candidates),
                    "section_count": sum(
                        candidate.kind == "section" for candidate in candidates
                    ),
                    "unique_section_count": len(
                        {
                            candidate.number
                            for candidate in candidates
                            if candidate.kind == "section"
                        }
                    ),
                    "source_preview_count": len(
                        session.exec(
                            select(SourcePage).where(
                                SourcePage.run_id == run.id,
                                col(SourcePage.thumbnail_key).is_not(None),
                            )
                        ).all()
                    ),
                    "parser_version": run.pipeline_config.get("parser_version"),
                    "blocking_issue_count": sum(issue.blocking for issue in issues),
                    "issues_by_type": {
                        name: sum(issue.issue_type == name for issue in issues)
                        for name in sorted({issue.issue_type for issue in issues})
                    },
                    "arrangement_findings": [
                        issue.evidence
                        for issue in issues
                        if issue.issue_type == "graph_act_arrangement_reconciliation"
                    ],
                    "materialized_version_count": sum(
                        candidate.materialized_version_id is not None
                        for candidate in candidates
                    ),
                }
            )
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report["sources"][-1]), flush=True)  # noqa: T201


if __name__ == "__main__":
    main()
