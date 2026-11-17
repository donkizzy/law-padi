"""Fail-closed deterministic and model-assisted grounding checks."""

import re
import uuid

from app.chat.llm.protocol import JsonObject
from app.chat.schemas import ExplanationDraft
from app.legal.instruments import CONSTITUTION_SLUG, law_mentions
from app.legal.references import (
    SectionReference,
    matches_reference,
    parse_section_reference,
    source_references,
)
from app.legal.schemas import EvidenceItem
from app.legal.topics import section_target

_QUOTED = re.compile(r'["“]([^"”]+)["”]')
_PRESENT_TENSE_STATUS = re.compile(
    r"\b(?:currently|today|now|current law|in force|up[- ]to[- ]date law|latest law)\b",
    re.I,
)
_NEGATED_STATUS_CONTEXT = re.compile(
    r"\b(?:not|never|no|cannot|can't|doesn't|isn't)\b(?:\W+\w+){0,6}\W*$",
    re.I,
)


# Answers name the relevant laws, never how they were produced.
_META_LANGUAGE = re.compile(
    r"\b(?:provided|supplied|given)\s+(?:evidence|text|sources?)\b"
    r"|\bevidence\s+(?:list|ids?|items?)\b"
    r"|\b(?:in|from)\s+the\s+evidence\b"
    r"|\bE\d+\b"
    r"|\bthis\s+answer\b"
    r"|\bsources?\s+(?:provided|given|listed|above|below)\b"
    r"|\bwording\b",
    re.I,
)
# A clause that opens with an auxiliary verb asks for a yes or no:
# "Is that allowed?", "Police held me, can they do that?".
_YES_NO_CLAUSE = re.compile(
    r"^(?:(?:and|but|so|please|sir|abeg|then|also)\s+)*"
    r"(?:can|could|do|does|did|is|are|was|were|will|would|shall|should|may|"
    r"might|must|am|have|has|had|isn't|aren't|don't|doesn't|can't|won't)\b",
    re.I,
)
_YES_NO_OPENING = re.compile(
    r"^\W*(?:generally|usually|mostly)?[,\s]*(?:yes|no)\b", re.I
)
_WORD = re.compile(r"[a-z]{4,}")
_REPEAT_OVERLAP = 0.5
# Links, email addresses and phone numbers can only come from the cited law.
# Anything else would publish text the reader, or text injected through the
# reader's question, put there.
_LINK = re.compile(
    r"\bhttps?://\S+|\bwww\.\S+"
    r"|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|ng|gov|edu|io|co|info|me|ly|app)\b",
    re.I,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DIGIT_RUN = re.compile(r"\+?\d[\d .()-]*\d")
# Shorter digit runs are citations, years, amounts and periods.
_PHONE_DIGITS = 9


class EvidenceValidationError(ValueError):
    pass


class QuestionNotAnsweredError(EvidenceValidationError):
    pass


def asks_yes_no(question: str) -> bool:
    return any(
        _YES_NO_CLAUSE.match(clause.strip())
        for clause in re.split(r"[,.;:?!\n]", question)
    )


def _repeats(text: str, earlier: str) -> bool:
    words = set(_WORD.findall(text.casefold()))
    previous = set(_WORD.findall(earlier.casefold()))
    if not words or not previous:
        return False
    return len(words & previous) / len(words | previous) >= _REPEAT_OVERLAP


def _asserts_current_law(text: str) -> bool:
    for match in _PRESENT_TENSE_STATUS.finditer(text):
        clause = re.split(r"[.!?;]", text[: match.start()])[-1]
        if not _NEGATED_STATUS_CONTEXT.search(clause):
            return True
    return False


def _contact_details(text: str) -> set[str]:
    """Links, email addresses and phone-length digit runs, normalised."""
    found = {match.casefold().rstrip(".,;:)") for match in _LINK.findall(text)}
    found.update(match.casefold() for match in _EMAIL.findall(text))
    for match in _DIGIT_RUN.findall(text):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= _PHONE_DIGITS:
            found.add(digits)
    return found


def _unsourced_contact_details(text: str, sources: list[str]) -> bool:
    details = _contact_details(text)
    if not details:
        return False
    available = set().union(*(_contact_details(source) for source in sources))
    return not details <= available


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
    if _META_LANGUAGE.search(text):
        return "A block describes how the answer was produced"
    cited = [by_id[identifier] for identifier in evidence_ids]
    texts = [item.authoritative_text for item in cited]
    if quotation and not any(quotation in source for source in texts):
        return "Quoted wording differs from the source"
    for quoted in _QUOTED.findall(text):
        if not any(quoted in source for source in texts):
            return "Quoted wording differs from the source"
    if _unsourced_contact_details(text, texts):
        return "A block gives a link or contact details that are not in its evidence"
    parsed = parse_section_reference(text, prose=True)
    if parsed.error:
        return "Explanation contains an unsupported citation"
    if any(
        not law.valid_year or law.slug not in {item.instrument_slug for item in cited}
        for law in law_mentions(text)
    ):
        return "Explanation names a law outside its evidence"
    for reference in parsed.references:
        if not any(
            item.canonical_path.startswith(f"{reference.instrument_slug}.")
            and (
                matches_reference(item.canonical_path, reference)
                or (
                    section_target(item.canonical_path)
                    == f"{reference.instrument_slug}:{reference.section}"
                    and reference.citation in item.ancestor_citations
                )
                # Preserve the existing Constitution source-cross-reference
                # allowance, but compare parsed identities, not substrings.
                # An Act citation always needs its own canonical section.
                or (
                    reference.instrument_slug == CONSTITUTION_SLUG
                    and item.instrument_slug == CONSTITUTION_SLUG
                    and reference
                    in source_references(
                        item.authoritative_text, instrument_slug=item.instrument_slug
                    )
                )
                # A subsection or paragraph of a cited section is inside its text.
                or matches_reference(
                    item.canonical_path,
                    SectionReference(
                        reference.section, instrument_slug=reference.instrument_slug
                    ),
                )
            )
            for item in cited
        ):
            return "Explanation cites a provision outside its evidence"
    if any(
        item.legal_status == "historical" for item in cited
    ) and _asserts_current_law(text):
        return "Historical wording was described as current law"
    return None


def validate_draft(
    draft: ExplanationDraft,
    evidence: list[EvidenceItem],
    *,
    release_id: uuid.UUID,
    question: str | None = None,
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
    if (
        question is not None
        and not asks_yes_no(question)
        and _YES_NO_OPENING.match(draft.blocks[0].text)
    ):
        raise QuestionNotAnsweredError(
            "The opening said yes or no to a question that does not ask for one"
        )
    failures: dict[int, str] = {}
    for index, block in enumerate(draft.blocks):
        error = _block_error(block.text, block.evidence_ids, block.quotation, by_id)
        if error is None and any(
            set(block.evidence_ids) == set(earlier.evidence_ids)
            and _repeats(block.text, earlier.text)
            for earlier in draft.blocks[:index]
        ):
            error = "A block repeats an earlier block"
        if error:
            if index == 0:
                raise EvidenceValidationError(error)
            failures[index] = error
    return failures


def validate_verifier(value: JsonObject, *, block_count: int) -> set[int]:
    """Validate the review shape; return indexes of unsupported blocks.

    An unsupported opening block, or one that does not answer the question as
    asked, rejects the explanation.
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
        if index == 0 and verdict.get("answers_question") is not True:
            raise QuestionNotAnsweredError(
                "The opening block did not answer the question as asked"
            )
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
