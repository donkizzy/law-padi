"""Conversation windows and follow-up resolution with their distinct query scopes."""

import re
import uuid
from dataclasses import dataclass
from functools import cached_property

from sqlmodel import Session, col, select

from app.chat.llm.protocol import JsonObject
from app.legal.enums import (
    MessageRole,
)
from app.legal.instruments import instrument_names
from app.legal.models import (
    ConversationMessage,
)
from app.legal.references import (
    SectionReference,
    parse_section_reference,
)
from app.legal.topics import tokens, topic_sections

_RELATIVE = re.compile(r"\b(?:that|this|its|same|it|above)\b", re.I)

_SUBSECTION = re.compile(r"\bsubsection\s*\(?\s*(\d+)\s*\)?", re.I)

_PARAGRAPH = re.compile(r"\bparagraph\s*\(?\s*([a-z])\s*\)?", re.I)

_ELLIPTICAL = re.compile(
    r"^\s*(?:why\b|how\b|what\s+(?:exceptions?|qualifications?|limitations?)\b|"
    r"what\s+about\b|and\b)",
    re.I,
)

_WORD = re.compile(r"[\w']+")

# Words that ask about whatever was just discussed without naming a subject of
# their own: "Explain that more simply", "What about the next section?",
# "What qualifications or exceptions does that section contain?".
_FOLLOWUP_WORDS = frozenset(
    tokens(
        "same above below previous earlier last next following preceding "
        "section sections subsection subsections paragraph paragraphs "
        "provision provisions part parts clause "
        "explain explanation simply simple simpler simplify plain plainly "
        "english again more detail details detailed example examples "
        "elaborate clarify further else exception exceptions qualification "
        "qualifications limitation limitations condition conditions apply "
        "applies word words term terms understand meant happen happens give "
        "show contain contains"
    )
)

# Pronouns and openings such as "why" and "how" are ordinary in new questions
# ("How long can police detain me?"), so they mark a follow-up only when the
# question has fewer subject words than this.
_STANDALONE_SUBJECT_WORDS = 3


@dataclass
class History:
    session: Session
    conversation_id: uuid.UUID
    message: ConversationMessage

    @cached_property
    def context(self) -> list[JsonObject]:
        return conversation_context(self.session, self.conversation_id, self.message)

    @cached_property
    def previous_question(self) -> str | None:
        # This query intentionally has no upper created_at bound.
        return previous_question(self.session, self.conversation_id, self.message.id)

    @cached_property
    def prior_answer(self) -> ConversationMessage | None:
        # The latest assistant query also intentionally has no time bound.
        return load_prior_answer(self.session, self.conversation_id)


def load_prior_answer(
    session: Session, conversation_id: uuid.UUID
) -> ConversationMessage | None:
    return session.exec(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role == MessageRole.ASSISTANT,
        )
        .order_by(
            col(ConversationMessage.created_at).desc(),
            col(ConversationMessage.id).desc(),
        )
    ).first()


def cited_ids(prior: ConversationMessage, *, resolved_only: bool = False) -> set[str]:
    answer = prior.answer_content or {}
    cited = {
        identifier
        for block in answer.get("blocks", [])
        for identifier in block.get("evidence_ids", [])
    }
    if not cited:
        cited = {
            identifier
            for outcome in answer.get("citation_outcomes", [])
            if not resolved_only or outcome.get("status") == "resolved"
            for identifier in outcome.get("evidence_ids", [])
        }
    return cited


def subject_words(question: str) -> list[str]:
    """Content words that could name a subject of the question's own."""
    return [token for token in tokens(question) if token not in _FOLLOWUP_WORDS]


def _names_topic(question: str) -> bool:
    # Follow-up words such as "limitations" also occur in topic phrases, so
    # only the question's remaining words may name a topic.
    remaining = " ".join(
        word
        for word in _WORD.findall(question)
        if not _FOLLOWUP_WORDS.intersection(tokens(word))
    )
    return bool(topic_sections(remaining, instrument_slugs=instrument_names()))


def is_followup_question(question: str) -> bool:
    """Read a question as a follow-up only when it has no subject of its own.

    A subsection or paragraph without a section can only mean the section just
    discussed. Any other question that names a topic the guide recognises, or
    has at least three subject words, is retrieved as written even when it
    contains "it", "this" or "that" or opens with "why" or "how". A question
    with no subject words at all ("Tell me more") is a follow-up even without
    those markers.
    """
    if _SUBSECTION.search(question) or _PARAGRAPH.search(question):
        return True
    if _names_topic(question):
        return False
    subject = subject_words(question)
    if not subject:
        return True
    return len(subject) < _STANDALONE_SUBJECT_WORDS and bool(
        _RELATIVE.search(question) or _ELLIPTICAL.search(question)
    )


def _elliptical(question: str) -> bool:
    return bool(_ELLIPTICAL.search(question)) or not subject_words(question)


def is_relative_reference(question: str) -> bool:
    return bool(
        _RELATIVE.search(question)
        or _SUBSECTION.search(question)
        or _PARAGRAPH.search(question)
    )


def conversation_context(
    session: Session, conversation_id: uuid.UUID, message: ConversationMessage
) -> list[JsonObject]:
    """Bound prior user facts and cited identities; never reuse old answer claims."""
    rows = session.exec(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.id != message.id,
            ConversationMessage.created_at <= message.created_at,
        )
        .order_by(
            col(ConversationMessage.created_at).desc(),
            col(ConversationMessage.id).desc(),
        )
        .limit(6)
    ).all()
    context: list[JsonObject] = []
    for row in reversed(rows):
        if row.role == MessageRole.USER:
            context.append(
                {"role": "user", "question": (row.english_text or row.content)[:2000]}
            )
        elif row.evidence_snapshot:
            cited = {
                identifier
                for block in (row.answer_content or {}).get("blocks", [])
                for identifier in block.get("evidence_ids", [])
            }
            provisions = [
                {
                    "citation": item.get("citation"),
                    "canonical_path": item.get("canonical_path"),
                    "provision_version_id": item.get("provision_version_id"),
                }
                for item in row.evidence_snapshot
                if item.get("evidence_id") in cited
            ]
            if provisions:
                context.append(
                    {"role": "assistant", "discussed_provisions": provisions[:5]}
                )
    return context


def prior_citations(
    session: Session, conversation_id: uuid.UUID, history: History | None = None
) -> list[str]:
    prior = (
        history.prior_answer
        if history is not None
        else load_prior_answer(session, conversation_id)
    )
    if prior is None or not prior.evidence_snapshot:
        return []
    answer = prior.answer_content or {}
    outcomes = answer.get("citation_outcomes") or []
    if any(outcome.get("status") != "resolved" for outcome in outcomes):
        return []
    cited = cited_ids(prior)
    values: list[str] = []
    for item in prior.evidence_snapshot:
        if cited and item.get("evidence_id") not in cited:
            continue
        citation = item.get("citation")
        if isinstance(citation, str) and citation not in values:
            values.append(citation)
    return values[:5]


def prior_section_path(
    session: Session, conversation_id: uuid.UUID, history: History | None = None
) -> str | None:
    prior = (
        history.prior_answer
        if history is not None
        else load_prior_answer(session, conversation_id)
    )
    if prior is None or not prior.evidence_snapshot:
        return None
    cited = cited_ids(prior, resolved_only=True)
    paths = {
        match.group(1)
        for item in prior.evidence_snapshot
        if item.get("evidence_id") in cited
        and isinstance(item.get("canonical_path"), str)
        and (
            match := re.match(r"(.*\.section\d+[a-z]?)(?:\.|$)", item["canonical_path"])
        )
    }
    return next(iter(paths)) if len(paths) == 1 else None


def relative_query(
    session: Session,
    conversation_id: uuid.UUID,
    question: str,
    history: History | None = None,
) -> str | None:
    if not (is_relative_reference(question) or _elliptical(question)):
        return None
    citations = prior_citations(session, conversation_id, history)
    if not citations:
        return None
    references = [
        parsed.reference
        for citation in citations
        if (parsed := parse_section_reference(citation)).reference is not None
    ]
    sections = list(
        dict.fromkeys(
            (reference.instrument_slug, reference.section) for reference in references
        )
    )
    if len(sections) > 1:
        if _elliptical(question) and not is_relative_reference(question):
            return " and ".join(
                SectionReference(number, instrument_slug=slug).citation
                for slug, number in sections
            )
        return None
    citation = (
        citations[0]
        if len(citations) == 1
        else SectionReference(sections[0][1], instrument_slug=sections[0][0]).citation
        if sections
        else citations[0]
    )
    match = re.search(r"Section\s+(\d+[a-z]?)", citation, re.I)
    if not match:
        return None
    parsed = parse_section_reference(citation)
    if parsed.reference is None:
        return None
    instrument_slug = parsed.reference.instrument_slug
    subsection = _SUBSECTION.search(question)
    paragraph = _PARAGRAPH.search(question)
    if subsection:
        return SectionReference(
            match.group(1), subsection.group(1), instrument_slug=instrument_slug
        ).citation
    if paragraph:
        parent = re.search(r"Section\s+\d+[a-z]?\((\d+)\)", citation, re.I)
        if parent:
            return SectionReference(
                match.group(1), parent.group(1), paragraph.group(1), instrument_slug
            ).citation
    return citation


def previous_question(
    session: Session, conversation_id: uuid.UUID, current_message_id: uuid.UUID
) -> str | None:
    previous = session.exec(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role == MessageRole.USER,
            ConversationMessage.id != current_message_id,
        )
        .order_by(col(ConversationMessage.created_at).desc())
    ).first()
    return (previous.english_text or previous.content) if previous else None
