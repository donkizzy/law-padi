"""Fail-closed deterministic and model-assisted grounding checks."""

import re
import uuid
from typing import Any

from app.chat.schemas import ExplanationDraft
from app.legal.references import parse_section_reference
from app.legal.schemas import EvidenceItem

_QUOTED = re.compile(r'["“]([^"”]+)["”]')
_PRESENT_TENSE_STATUS = re.compile(
    r"\b(?:currently|today|now|current law|law in force)\b", re.I
)
_NEGATED_STATUS_CONTEXT = re.compile(
    r"\b(?:not|never|no|cannot|can't|doesn't|isn't)\b(?:\W+\w+){0,6}\W*$",
    re.I,
)


class EvidenceValidationError(ValueError):
    pass


def _asserts_current_law(text: str) -> bool:
    for match in _PRESENT_TENSE_STATUS.finditer(text):
        clause = re.split(r"[.!?;]", text[: match.start()])[-1]
        if not _NEGATED_STATUS_CONTEXT.search(clause):
            return True
    return False


def _block_error(
    text: str,
    evidence_ids: list[str],
    quotation: str | None,
    by_id: dict[str, EvidenceItem],
) -> str | None:
    if not evidence_ids or len(set(evidence_ids)) != len(evidence_ids):
        return "A block has no distinct evidence references"
    if any(identifier not in by_id for identifier in evidence_ids):
        return "A block references fabricated evidence"
    cited = [by_id[identifier] for identifier in evidence_ids]
    texts = [item.authoritative_text for item in cited]
    if quotation and not any(quotation in source for source in texts):
        return "Quoted wording differs from the source"
    for quoted in _QUOTED.findall(text):
        if not any(quoted in source for source in texts):
            return "Quoted wording differs from the source"
    parsed = parse_section_reference(text, prose=True)
    if parsed.error:
        return "Explanation contains an unsupported citation"
    for reference in parsed.references:
        if not any(
            item.canonical_path.endswith(reference.suffix)
            or reference.citation in item.ancestor_citations
            or reference.citation.casefold() in item.authoritative_text.casefold()
            # A subsection or paragraph of a cited section is inside its text.
            or reference.suffix.startswith(f"{_section_suffix(item.canonical_path)}.")
            for item in cited
        ):
            return "Explanation cites a provision outside its evidence"
    if all(
        item.legal_status == "historical" for item in cited
    ) and _asserts_current_law(text):
        return "Historical wording was described as current law"
    return None


def _section_suffix(canonical_path: str) -> str:
    index = canonical_path.find(".section")
    return canonical_path[index:] if index >= 0 else canonical_path


def validate_draft(
    draft: ExplanationDraft,
    evidence: list[EvidenceItem],
    *,
    release_id: uuid.UUID,
) -> dict[int, str]:
    """Check every block; return failures by block index.

    The opening block carries the direct answer, so any failure there rejects
    the whole explanation. Later blocks that fail are reported for removal.
    """
    by_id = {item.evidence_id: item for item in evidence}
    if len(by_id) != len(evidence) or not draft.blocks:
        raise EvidenceValidationError("Explanation requires distinct supplied evidence")
    for item in evidence:
        if item.release_id != release_id:
            raise EvidenceValidationError("Evidence belongs to another release")
    failures: dict[int, str] = {}
    for index, block in enumerate(draft.blocks):
        error = _block_error(block.text, block.evidence_ids, block.quotation, by_id)
        if error:
            if index == 0:
                raise EvidenceValidationError(error)
            failures[index] = error
    return failures


def validate_verifier(value: dict[str, Any], *, block_count: int) -> set[int]:
    """Validate the review shape; return indexes of unsupported blocks.

    An unsupported opening block rejects the explanation.
    """
    verdicts = value.get("verdicts")
    if not isinstance(verdicts, list) or len(verdicts) != block_count:
        raise EvidenceValidationError("Grounding review is incomplete")
    seen: set[int] = set()
    rejected: set[int] = set()
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            raise EvidenceValidationError("Grounding review is malformed")
        index = verdict.get("index")
        if not isinstance(index, int) or index in seen or not 0 <= index < block_count:
            raise EvidenceValidationError(
                "Grounding review has invalid block identifiers"
            )
        seen.add(index)
        if (
            verdict.get("supported") is not True
            or verdict.get("qualifications_preserved") is not True
        ):
            rejected.add(index)
    if 0 in rejected:
        raise EvidenceValidationError(
            "Explanation was not supported by its cited evidence"
        )
    return rejected
