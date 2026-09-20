"""Document-level structural validators for the parsing pipeline.

Each validator inspects a DocumentGraph (plus page roles when relevant) and
returns blocking or non-blocking issues. Validators never rewrite authoritative
wording; they only flag candidates for review.
"""

from dataclasses import dataclass
from typing import Any

from app.ingestion.validation import has_unbalanced_punctuation
from app.legal.instrument_parser import DocumentGraph

SUSPICIOUS_OCR_SUBSTITUTIONS = (
    ("§", "S"),
    (" rn ", " m "),
    ("0", "O"),
)


@dataclass(frozen=True)
class DocumentIssue:
    canonical_path: str | None
    issue_type: str
    blocking: bool
    message: str
    evidence: dict[str, Any]


def validate_document_graph(
    graph: DocumentGraph,
    *,
    page_roles: list[dict[str, Any]] | None = None,
) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    issues.extend(_duplicate_paths(graph))
    issues.extend(_missing_parents(graph))
    issues.extend(_numbering_continuity(graph))
    issues.extend(_toc_reconciliation(graph, page_roles))
    issues.extend(_cross_page_joins(graph))
    issues.extend(_unbalanced_punctuation(graph))
    issues.extend(_suspicious_ocr_substitutions(graph))
    issues.extend(_source_span_coverage(graph))
    return issues


def _duplicate_paths(graph: DocumentGraph) -> list[DocumentIssue]:
    seen: set[str] = set()
    issues: list[DocumentIssue] = []
    for node in graph.nodes:
        if node.canonical_path in seen:
            issues.append(
                DocumentIssue(
                    canonical_path=node.canonical_path,
                    issue_type="duplicate_canonical_path",
                    blocking=True,
                    message="Duplicate canonical path in parsed document graph.",
                    evidence={"canonical_path": node.canonical_path},
                )
            )
        seen.add(node.canonical_path)
    return issues


def _missing_parents(graph: DocumentGraph) -> list[DocumentIssue]:
    paths = {node.canonical_path for node in graph.nodes}
    issues: list[DocumentIssue] = []
    for node in graph.nodes:
        if node.parent_path and node.parent_path not in paths:
            issues.append(
                DocumentIssue(
                    canonical_path=node.canonical_path,
                    issue_type="missing_parent",
                    blocking=True,
                    message="Candidate parent path is absent from the document graph.",
                    evidence={"parent_path": node.parent_path},
                )
            )
    return issues


def _numbering_continuity(graph: DocumentGraph) -> list[DocumentIssue]:
    from app.ingestion.quality import _section_sort_key

    sections = sorted(
        (
            node
            for node in graph.nodes
            if node.kind == "section" and node.number and node.number.isdigit()
        ),
        key=lambda node: _section_sort_key(str(node.number)),
    )
    issues: list[DocumentIssue] = []
    for prev, current in zip(sections, sections[1:], strict=False):
        try:
            gap = int(str(current.number)) - int(str(prev.number))
        except ValueError:
            continue
        if gap > 1:
            issues.append(
                DocumentIssue(
                    canonical_path=current.canonical_path,
                    issue_type="numbering_gap",
                    blocking=False,
                    message=f"Section numbering jumps from {prev.number} to {current.number}.",
                    evidence={
                        "previous_number": prev.number,
                        "current_number": current.number,
                    },
                )
            )
    return issues


def _toc_reconciliation(
    graph: DocumentGraph, page_roles: list[dict[str, Any]] | None
) -> list[DocumentIssue]:
    if not page_roles:
        return []
    toc_pages = [page for page in page_roles if page.get("role") == "table_of_contents"]
    if not toc_pages:
        return []
    section_count = sum(1 for node in graph.nodes if node.kind == "section")
    if section_count == 0:
        return [
            DocumentIssue(
                canonical_path=None,
                issue_type="toc_reconciliation",
                blocking=True,
                message="Table of contents present but no sections were parsed.",
                evidence={"toc_page_count": len(toc_pages)},
            )
        ]
    return []


def _cross_page_joins(graph: DocumentGraph) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    for node in graph.nodes:
        if node.page_end > node.page_start and not (node.text or "").strip():
            issues.append(
                DocumentIssue(
                    canonical_path=node.canonical_path,
                    issue_type="cross_page_join_empty",
                    blocking=True,
                    message="Cross-page node has no joined text.",
                    evidence={
                        "page_start": node.page_start,
                        "page_end": node.page_end,
                    },
                )
            )
    return issues


def _unbalanced_punctuation(graph: DocumentGraph) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    for node in graph.nodes:
        text = node.text or ""
        if text and has_unbalanced_punctuation(text):
            issues.append(
                DocumentIssue(
                    canonical_path=node.canonical_path,
                    issue_type="unbalanced_punctuation",
                    blocking=True,
                    message="Node text has unbalanced punctuation.",
                    evidence={"text_length": len(text)},
                )
            )
    return issues


def _suspicious_ocr_substitutions(graph: DocumentGraph) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    for node in graph.nodes:
        text = node.text or ""
        confidence = node.parser_confidence or 0
        for needle, _hint in SUSPICIOUS_OCR_SUBSTITUTIONS:
            if needle in text and confidence < 0.8:
                issues.append(
                    DocumentIssue(
                        canonical_path=node.canonical_path,
                        issue_type="suspicious_ocr_substitution",
                        blocking=False,
                        message=f"Low-confidence text contains suspicious token {needle!r}.",
                        evidence={"token": needle},
                    )
                )
                break
    return issues


def _source_span_coverage(graph: DocumentGraph) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    for node in graph.nodes:
        spans = (node.parser_metadata or {}).get("source_spans")
        if (node.text or "").strip() and not spans:
            issues.append(
                DocumentIssue(
                    canonical_path=node.canonical_path,
                    issue_type="source_span_coverage",
                    blocking=True,
                    message="Parsed node has text but no source spans.",
                    evidence={"page_start": node.page_start},
                )
            )
    return issues


def extractor_disagreement_issue(
    *,
    canonical_path: str,
    native_confidence: float | None,
    ocr_confidence: float | None,
) -> DocumentIssue | None:
    if native_confidence is None or ocr_confidence is None:
        return None
    if abs(native_confidence - ocr_confidence) >= 0.4:
        return DocumentIssue(
            canonical_path=canonical_path,
            issue_type="extractor_disagreement",
            blocking=False,
            message="Native extraction and OCR confidence disagree sharply.",
            evidence={
                "native_confidence": native_confidence,
                "ocr_confidence": ocr_confidence,
            },
        )
    return None
