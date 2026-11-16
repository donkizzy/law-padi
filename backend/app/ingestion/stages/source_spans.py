import re
from typing import Any

from app.ingestion.normalization import normalize_page_text
from app.ingestion.text_alignment import aligned_source_spans, compact_text


def normalized_page_text(text: str) -> str:
    return normalize_page_text(text).text


def ancestor_headings(
    parent_path: str | None, nodes_by_path: dict[str, Any]
) -> list[str]:
    headings: list[str] = []
    current_path = parent_path
    while current_path:
        node = nodes_by_path.get(current_path)
        if not node:
            break
        if node.heading:
            headings.append(str(node.heading))
        current_path = node.parent_path
    headings.reverse()
    return headings


def source_spans_for_node(
    node: Any,
    page_payloads: list[dict[str, Any]],
    *,
    nodes_by_path: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if node.page_start is None or node.page_end is None:
        return []
    page_range = range(int(node.page_start), int(node.page_end) + 1)
    spans: list[dict[str, Any]] = []
    matched_spans: list[dict[str, Any]] = []
    node_text = str(getattr(node, "text", "") or "")
    for page in page_payloads:
        page_number = int(page["page_number"])
        if page_number not in page_range:
            continue
        for span in page.get("spans") or []:
            span_text = str(span.get("text") or "")
            if not span_text:
                continue
            spans.append(
                {
                    "page_number": page_number,
                    "text": span_text,
                    "bbox": span.get("bbox") or {},
                    "reading_order": span.get("reading_order"),
                    "method": page.get("method"),
                    "provider_version": page.get("provider_version"),
                    "confidence": page.get("confidence"),
                }
            )
            if span_text_matches_node(span_text, node_text):
                matched_spans.append(spans[-1])
    aligned = aligned_source_spans(node_text, spans)
    parent_path = getattr(node, "parent_path", None)
    while aligned is None and parent_path and nodes_by_path:
        parent = nodes_by_path.get(parent_path)
        if parent is None:
            break
        if parent.text:
            aligned = aligned_source_spans(node_text, spans, context=parent.text)
        parent_path = parent.parent_path
    return aligned or matched_spans or spans


def extractor_version(source_spans: list[dict[str, Any]]) -> str | None:
    for span in source_spans:
        provider_version = span.get("provider_version")
        if provider_version:
            return str(provider_version)
    return None


def extractor_confidence(source_spans: list[dict[str, Any]]) -> float | None:
    confidences = [
        float(span["confidence"])
        for span in source_spans
        if span.get("confidence") is not None
    ]
    if not confidences:
        return None
    return round(min(confidences), 4)


def span_text_matches_node(span_text: str, node_text: str) -> bool:
    span_tokens = coverage_tokens(span_text)
    node_tokens = coverage_tokens(node_text)
    if not span_tokens or not node_tokens:
        return False
    span_phrase = " ".join(span_tokens)
    node_phrase = " ".join(node_tokens)
    if span_phrase in node_phrase or node_phrase in span_phrase:
        return True
    span_set = set(span_tokens)
    node_set = set(node_tokens)
    return len(span_set & node_set) / max(len(span_set), 1) >= 0.6


def source_span_text_metrics(
    raw_text: str, source_spans: list[dict[str, Any]]
) -> tuple[float, float]:
    # Fragment boundaries can split words. Exact character agreement is a
    # stronger coverage check than token counts in that case.
    span_text = "\n".join(str(span.get("text") or "") for span in source_spans)
    compact_raw, _ = compact_text(raw_text)
    if compact_raw and compact_raw == compact_text(span_text)[0]:
        return 1.0, 1.0
    raw_tokens = coverage_tokens(raw_text)
    span_tokens = coverage_tokens(
        " ".join(str(span.get("text") or "") for span in source_spans)
    )
    if not raw_tokens or not span_tokens:
        return 0.0, 0.0
    raw_counts = token_counts(raw_tokens)
    span_counts = token_counts(span_tokens)
    covered = sum(
        min(count, span_counts.get(token, 0)) for token, count in raw_counts.items()
    )
    extra = sum(
        max(count - raw_counts.get(token, 0), 0) for token, count in span_counts.items()
    )
    coverage = covered / sum(raw_counts.values())
    precision = covered / (covered + extra) if covered + extra else 0.0
    return round(coverage, 4), round(precision, 4)


def coverage_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def token_counts(tokens: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts
