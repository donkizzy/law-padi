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


def validate_draft(
    draft: ExplanationDraft,
    evidence: list[EvidenceItem],
    *,
    release_id: uuid.UUID,
) -> None:
    by_id = {item.evidence_id: item for item in evidence}
    if len(by_id) != len(evidence) or not draft.blocks:
        raise EvidenceValidationError("Explanation requires distinct supplied evidence")
    for item in evidence:
        if item.release_id != release_id:
            raise EvidenceValidationError("Evidence belongs to another release")
    for block in draft.blocks:
        if not block.evidence_ids or len(set(block.evidence_ids)) != len(
            block.evidence_ids
        ):
            raise EvidenceValidationError("A block has no distinct evidence references")
        if any(identifier not in by_id for identifier in block.evidence_ids):
            raise EvidenceValidationError("A block references fabricated evidence")
        cited = [by_id[identifier] for identifier in block.evidence_ids]
        texts = [item.authoritative_text for item in cited]
        if block.quotation and not any(block.quotation in text for text in texts):
            raise EvidenceValidationError("Quoted wording differs from the source")
        for quotation in _QUOTED.findall(block.text):
            if not any(quotation in text for text in texts):
                raise EvidenceValidationError("Quoted wording differs from the source")
        parsed = parse_section_reference(block.text, prose=True)
        if parsed.error:
            raise EvidenceValidationError(
                "Explanation contains an unsupported citation"
            )
        for reference in parsed.references:
            if not any(
                item.canonical_path.endswith(reference.suffix)
                or reference.citation in item.ancestor_citations
                or reference.citation.casefold() in item.authoritative_text.casefold()
                for item in cited
            ):
                raise EvidenceValidationError(
                    "Explanation cites a provision outside its evidence"
                )
        if all(
            item.legal_status == "historical" for item in cited
        ) and _asserts_current_law(block.text):
            raise EvidenceValidationError(
                "Historical wording was described as current law"
            )


def validate_verifier(value: dict[str, Any], *, block_count: int) -> None:
    verdicts = value.get("verdicts")
    if not isinstance(verdicts, list) or len(verdicts) != block_count:
        raise EvidenceValidationError("Grounding review is incomplete")
    seen: set[int] = set()
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
            raise EvidenceValidationError(
                "Explanation was not supported by its cited evidence"
            )
