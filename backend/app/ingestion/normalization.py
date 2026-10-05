"""Conservative, versioned cleanup of extraction formatting.

Never infer missing letters or punctuation. Hard hyphens survive line wrapping;
deciding whether a compound word should lose its hyphen requires source review.
"""

import re
from dataclasses import dataclass

NORMALIZER_VERSION = "legal-page-normalizer-v3"


@dataclass(frozen=True)
class NormalizedPageText:
    text: str
    changes: list[str]


def normalize_page_text(text: str) -> NormalizedPageText:
    changes: list[str] = []

    def record(rule: str, updated: str) -> None:
        nonlocal text
        if updated != text:
            changes.append(rule)
            text = updated

    record("nonbreaking_spaces", text.replace("\u00a0", " "))
    record(
        "split_number_markers",
        re.sub(r"(?m)^(\d+)\s*\n\s*(\d+[A-Za-z]?\s*[.\-–—])", r"\1\2", text),
    )
    record(
        "split_marker_punctuation",
        re.sub(r"(?m)^(\d+[A-Za-z]?)\s*\n\s*([.\-–—])\s*", r"\1\2 ", text),
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    record("line_whitespace", "\n".join(line for line in lines if line).strip())
    # Keep line boundaries and all punctuation. A period may be part of a
    # section marker, decimal, abbreviation or dotted form, so leave it alone.
    record("spaces_before_punctuation", re.sub(r"(?<=\w) +([,;:!?])", r"\1", text))
    return NormalizedPageText(text=text, changes=changes)


def legacy_hyphen_loss_matches(original: str, source_text: str) -> bool:
    """Recognize only hard hyphens deleted by the previous line-wrap rule."""
    legacy_text = re.sub(r"-\n(?=\w)", "", source_text)
    return "".join(original.split()) == "".join(legacy_text.split())
