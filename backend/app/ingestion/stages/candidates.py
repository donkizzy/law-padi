from typing import Any

from sqlmodel import Session, col, select

from app.ingestion.common import get_datetime_utc
from app.ingestion.evaluation import (
    load_gold_provisions_for_dataset,
)
from app.ingestion.quality import (
    LEGAL_GRADE_MIN_CHARACTER_ACCURACY,
    ExtractedProvision,
    LegalGradeQualityReport,
    evaluate_legal_grade_quality,
)
from app.ingestion.stages.source_spans import (
    extractor_confidence,
    extractor_version,
    source_span_text_metrics,
)
from app.ingestion.validation import has_unbalanced_punctuation
from app.legal.enums import (
    ExtractionCandidateStatus,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.models import (
    CandidateRevision,
    ExtractionCandidate,
    IngestionRun,
    ReviewIssue,
    SourceDocument,
)
from app.legal.parser import (
    PARSER_VERSION,
    legal_text_sha256,
    normalize_legal_text,
)

AUTO_APPROVAL_MIN_CONFIDENCE = 0.9


def candidate_text_for_materialization(
    session: Session, candidate: ExtractionCandidate
) -> str | None:
    revision = session.exec(
        select(CandidateRevision)
        .where(CandidateRevision.candidate_id == candidate.id)
        .order_by(col(CandidateRevision.revision_number).desc())
    ).first()
    text = revision.revised_text if revision else candidate.raw_text
    if not text or not text.strip():
        return None
    return text.strip()


def run_parser_version(run: IngestionRun) -> str:
    return str((run.pipeline_config or {}).get("parser_version") or PARSER_VERSION)


def upsert_candidate(
    session: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    node: Any,
    parent_candidate: ExtractionCandidate | None,
    ancestor_headings: list[str],
    source_spans: list[dict[str, Any]],
) -> ExtractionCandidate:
    existing = session.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == run.id,
            ExtractionCandidate.canonical_path == node.canonical_path,
            ExtractionCandidate.revision_number == 1,
        )
    ).first()
    candidate = existing or ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=node.kind,
        canonical_path=node.canonical_path,
        sort_key=node.sort_key,
    )
    candidate.parent_candidate_id = parent_candidate.id if parent_candidate else None
    candidate.kind = node.kind
    candidate.number = node.number
    candidate.heading = node.heading
    candidate.sort_key = node.sort_key
    candidate.raw_text = node.text
    candidate.normalized_text = normalize_legal_text(node.text) if node.text else None
    candidate.text_sha256 = legal_text_sha256(node.text) if node.text else None
    candidate.source_page_start = node.page_start
    candidate.source_page_end = node.page_end
    candidate.source_spans = source_spans
    candidate.ancestor_headings = ancestor_headings
    candidate.parser_version = str(
        (node.parser_metadata or {}).get("parser_version") or run_parser_version(run)
    )
    candidate.extractor_version = extractor_version(source_spans)
    candidate.parser_confidence = node.parser_confidence
    candidate.extractor_confidence = extractor_confidence(source_spans)
    candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
    candidate.lock_version += 1
    candidate.updated_at = get_datetime_utc()
    session.add(candidate)
    session.flush()
    return candidate


def validate_candidate_for_review(
    session: Session, candidate: ExtractionCandidate
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if candidate.raw_text and not candidate.source_spans:
        issues.append(
            ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="missing_source_spans",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate text does not have source-coordinate spans.",
                evidence={"canonical_path": candidate.canonical_path},
            )
        )
    elif candidate.raw_text and candidate.source_spans:
        coverage, precision = source_span_text_metrics(
            candidate.raw_text, candidate.source_spans
        )
        if coverage < 0.8 or precision < 0.5:
            issues.append(
                ensure_review_issue(
                    session,
                    candidate=candidate,
                    issue_type="source_span_coverage",
                    severity=ReviewIssueSeverity.BLOCKING,
                    blocking=True,
                    message="Candidate text is not sufficiently covered by source-coordinate spans.",
                    evidence={
                        "canonical_path": candidate.canonical_path,
                        "coverage": coverage,
                        "precision": precision,
                    },
                )
            )
    if (
        candidate.raw_text
        and candidate.parser_confidence is not None
        and candidate.parser_confidence < 0.8
    ):
        issues.append(
            ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="low_parser_confidence",
                severity=ReviewIssueSeverity.HIGH,
                blocking=False,
                message="Parser confidence fell below the auto-approval threshold.",
                evidence={"parser_confidence": candidate.parser_confidence},
            )
        )
    if candidate.raw_text and has_unbalanced_punctuation(candidate.raw_text):
        issues.append(
            ensure_review_issue(
                session,
                candidate=candidate,
                issue_type="unbalanced_punctuation",
                severity=ReviewIssueSeverity.BLOCKING,
                blocking=True,
                message="Candidate text has unbalanced punctuation.",
                evidence={"canonical_path": candidate.canonical_path},
            )
        )
    candidate.blocking_issue_count = sum(1 for issue in issues if issue.blocking)
    session.add(candidate)
    return issues


def maybe_compute_gold_quality_report(
    session: Session,
    run: IngestionRun,
    candidates: list[ExtractionCandidate],
) -> LegalGradeQualityReport | None:
    policy = (run.pipeline_config or {}).get("auto_approval_policy")
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return None
    dataset_version = policy.get("gold_dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        return None
    gold_provisions = load_gold_provisions_for_dataset(session, dataset_version)
    if not gold_provisions:
        return None

    report = evaluate_legal_grade_quality(
        gold_dataset_version=dataset_version,
        gold_provisions=gold_provisions,
        extracted_provisions=[
            ExtractedProvision(
                canonical_path=candidate.canonical_path,
                text=candidate.raw_text,
                kind=candidate.kind,
                number=candidate.number,
                source_page_start=candidate.source_page_start,
                source_page_end=candidate.source_page_end,
                source_spans=candidate.source_spans,
            )
            for candidate in candidates
        ],
    )
    run.pipeline_config = {
        **(run.pipeline_config or {}),
        "auto_approval_policy": {
            **policy,
            **report.to_policy_metrics(),
        },
    }
    session.add(run)
    return report


def validated_candidate_status(
    run: IngestionRun,
    candidate: ExtractionCandidate,
    issues: list[ReviewIssue],
) -> ExtractionCandidateStatus:
    if issues or not auto_approval_policy_passes(run):
        return ExtractionCandidateStatus.NEEDS_REVIEW
    if candidate.raw_text and not candidate_confidence_passes(candidate):
        return ExtractionCandidateStatus.NEEDS_REVIEW
    return ExtractionCandidateStatus.AUTO_APPROVED


def auto_approval_policy_passes(run: IngestionRun) -> bool:
    policy = (run.pipeline_config or {}).get("auto_approval_policy")
    if not isinstance(policy, dict):
        return False
    if policy.get("enabled") is not True:
        return False
    if policy.get("metrics_source") != "computed_gold_evaluation":
        return False
    if policy.get("passed_legal_grade_gate") is not True:
        return False
    if not policy.get("gold_dataset_version"):
        return False
    if policy.get("complete_section_number_coverage") is not True:
        return False
    if int(policy.get("meaning_changing_token_errors") or 0) != 0:
        return False
    accuracy = policy.get("character_accuracy")
    if not isinstance(accuracy, int | float):
        return False
    return float(accuracy) >= LEGAL_GRADE_MIN_CHARACTER_ACCURACY


def candidate_confidence_passes(candidate: ExtractionCandidate) -> bool:
    confidence_values = [
        value
        for value in (candidate.parser_confidence, candidate.extractor_confidence)
        if value is not None
    ]
    if not confidence_values:
        return False
    return all(value >= AUTO_APPROVAL_MIN_CONFIDENCE for value in confidence_values)


def ensure_review_issue(
    session: Session,
    *,
    candidate: ExtractionCandidate,
    issue_type: str,
    severity: ReviewIssueSeverity,
    blocking: bool,
    message: str,
    evidence: dict[str, Any],
) -> ReviewIssue:
    existing = session.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == issue_type,
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    if existing:
        return existing
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type=issue_type,
        severity=severity,
        status=ReviewIssueStatus.OPEN,
        blocking=blocking,
        message=message,
        evidence=evidence,
    )
    session.add(issue)
    return issue
