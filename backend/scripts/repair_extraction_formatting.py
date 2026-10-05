"""Preview/apply source-verified formatting revisions to a waiting review run.

Run from backend with `python -m scripts.repair_extraction_formatting --help`.
The default is a dry run. Never approves candidates or publishes a corpus.
"""

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.db import engine
from app.ingestion.extraction import NATIVE_PDF_EXTRACTOR_VERSION, NativePdfExtractor
from app.ingestion.normalization import legacy_hyphen_loss_matches, normalize_page_text
from app.ingestion.service import decide_review_candidate, update_review_candidate
from app.ingestion.text_alignment import (
    aligned_source_spans,
    compact_text,
    unique_text_range,
)
from app.ingestion.worker import (
    _ancestor_headings,
    _upsert_candidate,
    _validate_candidate_for_review,
)
from app.ingestion.workflow import append_run_event
from app.legal.enums import (
    ExtractionCandidateStatus,
    IngestionRunStatus,
    PageInclusionStatus,
    ProvisionKind,
    ReviewDecisionType,
)
from app.legal.models import (
    ExtractionCandidate,
    IngestionRun,
    SourceDocument,
    SourcePage,
)
from app.legal.parser import SourcePage as ParserSourcePage
from app.legal.parser import _heading_from_text, parse_constitution_pages
from app.legal.schemas import ReviewDecisionCreate, ReviewItemUpdate
from app.models import User


def repair_run(
    session: Session,
    *,
    run_id: uuid.UUID,
    source_file: Path,
    reviewer: User,
    report_path: Path,
    apply: bool = False,
    separate_appendices: bool = False,
    repair_boundaries: bool = False,
) -> dict[str, Any]:
    run = session.get(IngestionRun, run_id)
    if not run or run.status != IngestionRunStatus.WAITING_FOR_REVIEW:
        raise ValueError("Repairs require a run waiting for review")
    source = session.get(SourceDocument, run.source_document_id)
    if not source:
        raise ValueError("Run has no canonical source document")
    content = source_file.read_bytes()
    if hashlib.sha256(content).hexdigest() != source.sha256:
        raise ValueError("Source file does not match the immutable source SHA-256")
    pages = session.exec(select(SourcePage).where(SourcePage.run_id == run_id)).all()
    included = {
        p.page_number
        for p in pages
        if p.inclusion_status == PageInclusionStatus.INCLUDED
    }
    extracted = NativePdfExtractor().extract(content, included_pages=included)
    by_page = {p.page_number: p for p in extracted}
    # Instrument slug comes from stable candidate paths, not the filename.
    from app.legal.models import LegalInstrument

    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    if not instrument:
        raise ValueError("Source has no legal instrument")
    nodes = parse_constitution_pages(
        [
            ParserSourcePage(p.page_number, normalize_page_text(p.text).text)
            for p in extracted
        ],
        instrument.slug,
    )
    boundary = next(
        (
            n.parser_metadata["appended_instrument_boundary"]
            for n in nodes
            if "appended_instrument_boundary" in n.parser_metadata
        ),
        None,
    )
    new_paths = {n.canonical_path for n in nodes}
    node_by_path = {n.canonical_path: n for n in nodes}
    candidates = session.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.run_id == run_id)
        .order_by(ExtractionCandidate.sort_key)
    ).all()
    report: dict[str, Any] = {
        "run_id": str(run_id),
        "source_sha256": source.sha256,
        "extractor_version": NATIVE_PDF_EXTRACTOR_VERSION,
        "applied": False,
        "revisions": [],
        "skipped": [],
        "separate_instrument_candidates": [],
        "restored_provisions": [],
        "appendix_boundary": boundary,
        "appendix_status": "Retained in original source; separate instrument ingestion requires a supported parser and reviewed instrument metadata.",
    }
    by_path = {c.canonical_path: c for c in candidates}
    for candidate in candidates:
        if (
            candidate.status != ExtractionCandidateStatus.NEEDS_REVIEW
            or candidate.revision_number != 1
        ):
            report["skipped"].append(
                {"id": str(candidate.id), "reason": "Existing review work preserved"}
            )
            continue
        if (
            boundary
            and candidate.canonical_path not in new_paths
            and (candidate.source_page_start or 0) >= boundary["page_number"]
        ):
            report["separate_instrument_candidates"].append(
                {
                    "id": str(candidate.id),
                    "canonical_path": candidate.canonical_path,
                    "pages": [candidate.source_page_start, candidate.source_page_end],
                    "expected_version": candidate.lock_version,
                }
            )
            continue
        if not candidate.raw_text:
            continue
        selected = [
            by_page[n]
            for n in range(
                candidate.source_page_start or 1,
                (candidate.source_page_end or candidate.source_page_start or 1) + 1,
            )
            if n in by_page
        ]
        page_text = "\n".join(p.text for p in selected)
        target = candidate.raw_text
        repair_kind = "whitespace"
        node = node_by_path.get(candidate.canonical_path)
        if node and node.text and legacy_hyphen_loss_matches(target, node.text):
            if compact_text(target)[0] != compact_text(node.text)[0]:
                target = node.text
                repair_kind = "restore_source_hyphens"
        if (
            repair_boundaries
            and node
            and node.text
            and node.kind == ProvisionKind.SCHEDULE_ITEM
            and node.number
            and node.number.isdigit()
        ):
            successor_path = f"{node.parent_path}.item{int(node.number) + 1}"
            successor = node_by_path.get(successor_path)
            if (
                successor
                and successor_path not in by_path
                and (node.page_end or 0) < (candidate.source_page_end or 0)
            ):
                target = node.text
                repair_kind = "restore_provision_boundary"
        match = unique_text_range(target, page_text)
        spans = [
            {
                "text": s.text,
                "page_number": p.page_number,
                "bbox": s.bbox,
                "reading_order": s.reading_order,
                "method": p.method,
                "provider_version": p.provider_version,
                "confidence": p.confidence,
            }
            for p in selected
            for s in p.spans
        ]
        aligned = aligned_source_spans(target, spans)
        ancestor = node_by_path.get(node.parent_path or "") if node else None
        while (match is None or aligned is None) and ancestor:
            if ancestor.text:
                match = unique_text_range(target, page_text, context=ancestor.text)
                aligned = aligned_source_spans(target, spans, context=ancestor.text)
            ancestor = node_by_path.get(ancestor.parent_path or "")
        if match is None or aligned is None:
            report["skipped"].append(
                {
                    "id": str(candidate.id),
                    "canonical_path": candidate.canonical_path,
                    "reason": "No unique exact source-character match; manual source review required",
                }
            )
            continue
        revised = normalize_page_text(page_text[match[0] : match[1]]).text
        if compact_text(revised)[0] != compact_text(target)[0]:
            raise ValueError("Formatting repair unexpectedly changed source characters")
        heading = (
            _heading_from_text(revised)
            if candidate.heading == _heading_from_text(candidate.raw_text)
            else None
        )
        update = ReviewItemUpdate(
            idempotency_key=f"layout-v2-formatting-{candidate.id}",
            expected_version=candidate.lock_version,
            revised_text=revised,
            heading=heading,
            source_spans=aligned,
            source_page_start=min(int(s["page_number"]) for s in aligned),
            source_page_end=max(int(s["page_number"]) for s in aligned),
            reason=f"Source-verified PDF repair: {repair_kind}. Text matches the immutable source character-for-character after whitespace cleanup. Source-coordinate spans narrowed with original text and offsets retained. Missing hyphens are restored only where the legacy line-wrap rule demonstrably removed them; swallowed text is restored in separate provision candidates. No legal wording inferred.",
        )
        report["revisions"].append(
            {
                "id": str(candidate.id),
                "canonical_path": candidate.canonical_path,
                "update": update.model_dump(mode="json"),
                "previous_text": candidate.raw_text,
                "repair_kind": repair_kind,
            }
        )
    restored_proposals = []
    for node in nodes:
        if (
            node.kind != ProvisionKind.SCHEDULE_ITEM
            or node.canonical_path in by_path
            or node.parent_path not in by_path
        ):
            continue
        if ".oath-" not in node.canonical_path and not repair_boundaries:
            continue
        selected = [
            by_page[n]
            for n in range(node.page_start or 1, (node.page_end or 1) + 1)
            if n in by_page
        ]
        spans = [
            {
                "text": s.text,
                "page_number": p.page_number,
                "bbox": s.bbox,
                "reading_order": s.reading_order,
                "method": p.method,
                "provider_version": p.provider_version,
                "confidence": p.confidence,
            }
            for p in selected
            for s in p.spans
        ]
        aligned = aligned_source_spans(node.text or "", spans)
        if not aligned:
            raise ValueError(
                f"Restored provision has no exact source evidence: {node.canonical_path}"
            )
        report["restored_provisions"].append(
            {
                "canonical_path": node.canonical_path,
                "text": node.text,
                "pages": [node.page_start, node.page_end],
            }
        )
        restored_proposals.append((node, aligned))
    report["summary"] = {
        name: len(report[name])
        for name in (
            "revisions",
            "skipped",
            "separate_instrument_candidates",
            "restored_provisions",
        )
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if apply:
        if separate_appendices:
            for proposal in report["separate_instrument_candidates"]:
                decide_review_candidate(
                    session,
                    uuid.UUID(proposal["id"]),
                    ReviewDecisionCreate(
                        idempotency_key=f"source-partition-v1-{proposal['id']}",
                        expected_version=proposal["expected_version"],
                        decision=ReviewDecisionType.REJECT,
                        reason="Appended rules/orders belong to separate instruments, not Constitution Schedule 7. Original PDF, extraction and candidate retained for separate ingestion; no source content deleted.",
                    ),
                    reviewer,
                )
        for proposal in report["revisions"]:
            update_review_candidate(
                session,
                uuid.UUID(proposal["id"]),
                ReviewItemUpdate.model_validate(proposal["update"]),
                reviewer,
            )
        for node, aligned in restored_proposals:
            candidate = _upsert_candidate(
                session,
                run=run,
                source=source,
                node=node,
                parent_candidate=by_path.get(node.parent_path or ""),
                ancestor_headings=_ancestor_headings(node.parent_path, node_by_path),
                source_spans=aligned,
            )
            _validate_candidate_for_review(session, candidate)
            session.commit()
    report["summary"] = {
        name: len(report[name])
        for name in (
            "revisions",
            "skipped",
            "separate_instrument_candidates",
            "restored_provisions",
        )
    }
    report["applied"] = apply
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if apply:
        append_run_event(
            session,
            run,
            event_type="source_formatting_repaired",
            message="Source-verified formatting revisions saved; appended instruments retained separately and omitted schedule provisions restored for review.",
            payload={
                "source_sha256": source.sha256,
                "extractor_version": NATIVE_PDF_EXTRACTOR_VERSION,
                **report["summary"],
            },
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=uuid.UUID, required=True)
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--reviewer-email", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--repair-boundaries",
        action="store_true",
        help="Restore swallowed schedule items from explicit source numbering",
    )
    parser.add_argument(
        "--separate-appendices",
        action="store_true",
        help="Reject misattributed appendix candidates while retaining their source and audit records",
    )
    args = parser.parse_args()
    with Session(engine) as session:
        reviewer = session.exec(
            select(User).where(
                User.email == args.reviewer_email,
                User.is_superuser == True,  # noqa: E712
            )
        ).one_or_none()  # noqa: E712
        if not reviewer:
            raise ValueError(
                "A known superuser reviewer is required for this maintenance command"
            )
        report = repair_run(
            session,
            run_id=args.run_id,
            source_file=args.source_file,
            reviewer=reviewer,
            report_path=args.report,
            apply=args.apply,
            separate_appendices=args.separate_appendices,
            repair_boundaries=args.repair_boundaries,
        )
        print(json.dumps(report["summary"]))  # noqa: T201


if __name__ == "__main__":
    main()
