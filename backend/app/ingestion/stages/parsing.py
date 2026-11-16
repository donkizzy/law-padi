import uuid

from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.common import enum_value
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.types import StageOutcome
from app.ingestion.stages.candidates import (
    ensure_review_issue,
    maybe_compute_gold_quality_report,
    upsert_candidate,
    validate_candidate_for_review,
    validated_candidate_status,
)
from app.ingestion.stages.page_payloads import normalized_pages_payload
from app.ingestion.stages.source_spans import ancestor_headings, source_spans_for_node
from app.ingestion.stages.sources import get_source_for_run
from app.ingestion.structure_validators import validate_document_graph
from app.legal.enums import (
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    ReviewIssueSeverity,
    VerificationStatus,
)
from app.legal.instrument_parser import (
    parse_instrument_pages,
    parsed_provisions_from_graph,
)
from app.legal.models import (
    ExtractionCandidate,
    IngestionRun,
    IngestionTask,
    LegalInstrument,
    ReviewIssue,
    SourcePage,
)
from app.legal.parser import (
    SourcePage as ParserSourcePage,
)


def handle_parsing_structure(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = get_source_for_run(session, run, task)
    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    if not instrument:
        raise IngestionWorkerError(
            "Source document is not linked to a legal instrument"
        )
    normalized_payload = normalized_pages_payload(session, run)
    page_payloads = list(normalized_payload["pages"])
    parser_pages = [
        ParserSourcePage(
            page_number=int(page["page_number"]),
            text=str(page["text"]),
        )
        for page in page_payloads
    ]
    instrument_type = getattr(instrument, "instrument_type", "constitution")
    instrument_type_value = str(getattr(instrument_type, "value", instrument_type))
    if instrument_type_value not in settings.INGESTION_ALLOWED_INSTRUMENT_TYPES:
        raise IngestionWorkerError(
            f"Ingestion is disabled for instrument type: {instrument_type_value}"
        )
    graph = parse_instrument_pages(
        instrument_type=instrument_type_value,
        instrument_slug=instrument.slug,
        pages=parser_pages,
    )
    run.pipeline_config = {
        **(run.pipeline_config or {}),
        "parser_version": graph.parser_version,
        "instrument_parser": instrument_type_value,
    }
    parsed_nodes = parsed_provisions_from_graph(graph)
    page_roles = [
        {"page_number": page.page_number, "role": enum_value(page.role)}
        for page in session.exec(
            select(SourcePage).where(SourcePage.run_id == run.id)
        ).all()
    ]
    graph_issues = validate_document_graph(graph, page_roles=page_roles)
    node_by_path = {node.canonical_path: node for node in parsed_nodes}
    candidates_by_path: dict[str, ExtractionCandidate] = {}
    issues_by_candidate_id: dict[uuid.UUID, list[ReviewIssue]] = {}
    issue_count = 0
    blocking_issue_count = 0

    for node in parsed_nodes:
        candidate = upsert_candidate(
            session,
            run=run,
            source=source,
            node=node,
            parent_candidate=candidates_by_path.get(node.parent_path or ""),
            ancestor_headings=ancestor_headings(node.parent_path, node_by_path),
            source_spans=source_spans_for_node(
                node, page_payloads, nodes_by_path=node_by_path
            ),
        )
        candidates_by_path[node.canonical_path] = candidate
        missing_parent_issue = None
        if node.parent_path and not candidate.parent_candidate_id:
            missing_parent_issue = ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="missing_parent",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate parent path was not materialized before this node.",
                evidence={"parent_path": node.parent_path},
            )
        issues = validate_candidate_for_review(session, candidate)
        if missing_parent_issue:
            issues.append(missing_parent_issue)
        candidate.blocking_issue_count = sum(1 for issue in issues if issue.blocking)
        session.add(candidate)
        issues_by_candidate_id[candidate.id] = issues
        issue_count += len(issues)
        blocking_issue_count += sum(1 for issue in issues if issue.blocking)
    for graph_issue in graph_issues:
        # Per-candidate validators already cover parents, punctuation, and
        # source spans; only emit document-level findings here to avoid
        # double-reporting the same defect.
        if graph_issue.issue_type in {
            "missing_parent",
            "unbalanced_punctuation",
            "source_span_coverage",
            "duplicate_canonical_path",
        }:
            continue
        target_candidate: ExtractionCandidate | None = (
            candidates_by_path.get(graph_issue.canonical_path or "")
            if graph_issue.canonical_path
            else None
        )
        if target_candidate is None and candidates_by_path:
            target_candidate = next(iter(candidates_by_path.values()))
        if target_candidate is None:
            continue
        issue = ensure_review_issue(
            session,
            candidate=target_candidate,
            issue_type=f"graph_{graph_issue.issue_type}",
            severity=ReviewIssueSeverity.BLOCKING
            if graph_issue.blocking
            else ReviewIssueSeverity.HIGH,
            blocking=graph_issue.blocking,
            message=graph_issue.message,
            evidence=graph_issue.evidence,
        )
        issues_by_candidate_id.setdefault(target_candidate.id, []).append(issue)
        target_candidate.blocking_issue_count = sum(
            1 for item in issues_by_candidate_id[target_candidate.id] if item.blocking
        )
        session.add(target_candidate)
        issue_count += 1
        blocking_issue_count += 1 if issue.blocking else 0
    quality_report = maybe_compute_gold_quality_report(
        session, run, list(candidates_by_path.values())
    )
    for candidate in candidates_by_path.values():
        candidate.status = validated_candidate_status(
            run, candidate, issues_by_candidate_id.get(candidate.id, [])
        )
        session.add(candidate)
    session.commit()
    auto_approved_count = sum(
        1
        for candidate in candidates_by_path.values()
        if candidate.status == ExtractionCandidateStatus.AUTO_APPROVED
    )
    return StageOutcome(
        metrics={
            "candidate_count": len(parsed_nodes),
            "issue_count": issue_count,
            "blocking_issue_count": blocking_issue_count,
            "auto_approved_count": auto_approved_count,
            "parser_version": graph.parser_version,
            "legal_grade_quality": (
                quality_report.to_policy_metrics() if quality_report else None
            ),
        },
        next_stage=IngestionStage.VALIDATING_DOCUMENT,
        next_task_payload={"source_document_id": str(source.id)},
    )


def handle_validating_document(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = get_source_for_run(session, run, task)
    candidates = session.exec(
        select(ExtractionCandidate).where(ExtractionCandidate.run_id == run.id)
    ).all()
    if not candidates:
        raise IngestionWorkerError("Run does not have parsed extraction candidates")
    blocking_count = sum(candidate.blocking_issue_count for candidate in candidates)
    review_count = sum(
        1
        for candidate in candidates
        if candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    )
    text_candidate_count = sum(1 for candidate in candidates if candidate.raw_text)
    metrics = {
        "candidate_count": len(candidates),
        "text_candidate_count": text_candidate_count,
        "review_count": review_count,
        "blocking_issue_count": blocking_count,
        "source_verification_required": (
            source.verification_status != VerificationStatus.VERIFIED
        ),
    }
    if blocking_count or review_count or metrics["source_verification_required"]:
        return StageOutcome(
            metrics=metrics,
            next_stage=IngestionStage.REVIEW,
            next_status=IngestionRunStatus.WAITING_FOR_REVIEW,
            block_next_stage=True,
        )
    return StageOutcome(
        metrics=metrics,
        next_stage=IngestionStage.MATERIALIZING,
        next_task_payload={"candidate_count": len(candidates)},
    )
