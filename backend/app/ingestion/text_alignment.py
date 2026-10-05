"""Locate exact source text despite extraction whitespace differences."""

from typing import Any


def compact_text(text: str) -> tuple[str, list[int]]:
    offsets = [index for index, char in enumerate(text) if not char.isspace()]
    return "".join(text[index] for index in offsets), offsets


def unique_text_range(
    needle: str, source: str, *, context: str | None = None
) -> tuple[int, int] | None:
    if context:
        context_range = unique_text_range(context, source)
        if context_range is None:
            return None
        start, end = context_range
        local_range = unique_text_range(needle, source[start:end])
        return (start + local_range[0], start + local_range[1]) if local_range else None
    compact_needle, _ = compact_text(needle)
    compact_source, offsets = compact_text(source)
    if not compact_needle:
        return None
    start = compact_source.find(compact_needle)
    if start < 0 or compact_source.find(compact_needle, start + 1) >= 0:
        return None
    return offsets[start], offsets[start + len(compact_needle) - 1] + 1


def aligned_source_spans(
    text: str, spans: list[dict[str, Any]], *, context: str | None = None
) -> list[dict[str, Any]] | None:
    """Trim span text to an exact candidate, retaining original coordinates.

    The original span text and character offsets remain available for audit.
    Bounding boxes still enclose the original fragment: no coordinates are
    fabricated when a PDF callback contains several legal units.
    """
    source = "\n".join(str(span.get("text") or "") for span in spans)
    match = unique_text_range(text, source, context=context)
    if match is None:
        return None
    start, end = match
    aligned = []
    cursor = 0
    for span in spans:
        original = str(span.get("text") or "")
        local_start = max(start - cursor, 0)
        local_end = min(end - cursor, len(original))
        if local_start < local_end:
            aligned.append(
                {
                    **span,
                    "text": original[local_start:local_end],
                    "original_span_text": original,
                    "source_text_start": local_start,
                    "source_text_end": local_end,
                }
            )
        cursor += len(original) + 1
    return aligned
