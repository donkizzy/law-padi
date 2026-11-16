"""Dedicated durable chat worker. Run with python -m app.chat.worker."""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlmodel import Session, col, delete, select

from app.chat import EXPLANATION_PROMPT_VERSION
from app.chat.budget import BudgetExhausted, reserve, settle
from app.chat.events import emit_event
from app.chat.prompts import explanation, verifier
from app.chat.provider import DeepSeekClient, ProviderError, ProviderResult
from app.chat.schemas import ExplanationAnswer, ExplanationDraft
from app.chat.translation import TranslationRejected, translate_answer, understand
from app.chat.validation import (
    EvidenceValidationError,
    validate_draft,
    validate_verifier,
)
from app.core.config import settings
from app.core.db import engine
from app.ingestion.pgvector_repository import PgVectorRetrievalError
from app.languages.codes import Language, parse_language
from app.languages.detect import detect
from app.legal.enums import (
    AnswerStatus,
    CorpusReleaseStatus,
    EvidenceRole,
    InstrumentType,
    MessageRole,
    ProvisionKind,
)
from app.legal.evidence import (
    default_embedding_provider,
    evidence_item,
    exact_lookup,
    message_code,
    semantic_lookup,
)
from app.legal.instruments import ACJA_SLUG, instrument_label
from app.legal.models import (
    Conversation,
    ConversationMessage,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    GenerationAdmission,
    GenerationCapacity,
    GenerationReservation,
    GenerationRun,
    MessageEvidence,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    SourceDocument,
    get_datetime_utc,
)
from app.legal.public_corpus import (
    PublicCorpus,
    load_ranked_corpus,
    load_reference_corpus,
)
from app.legal.references import (
    CONSTITUTION_SLUG,
    SectionReference,
    matches_reference,
    parse_section_reference,
    source_reference_groups,
)
from app.legal.release_scope import release_instruments
from app.legal.schemas import CitationOutcome, EvidenceItem, LegalSearchResponse
from app.legal.topics import companion_sections, related_laws, section_target

_PROMPT_VERSION = EXPLANATION_PROMPT_VERSION
_DRAFT_ATTEMPTS = 2
_logger = logging.getLogger(__name__)
_RELATIVE = re.compile(r"\b(?:that|this|its|same|it|above)\b", re.I)
_SUBSECTION = re.compile(r"\bsubsection\s*\(?\s*(\d+)\s*\)?", re.I)
_PARAGRAPH = re.compile(r"\bparagraph\s*\(?\s*([a-z])\s*\)?", re.I)
_ELLIPTICAL = re.compile(
    r"^\s*(?:why\b|how\b|what\s+(?:exceptions?|qualifications?|limitations?)\b|"
    r"what\s+about\b|and\b)",
    re.I,
)
_NOTICE = {
    "cancelled": "You stopped this answer.",
    "disabled": "Explanations are switched off at the moment. You can still search and read the published laws.",
    "too_large": "That question covers too much to explain at once. Try asking about one law, section or issue.",
    "no_match": "We couldn't find a published section that answers this. Try rephrasing, or name a law and section.",
    "not_covered": "The published provisions don't seem to answer this directly. These are the closest sections we found.",
    "budget": "We've reached the available budget for explanations. You can still read the relevant sections below.",
    "unverified": "We couldn't confirm that the explanation matches the published provisions, so here are the sections themselves.",
    "unavailable": "Explanations aren't available right now. Here are the relevant published sections.",
    "stalled": "This answer took too long. Please try again.",
}
_EDITION_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def _edition_notice(evidence: list[EvidenceItem]) -> str | None:
    """One caveat per cited historical instrument, preserving legacy copy."""
    historical = [item for item in evidence if item.legal_status == "historical"]
    if not historical:
        return None
    notices: list[str] = []
    seen: set[str] = set()
    for item in historical:
        if item.instrument_slug in seen:
            continue
        seen.add(item.instrument_slug)
        if item.instrument_slug == CONSTITUTION_SLUG:
            years = _EDITION_YEAR.findall(item.edition_label)
            published = (
                f"as published in {years[-1]}" if years else "from an earlier edition"
            )
            notices.append(
                f"Based on the 1999 Constitution {published}. Later amendments aren't included yet, so check whether a section has changed before relying on it."
            )
        else:
            label = (
                item.instrument_short_title
                or item.instrument_title
                or instrument_label(item.instrument_slug)
            )
            notices.append(f"{label}: As enacted, may have been amended.")
    return "\n\n".join(notices)


@dataclass
class Prepared:
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    release_id: uuid.UUID
    question: str
    previous_question: str | None
    lookup: LegalSearchResponse
    selected: list[EvidenceItem]
    all_evidence: list[EvidenceItem]
    prompt_evidence: list[dict[str, Any]]
    too_large: bool
    conversation_context: list[dict[str, Any]] = field(default_factory=list)
    clarification_choices: list[str] = field(default_factory=list)
    related_laws: list[str] = field(default_factory=list)
    covered_laws: list[dict[str, str]] = field(default_factory=list)


def _with_coverage(message: str, prepared: Prepared | None) -> str:
    labels = [law["label"] for law in prepared.covered_laws] if prepared else []
    if not labels:
        return message
    names = (
        labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
    )
    return f"{message} This edition includes {names}."


def _notice(key: str, prepared: Prepared | None = None) -> str:
    return _with_coverage(_NOTICE[key], prepared)


def _notice_fields(key: str, prepared: Prepared | None = None) -> dict[str, Any]:
    """English notice plus the key and values a client needs to translate it."""
    laws = [law["label"] for law in prepared.covered_laws] if prepared else []
    return {
        "notice": _notice(key, prepared),
        "notice_code": key,
        "notice_params": {"laws": laws} if laws else {},
    }


def _conversation_context(
    session: Session, conversation_id: uuid.UUID, message: ConversationMessage
) -> list[dict[str, Any]]:
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
    context: list[dict[str, Any]] = []
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


def _prior_citations(session: Session, conversation_id: uuid.UUID) -> list[str]:
    prior = session.exec(
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
    if prior is None or not prior.evidence_snapshot:
        return []
    answer = prior.answer_content or {}
    outcomes = answer.get("citation_outcomes") or []
    if any(outcome.get("status") != "resolved" for outcome in outcomes):
        return []
    cited = {
        identifier
        for block in answer.get("blocks", [])
        for identifier in block.get("evidence_ids", [])
    }
    if not cited:
        cited = {
            identifier
            for outcome in outcomes
            for identifier in outcome.get("evidence_ids", [])
        }
    values: list[str] = []
    for item in prior.evidence_snapshot:
        if cited and item.get("evidence_id") not in cited:
            continue
        citation = item.get("citation")
        if isinstance(citation, str) and citation not in values:
            values.append(citation)
    return values[:5]


def _prior_section_path(session: Session, conversation_id: uuid.UUID) -> str | None:
    prior = session.exec(
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
    if prior is None or not prior.evidence_snapshot:
        return None
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
            if outcome.get("status") == "resolved"
            for identifier in outcome.get("evidence_ids", [])
        }
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


def _relative_query(
    session: Session, conversation_id: uuid.UUID, question: str
) -> str | None:
    if not (
        _RELATIVE.search(question)
        or _SUBSECTION.search(question)
        or _PARAGRAPH.search(question)
        or _ELLIPTICAL.search(question)
    ):
        return None
    citations = _prior_citations(session, conversation_id)
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
        if _ELLIPTICAL.search(question) and not (
            _RELATIVE.search(question)
            or _SUBSECTION.search(question)
            or _PARAGRAPH.search(question)
        ):
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


def _previous_question(
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


def _source_crossrefs(
    text: str, instrument_slug: str = CONSTITUTION_SLUG
) -> list[SectionReference]:
    groups = source_reference_groups(text, instrument_slug=instrument_slug)
    # Keep each marker's first reference before expanding long lists/ranges.
    # A list in Section 45 must not crowd out its later s.33, s.36(8), s.305.
    primary = [group[0] for group in groups]
    extra = [reference for group in groups for reference in group[1:]]
    return list(dict.fromkeys([*primary, *extra]))[:5]


def _context(
    session: Session,
    corpus: PublicCorpus,
    selected: list[EvidenceItem],
) -> list[EvidenceItem]:
    """Load published parents and a few unambiguous cross-references."""
    result: list[EvidenceItem] = []
    seen = {item.provision_version_id for item in selected}
    parent_ids: set[uuid.UUID] = set()
    for item in selected:
        provision = corpus.provisions.get(item.provision_id) or session.get(
            Provision, item.provision_id
        )
        while provision and provision.parent_id:
            provision = corpus.provisions.get(provision.parent_id) or session.get(
                Provision, provision.parent_id
            )
            if provision and provision.kind in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
            ):
                parent_ids.add(provision.id)
    if parent_ids:
        rows = session.exec(
            select(ProvisionVersion, Provision, SourceDocument)
            .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
            .join(
                SourceDocument,
                col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
            )
            .join(
                CorpusReleaseEntry,
                col(CorpusReleaseEntry.provision_version_id)
                == col(ProvisionVersion.id),
            )
            .where(
                CorpusReleaseEntry.release_id == corpus.release.id,
                col(Provision.id).in_(parent_ids),
            )
        ).all()
        for version, provision, source in rows:
            if version.id in seen:
                continue
            seen.add(version.id)
            corpus.provisions[provision.id] = provision
            corpus.versions[provision.id] = version
            corpus.sources[source.id] = source
            public = corpus.result(provision)
            result.append(
                evidence_item(corpus, public, f"E{len(selected) + len(result) + 1}")
            )
    crossrefs: list[SectionReference] = []
    # Provisions that limit or pair with the selected ones come first, so
    # restrictions such as Section 45 reach the explanation.
    for item in selected:
        number = section_target(item.canonical_path)
        for companion in companion_sections(number) if number else ():
            slug, _, section = companion.partition(":")
            reference = SectionReference(section, instrument_slug=slug)
            if reference not in crossrefs:
                crossrefs.append(reference)
    available_slugs = {
        instrument.slug
        for instrument in release_instruments(
            session, corpus.release.id, index_kind=corpus.index_kind
        ).values()
    }
    crossrefs = [
        reference
        for reference in crossrefs
        if reference.instrument_slug in available_slugs
    ]
    act_slugs = {
        item.instrument_slug
        for item in selected
        if item.instrument_type == InstrumentType.ACT
    } | {
        reference.instrument_slug
        for reference in crossrefs
        if reference.instrument_slug != CONSTITUTION_SLUG
    }
    # Reserve two extra context slots for canonical scope/supremacy text,
    # including when an Act first enters the answer through a companion.
    scope_references = [SectionReference("1")] if act_slugs else []
    if ACJA_SLUG in act_slugs:
        scope_references.append(SectionReference("2", instrument_slug=ACJA_SLUG))
    crossrefs = list(dict.fromkeys([*scope_references, *crossrefs]))
    crossref_limit = 7 if act_slugs else 5
    for item in selected:
        for reference in _source_crossrefs(
            item.authoritative_text, item.instrument_slug
        ):
            if reference not in crossrefs:
                crossrefs.append(reference)
            if len(crossrefs) >= crossref_limit:
                break
        if len(crossrefs) >= crossref_limit:
            break
    if crossrefs:
        focused = load_reference_corpus(
            session,
            corpus.release,
            crossrefs[:crossref_limit],
            index_kind=corpus.index_kind,
        )
        for reference in crossrefs[:crossref_limit]:
            matches = [
                provision
                for provision in focused.provisions.values()
                if provision.id in focused.versions
                and matches_reference(provision.canonical_path, reference)
            ]
            if len(matches) != 1:
                continue
            provision = matches[0]
            version = focused.versions[provision.id]
            if version.id in seen:
                continue
            seen.add(version.id)
            result.append(
                evidence_item(
                    focused,
                    focused.result(provision),
                    f"E{len(selected) + len(result) + 1}",
                )
            )
    return result


def _prompt_items(evidence: list[EvidenceItem]) -> list[dict[str, Any]]:
    """Represent contained text once while keeping each citation ID addressable."""
    ordered = sorted(
        evidence, key=lambda item: len(item.authoritative_text), reverse=True
    )
    included: list[EvidenceItem] = []
    values: dict[str, dict[str, Any]] = {}
    for item in ordered:
        container = next(
            (
                other
                for other in included
                if item.instrument_slug == other.instrument_slug
                and item.authoritative_text in other.authoritative_text
            ),
            None,
        )
        values[item.evidence_id] = {
            "id": item.evidence_id,
            "canonical_path": item.canonical_path,
            "citation": item.citation,
            "instrument_slug": item.instrument_slug,
            "instrument_title": item.instrument_title,
            "instrument_short_title": item.instrument_short_title,
            "instrument_type": item.instrument_type,
            "title": item.title,
            "ancestor_citations": item.ancestor_citations,
            "status": item.legal_status,
            "edition": item.edition_label,
            "text": item.authoritative_text if container is None else None,
            "text_in": container.evidence_id if container else None,
        }
        if container is None:
            included.append(item)
    return [values[item.evidence_id] for item in evidence]


def _shown_evidence(prepared: Prepared, cited_ids: set[str]) -> list[EvidenceItem]:
    """Sources behind a delivered explanation: what it cited or was asked about.

    Retrieval also pulls near matches and context the explanation never used;
    listing them beside the answer padded it with unrelated sections.
    """
    asked = {
        identifier
        for row in prepared.lookup.citation_outcomes
        for identifier in row.evidence_ids
    }
    shown = [
        item
        for item in prepared.all_evidence
        if item.evidence_id in cited_ids or item.evidence_id in asked
    ]
    return shown or prepared.all_evidence


# Best matches kept before any context is trimmed.
_KEEP_MATCHES = 4


def _prompt_bytes(base: dict[str, Any], prompt_evidence: list[dict[str, Any]]) -> int:
    return len(
        json.dumps({**base, "evidence": prompt_evidence}, ensure_ascii=False).encode()
    )


def _fit_prompt(
    selected: list[EvidenceItem],
    context: list[EvidenceItem],
    base: dict[str, Any],
    limit: int,
) -> tuple[list[EvidenceItem], list[EvidenceItem], list[dict[str, Any]], int]:
    """Shrink the evidence packet to the budget instead of refusing the question.

    Broad questions pull in long sections, and refusing them looked like a
    failure to understand. The lowest-ranked matches go first, because the
    context carries the restrictions and scope rules that change an answer.
    Then context is trimmed from the end; a question is only too large when its
    single best match is.
    """
    selected = list(selected)
    context = list(context)

    def measure() -> tuple[list[dict[str, Any]], int]:
        items = _prompt_items([*selected, *context])
        return items, _prompt_bytes(base, items)

    items, size = measure()
    while size > limit and len(selected) > _KEEP_MATCHES:
        selected.pop()
        items, size = measure()
    while size > limit and context:
        context.pop()
        items, size = measure()
    while size > limit and len(selected) > 1:
        selected.pop()
        items, size = measure()
    return selected, context, items, size


def prepare_run(run_id: uuid.UUID) -> Prepared:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        if run is None:
            raise ValueError("Generation run was not found")
        conversation = session.get(Conversation, run.conversation_id)
        question_message = session.get(ConversationMessage, run.user_message_id)
        release = (
            session.get(CorpusRelease, conversation.pinned_release_id)
            if conversation
            else None
        )
        build = (
            session.get(RetrievalIndexBuild, conversation.pinned_index_build_id)
            if conversation
            else None
        )
        if (
            conversation is None
            or question_message is None
            or release is None
            or release.status
            not in (CorpusReleaseStatus.PRODUCTION, CorpusReleaseStatus.RETIRED)
            or build is None
            or build.release_id != release.id
            or build.index_kind != conversation.index_kind
        ):
            raise PgVectorRetrievalError("Pinned conversation evidence is unavailable")
        question = question_message.english_text or question_message.content
        previous_question: str | None = None
        conversation_context = _conversation_context(
            session, conversation.id, question_message
        )
        clarification_choices: list[str] = []
        if run.selected_provision_version_id is not None:
            corpus = load_ranked_corpus(
                session,
                release,
                [run.selected_provision_version_id],
                index_kind=conversation.index_kind,
            )
            version = session.get(ProvisionVersion, run.selected_provision_version_id)
            provision = corpus.provisions.get(version.provision_id) if version else None
            if provision is None:
                raise PgVectorRetrievalError("Selected provision is unavailable")
            result = corpus.result(provision)
            item = evidence_item(corpus, result, "E1")
            lookup = LegalSearchResponse(
                data=[result],
                count=1,
                outcome="exact",
                retrieval_mode="exact",
                release_version=release.version,
                edition_label=corpus.edition_label,
                citation_outcomes=[
                    CitationOutcome(
                        reference=result.citation,
                        status="resolved",
                        evidence_ids=["E1"],
                    )
                ],
                evidence=[item],
            )
            selected = [item]
        else:
            parsed = parse_section_reference(question)
            is_followup = False
            semantic_query = question
            if not parsed.references and not parsed.error:
                is_followup = bool(
                    _RELATIVE.search(question)
                    or _SUBSECTION.search(question)
                    or _PARAGRAPH.search(question)
                    or _ELLIPTICAL.search(question)
                )
                if is_followup:
                    previous_question = _previous_question(
                        session, conversation.id, question_message.id
                    )
                    relative = _relative_query(session, conversation.id, question)
                    if relative:
                        parsed = parse_section_reference(relative)
                    elif previous_question:
                        references = _prior_citations(session, conversation.id)
                        sections = {
                            (
                                parsed_ref.reference.instrument_slug,
                                parsed_ref.reference.section,
                            )
                            for citation in references
                            if (
                                parsed_ref := parse_section_reference(citation)
                            ).reference
                            is not None
                        }
                        if len(sections) > 1 and (
                            _RELATIVE.search(question)
                            or _SUBSECTION.search(question)
                            or _PARAGRAPH.search(question)
                        ):
                            clarification_choices = references
                        semantic_query = f"{previous_question} {question}"
            if clarification_choices:
                corpus = load_reference_corpus(
                    session, release, [], index_kind=conversation.index_kind
                )
                lookup = LegalSearchResponse(
                    data=[],
                    count=0,
                    outcome="not_found",
                    retrieval_mode="exact",
                    release_version=release.version,
                    edition_label=corpus.edition_label,
                )
                selected = []
            elif parsed.references or parsed.error:
                corpus = load_reference_corpus(
                    session,
                    release,
                    parsed.references,
                    index_kind=conversation.index_kind,
                )
                lookup = exact_lookup(corpus, parsed, question).response
                if is_followup and lookup.outcome == "ambiguous":
                    prior_path = _prior_section_path(session, conversation.id)
                    matches = [
                        item
                        for item in lookup.data
                        if prior_path
                        and (
                            item.canonical_path == prior_path
                            or item.canonical_path.startswith(prior_path + ".")
                        )
                    ]
                    if len(matches) == 1:
                        item = evidence_item(corpus, matches[0], "E1")
                        lookup = LegalSearchResponse(
                            data=matches,
                            count=1,
                            outcome="exact",
                            retrieval_mode="exact",
                            release_version=release.version,
                            edition_label=corpus.edition_label,
                            citation_outcomes=[
                                CitationOutcome(
                                    reference=item.citation,
                                    status="resolved",
                                    evidence_ids=["E1"],
                                )
                            ],
                            evidence=[item],
                        )
                resolved_ids = {
                    identifier
                    for outcome in lookup.citation_outcomes
                    if outcome.status == "resolved"
                    for identifier in outcome.evidence_ids
                }
                selected = [
                    item for item in lookup.evidence if item.evidence_id in resolved_ids
                ]
            else:
                profile = session.get(EmbeddingProfile, build.profile_id)
                if profile is None:
                    raise PgVectorRetrievalError("Pinned search profile is unavailable")
                lookup = semantic_lookup(
                    session,
                    release,
                    profile=profile,
                    embedding_run_id=build.embedding_run_id,
                    query=semantic_query,
                    top_k=6,
                    index_kind=conversation.index_kind,
                    embedding_provider=default_embedding_provider,
                )
                selected = lookup.evidence
                corpus = load_ranked_corpus(
                    session,
                    release,
                    [item.provision_version_id for item in selected],
                    index_kind=conversation.index_kind,
                )
        context = _context(session, corpus, selected) if selected else []
        for index, item in enumerate(context, start=len(lookup.evidence) + 1):
            item.evidence_id = f"E{index}"
        all_evidence = [*lookup.evidence, *context]
        prompt_evidence = _prompt_items([*selected, *context])
        available_instruments = release_instruments(
            session, release.id, index_kind=corpus.index_kind
        )
        available_slugs = {
            instrument.slug for instrument in available_instruments.values()
        }
        covered_laws = [
            {
                "slug": instrument.slug,
                "title": instrument.title,
                "label": instrument_label(instrument.slug)
                if instrument.slug == CONSTITUTION_SLUG
                else instrument.short_title or instrument.title,
                "type": str(instrument.instrument_type),
            }
            for instrument in sorted(
                available_instruments.values(),
                key=lambda value: (value.slug != CONSTITUTION_SLUG, value.slug),
            )
        ]
        selected, context, prompt_evidence, prompt_bytes = _fit_prompt(
            selected,
            context,
            {
                "question": question,
                "previous_question": previous_question,
                "conversation_context": conversation_context,
                "covered_laws": covered_laws,
            },
            settings.CHAT_EVIDENCE_MAX_CHARS,
        )
        all_evidence = [*lookup.evidence, *context]
        return Prepared(
            run_id=run.id,
            conversation_id=conversation.id,
            release_id=release.id,
            question=question,
            previous_question=previous_question,
            lookup=lookup,
            selected=selected,
            all_evidence=all_evidence,
            prompt_evidence=prompt_evidence,
            too_large=prompt_bytes > settings.CHAT_EVIDENCE_MAX_CHARS,
            conversation_context=conversation_context,
            clarification_choices=clarification_choices,
            related_laws=related_laws(question, instrument_slugs=available_slugs)
            or (
                related_laws(previous_question, instrument_slugs=available_slugs)
                if previous_question
                else []
            ),
            covered_laws=covered_laws,
        )


def _claim_run(worker_id: str, *, run_id: uuid.UUID | None = None) -> uuid.UUID | None:
    with Session(engine) as session:
        statement = (
            select(GenerationRun)
            .where(GenerationRun.status == "pending")
            .with_for_update(skip_locked=True)
        )
        if run_id is not None:
            statement = statement.where(GenerationRun.id == run_id)
        else:
            statement = statement.order_by(col(GenerationRun.created_at))
        run = session.exec(statement.limit(1)).first()
        if run is None:
            return None
        run.status = "running"
        run.lease_owner = worker_id
        run.lease_until = get_datetime_utc() + timedelta(
            seconds=settings.CHAT_RUN_TIMEOUT_SECONDS + 30
        )
        run.attempt_count += 1
        run.updated_at = get_datetime_utc()
        emit_event(session, run, "retrieval.started", {"run_id": str(run.id)})
        session.add(run)
        session.commit()
        return run.id


def _cancelled(run_id: uuid.UUID) -> bool:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        return (
            run is None
            or run.cancellation_requested
            or settings.CHAT_GENERATION_KILL_SWITCH
        )


def _emit_sources(prepared: Prepared) -> None:
    with Session(engine) as session:
        run = session.get(GenerationRun, prepared.run_id)
        if run is None or run.status != "running":
            return
        emit_event(
            session,
            run,
            "retrieval.complete",
            {
                "evidence": [
                    item.model_dump(mode="json") for item in prepared.all_evidence
                ],
                "citation_outcomes": [
                    item.model_dump(mode="json")
                    for item in prepared.lookup.citation_outcomes
                ],
                "retrieval_mode": prepared.lookup.retrieval_mode,
                "message": prepared.lookup.message,
            },
        )
        session.commit()


def _emit_progress(run_id: uuid.UUID, event_type: str) -> None:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        if run and run.status == "running":
            emit_event(session, run, event_type, {"run_id": str(run_id)})
            session.commit()


def _reserve_call(
    run_id: uuid.UUID,
    purpose: str,
    system: str,
    payload: dict[str, Any],
    max_tokens: int,
) -> uuid.UUID:
    with Session(engine) as session:
        run = session.exec(
            select(GenerationRun).where(GenerationRun.id == run_id).with_for_update()
        ).one()
        if run.cancellation_requested or settings.CHAT_GENERATION_KILL_SWITCH:
            raise asyncio.CancelledError
        reservation = reserve(
            session,
            run_id=run_id,
            purpose=purpose,
            prompt_chars=len(system.encode())
            + len(json.dumps(payload, ensure_ascii=False).encode())
            + 128,
            max_output_tokens=max_tokens,
        )
        run.provider_started_at = get_datetime_utc()
        session.add(run)
        session.commit()
        return reservation.id


def _settle_call(
    reservation_id: uuid.UUID, result: ProviderResult | None, *, uncertain: bool
) -> None:
    with Session(engine) as session:
        settle(
            session,
            reservation_id,
            prompt_tokens=result.prompt_tokens if result else None,
            completion_tokens=result.completion_tokens if result else None,
            uncertain=uncertain,
        )
        session.commit()


async def _call(
    provider: DeepSeekClient,
    run_id: uuid.UUID,
    purpose: str,
    system: str,
    payload: dict[str, Any],
    *,
    max_tokens: int,
    thinking: bool = False,
) -> ProviderResult:
    for attempt in range(2):
        reservation_id = await asyncio.to_thread(
            _reserve_call, run_id, purpose, system, payload, max_tokens
        )
        try:
            result = await provider.complete_json(
                system=system,
                payload=payload,
                max_tokens=max_tokens,
                thinking=thinking,
            )
        except ProviderError as exc:
            await asyncio.to_thread(
                _settle_call, reservation_id, None, uncertain=exc.uncertain_charge
            )
            if exc.retryable and not exc.uncertain_charge and attempt == 0:
                continue
            raise
        except BaseException:
            await asyncio.to_thread(_settle_call, reservation_id, None, uncertain=True)
            raise
        await asyncio.to_thread(_settle_call, reservation_id, result, uncertain=False)
        return result
    raise ProviderError("DeepSeek request failed")


def _finish(
    run_id: uuid.UUID,
    worker_id: str,
    answer: ExplanationAnswer,
    *,
    provider_result: ProviderResult | None = None,
    validation: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
) -> None:
    with Session(engine) as session:
        run = session.exec(
            select(GenerationRun).where(GenerationRun.id == run_id).with_for_update()
        ).first()
        if run is None or run.status != "running" or run.lease_owner != worker_id:
            return
        if run.cancellation_requested or settings.CHAT_GENERATION_KILL_SWITCH:
            answer = ExplanationAnswer(
                outcome="cancelled", **_notice_fields("cancelled")
            )
        content = "\n\n".join(block.text for block in answer.blocks)
        message = ConversationMessage(
            conversation_id=run.conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            answer_status=AnswerStatus.COMPLETED
            if answer.outcome in ("completed", "partial_evidence")
            else AnswerStatus.INSUFFICIENT_EVIDENCE
            if answer.outcome in ("insufficient_evidence", "clarification_required")
            else AnswerStatus.FAILED,
            model_provider="deepseek" if provider_result else None,
            model_name=provider_result.model if provider_result else None,
            answer_content=answer.model_dump(mode="json"),
            evidence_snapshot=[
                item.model_dump(mode="json") for item in answer.evidence
            ],
            prompt_version=_PROMPT_VERSION,
            usage={
                "prompt_tokens": provider_result.prompt_tokens,
                "completion_tokens": provider_result.completion_tokens,
            }
            if provider_result
            else None,
            validation_result={**(validation or {}), **(telemetry or {})}
            if validation or telemetry
            else None,
        )
        session.add(message)
        session.flush()
        for rank, item in enumerate(answer.evidence, start=1):
            session.add(
                MessageEvidence(
                    message_id=message.id,
                    provision_version_id=item.provision_version_id,
                    release_id=item.release_id,
                    evidence_role=EvidenceRole.PRIMARY
                    if rank == 1
                    else EvidenceRole.SUPPORTING,
                    retrieval_rank=rank,
                    citation_label=item.citation,
                    evidence_snapshot=item.model_dump(mode="json"),
                )
            )
        run.assistant_message_id = message.id
        run.status = (
            "completed"
            if answer.outcome in ("completed", "partial_evidence")
            else "failed"
        )
        run.outcome = answer.outcome
        run.updated_at = get_datetime_utc()
        capacity = session.exec(
            select(GenerationCapacity)
            .where(GenerationCapacity.id == 1)
            .with_for_update()
        ).one()
        capacity.active_count = max(0, capacity.active_count - 1)
        reservations = session.exec(
            select(GenerationReservation).where(GenerationReservation.run_id == run_id)
        ).all()
        operational = {
            "run_id": str(run_id),
            "outcome": answer.outcome,
            "active_generations": capacity.active_count,
            "prompt_tokens": provider_result.prompt_tokens if provider_result else 0,
            "completion_tokens": provider_result.completion_tokens
            if provider_result
            else 0,
            "reserved_micro_usd": sum(
                row.reserved_micro_usd
                for row in reservations
                if row.status in ("reserved", "uncertain")
            ),
            "actual_micro_usd": sum(row.actual_micro_usd or 0 for row in reservations),
            **(telemetry or {}),
        }
        session.add(capacity)
        session.add(run)
        emit_event(
            session,
            run,
            "answer.complete",
            {"message_id": str(message.id), "answer": answer.model_dump(mode="json")},
        )
        session.commit()
        _logger.info("chat_run_finished %s", json.dumps(operational, sort_keys=True))


@dataclass(frozen=True)
class ReaderQuestion:
    message_id: uuid.UUID
    question: str
    detected_language: str | None
    answer_language: str | None
    explains_selected_provision: bool


def _reader_question(run_id: uuid.UUID) -> ReaderQuestion:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        message = session.get(ConversationMessage, run.user_message_id) if run else None
        if run is None or message is None:
            raise ValueError("Generation run was not found")
        return ReaderQuestion(
            message_id=message.id,
            question=message.content,
            detected_language=message.detected_language,
            answer_language=run.answer_language,
            explains_selected_provision=run.selected_provision_version_id is not None,
        )


def _record_understanding(
    message_id: uuid.UUID, language: Language | None, english_text: str | None
) -> None:
    with Session(engine) as session:
        message = session.get(ConversationMessage, message_id)
        if message is None:
            return
        message.detected_language = language.value if language else "other"
        message.english_text = english_text
        session.add(message)
        session.commit()


async def _reader_languages(
    provider: DeepSeekClient,
    run_id: uuid.UUID,
    reader: ReaderQuestion,
    telemetry: dict[str, Any],
) -> tuple[Language | None, Language]:
    """Return the question's language and the language to answer in.

    A question that is not clearly English is rendered in English once, before
    retrieval, and stored so retries and follow-ups reuse it. Nothing changes
    while English is the only enabled language.
    """
    enabled = settings.CHAT_LANGUAGES_ENABLED
    explicit = parse_language(reader.answer_language)
    if explicit not in enabled:
        explicit = None
    language = parse_language(reader.detected_language)
    if (
        reader.detected_language is None
        and not reader.explains_selected_provision
        and len(enabled) > 1
    ):
        detection = detect(reader.question)
        language = detection.language
        english: str | None = None
        if not detection.confident:

            async def call(
                purpose: str, system: str, payload: dict[str, Any], max_tokens: int
            ) -> ProviderResult:
                return await _call(
                    provider, run_id, purpose, system, payload, max_tokens=max_tokens
                )

            try:
                understood = await understand(
                    call, reader.question, settings.DEEPSEEK_MAX_OUTPUT_TOKENS
                )
            except (ProviderError, TranslationRejected) as exc:
                # Retrieval still runs on the original wording.
                telemetry["understanding"] = "fallback"
                telemetry["understanding_reason"] = str(exc)[:200]
            else:
                telemetry["understanding"] = "completed"
                language = understood.language
                if language != Language.ENGLISH:
                    english = understood.english_question
        await asyncio.to_thread(
            _record_understanding, reader.message_id, language, english
        )
    telemetry["question_language"] = language.value if language else None
    target = explicit or (language if language in enabled else Language.ENGLISH)
    return language, target


async def _translate(
    provider: DeepSeekClient,
    run_id: uuid.UUID,
    answer: ExplanationAnswer,
    language: Language,
    telemetry: dict[str, Any],
    *,
    timeout_seconds: float = 60.0,
) -> None:
    """Attach a checked translation; on any failure the English answer stands."""

    async def call(
        purpose: str, system: str, payload: dict[str, Any], max_tokens: int
    ) -> ProviderResult:
        return await _call(
            provider, run_id, purpose, system, payload, max_tokens=max_tokens
        )

    await asyncio.to_thread(_emit_progress, run_id, "translation.started")
    started = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            answer.translation = await translate_answer(
                call,
                answer,
                language,
                max_tokens=settings.TRANSLATION_MAX_OUTPUT_TOKENS,
                judge_max_tokens=settings.DEEPSEEK_VERIFIER_MAX_OUTPUT_TOKENS,
            )
    except (ProviderError, BudgetExhausted, ValueError, TimeoutError) as exc:
        telemetry["translation"] = "fallback"
        telemetry["translation_reason"] = (
            "Translation timed out" if isinstance(exc, TimeoutError) else str(exc)[:200]
        )
    else:
        telemetry["translation"] = "completed"
    telemetry["translation_ms"] = round((time.perf_counter() - started) * 1000)


async def process_run(
    run_id: uuid.UUID, worker_id: str, provider: DeepSeekClient | None = None
) -> None:
    provider = provider or DeepSeekClient()
    started = time.perf_counter()
    telemetry: dict[str, Any] = {}
    prepared: Prepared | None = None
    provider_result: ProviderResult | None = None
    validation_stage = "preparation"
    expected_verdict_count: int | None = None
    verifier_verdict_count: int | None = None
    try:
        async with asyncio.timeout(settings.CHAT_RUN_TIMEOUT_SECONDS):
            reader = await asyncio.to_thread(_reader_question, run_id)
            question_language, answer_language = await _reader_languages(
                provider, run_id, reader, telemetry
            )
            prepared = await asyncio.to_thread(prepare_run, run_id)
            telemetry["retrieval_ms"] = round((time.perf_counter() - started) * 1000)
            telemetry["retrieval_mode"] = prepared.lookup.retrieval_mode
            telemetry["retrieval_fallback"] = (
                prepared.lookup.retrieval_mode == "lexical"
            )
            await asyncio.to_thread(_emit_sources, prepared)
            if await asyncio.to_thread(_cancelled, run_id):
                answer = ExplanationAnswer(
                    outcome="cancelled", **_notice_fields("cancelled")
                )
            elif prepared.clarification_choices:
                answer = ExplanationAnswer(
                    outcome="clarification_required",
                    notice="Which section do you mean: "
                    + ", ".join(prepared.clarification_choices)
                    + "?",
                    notice_code="clarify_section",
                    notice_params={"choices": prepared.clarification_choices},
                    follow_up_questions=[
                        f"Explain {citation}"
                        for citation in prepared.clarification_choices
                    ],
                )
            elif prepared.too_large:
                answer = ExplanationAnswer(
                    outcome="clarification_required",
                    evidence=prepared.all_evidence,
                    citation_outcomes=prepared.lookup.citation_outcomes,
                    **_notice_fields("too_large", prepared),
                )
            elif not prepared.selected:
                answer = ExplanationAnswer(
                    outcome="insufficient_evidence",
                    evidence=prepared.all_evidence,
                    citation_outcomes=prepared.lookup.citation_outcomes,
                    related_laws=prepared.related_laws,
                    **(
                        {
                            **_notice_fields("no_match", prepared),
                            "notice": _with_coverage(prepared.lookup.message, prepared),
                            "notice_code": message_code(prepared.lookup.message),
                        }
                        if prepared.lookup.message
                        else _notice_fields("no_match", prepared)
                    ),
                )
            else:
                payload: dict[str, Any] = {
                    "question": prepared.question,
                    "previous_question": prepared.previous_question,
                    "conversation_context": prepared.conversation_context,
                    "unresolved_references": [
                        row.model_dump(mode="json")
                        for row in prepared.lookup.citation_outcomes
                        if row.status != "resolved"
                    ],
                    "evidence": prepared.prompt_evidence,
                    "covered_laws": prepared.covered_laws,
                }
                allowed_ids = {str(item["id"]) for item in prepared.prompt_evidence}
                allowed_evidence = [
                    item
                    for item in prepared.all_evidence
                    if item.evidence_id in allowed_ids
                ]
                await asyncio.to_thread(_emit_progress, run_id, "generation.started")
                generation_started = time.perf_counter()
                prompt_tokens = 0
                completion_tokens = 0
                drafted: ExplanationAnswer | None = None
                # A rejected draft gets one rewrite with the reason; a second
                # rejection fails closed.
                for attempt in range(_DRAFT_ATTEMPTS):
                    try:
                        validation_stage = "generation"
                        provider_result = await _call(
                            provider,
                            run_id,
                            "generation",
                            explanation.TEXT,
                            payload,
                            max_tokens=settings.DEEPSEEK_GENERATION_MAX_OUTPUT_TOKENS,
                            thinking=settings.DEEPSEEK_GENERATION_THINKING,
                        )
                        prompt_tokens += provider_result.prompt_tokens
                        completion_tokens += provider_result.completion_tokens
                        telemetry["generation_ms"] = round(
                            (time.perf_counter() - generation_started) * 1000
                        )
                        validation_stage = "generation_schema"
                        draft = ExplanationDraft.model_validate(provider_result.value)
                        telemetry["direct_answer"] = draft.direct_answer
                        follow_ups = [
                            question.strip()
                            for question in draft.follow_up_questions[:3]
                            if question.strip()
                        ]
                        if not draft.blocks:
                            drafted = ExplanationAnswer(
                                outcome="insufficient_evidence",
                                follow_up_questions=follow_ups,
                                citation_outcomes=prepared.lookup.citation_outcomes,
                                evidence=prepared.all_evidence,
                                related_laws=prepared.related_laws,
                                **_notice_fields("not_covered", prepared),
                            )
                            break
                        validation_stage = "deterministic"
                        dropped = validate_draft(
                            draft,
                            allowed_evidence,
                            release_id=prepared.release_id,
                            question=prepared.question,
                        )
                        if await asyncio.to_thread(_cancelled, run_id):
                            raise asyncio.CancelledError
                        await asyncio.to_thread(
                            _emit_progress, run_id, "verification.started"
                        )
                        verification_started = time.perf_counter()
                        expected_verdict_count = len(draft.blocks)
                        verdict = await _call(
                            provider,
                            run_id,
                            "verification",
                            verifier.TEXT,
                            {
                                "question": prepared.question,
                                "direct_answer": draft.direct_answer,
                                "evidence": prepared.prompt_evidence,
                                "covered_laws": prepared.covered_laws,
                                "missing_facts": draft.missing_facts[:4],
                                "previous_question": prepared.previous_question,
                                "conversation_context": prepared.conversation_context,
                                "blocks": [
                                    {"index": index, **block.model_dump()}
                                    for index, block in enumerate(draft.blocks)
                                ],
                            },
                            max_tokens=settings.DEEPSEEK_VERIFIER_MAX_OUTPUT_TOKENS,
                            thinking=settings.DEEPSEEK_VERIFIER_THINKING,
                        )
                        prompt_tokens += verdict.prompt_tokens
                        completion_tokens += verdict.completion_tokens
                        validation_stage = "verification"
                        verdict_rows = verdict.value.get("verdicts")
                        verifier_verdict_count = (
                            len(verdict_rows)
                            if isinstance(verdict_rows, list)
                            else None
                        )
                        rejected = validate_verifier(
                            verdict.value, block_count=len(draft.blocks)
                        )
                    except (EvidenceValidationError, ValueError) as exc:
                        if attempt + 1 >= _DRAFT_ATTEMPTS:
                            raise
                        reason = (
                            str(exc)
                            if isinstance(exc, EvidenceValidationError)
                            else "The response did not match the required JSON shape"
                        )
                        telemetry["revision_reason"] = reason
                        payload = {**payload, "revision_reason": reason}
                        continue
                    telemetry["verification_ms"] = round(
                        (time.perf_counter() - verification_started) * 1000
                    )
                    telemetry["draft_attempts"] = attempt + 1
                    # Later blocks that fail a check are removed rather than
                    # failing the answer; each kept block passed both checks.
                    removed = set(dropped) | rejected
                    telemetry["removed_blocks"] = len(removed)
                    if dropped:
                        telemetry["removed_block_reasons"] = sorted(
                            set(dropped.values())
                        )
                    kept_blocks = [
                        block
                        for index, block in enumerate(draft.blocks)
                        if index not in removed
                    ]
                    cited_ids = {
                        identifier
                        for block in kept_blocks
                        for identifier in block.evidence_ids
                    }
                    edition = _edition_notice(
                        [
                            item
                            for item in prepared.all_evidence
                            if item.evidence_id in cited_ids
                        ]
                    )
                    drafted = ExplanationAnswer(
                        outcome="partial_evidence"
                        if any(
                            row.status != "resolved"
                            for row in prepared.lookup.citation_outcomes
                        )
                        else "completed",
                        blocks=kept_blocks,
                        missing_facts=draft.missing_facts[:4],
                        follow_up_questions=follow_ups,
                        citation_outcomes=prepared.lookup.citation_outcomes,
                        evidence=_shown_evidence(prepared, cited_ids),
                        related_laws=prepared.related_laws,
                        notice=edition,
                        notice_code="edition" if edition else None,
                    )
                    break
                assert drafted is not None and provider_result is not None
                answer = drafted
                provider_result = ProviderResult(
                    value=provider_result.value,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model=provider_result.model,
                )
            answer.question_language = question_language
            answer.answer_language = answer_language
            if answer_language != Language.ENGLISH and answer.blocks:
                await _translate(
                    provider,
                    run_id,
                    answer,
                    answer_language,
                    telemetry,
                    timeout_seconds=min(
                        60.0,
                        max(
                            0.0,
                            settings.CHAT_RUN_TIMEOUT_SECONDS
                            - (time.perf_counter() - started)
                            - 5.0,
                        ),
                    ),
                )
            telemetry["total_ms"] = round((time.perf_counter() - started) * 1000)
            await asyncio.to_thread(
                _finish,
                run_id,
                worker_id,
                answer,
                provider_result=provider_result,
                validation={"deterministic": True, "verifier": True}
                if answer.blocks
                else None,
                telemetry=telemetry,
            )
    except BudgetExhausted:
        telemetry["total_ms"] = round((time.perf_counter() - started) * 1000)
        await asyncio.to_thread(
            _finish,
            run_id,
            worker_id,
            ExplanationAnswer(
                outcome="budget_exhausted",
                evidence=prepared.all_evidence if prepared else [],
                **_notice_fields("budget"),
            ),
            telemetry=telemetry,
        )
    except (EvidenceValidationError, ValueError) as exc:
        telemetry["total_ms"] = round((time.perf_counter() - started) * 1000)
        await asyncio.to_thread(
            _finish,
            run_id,
            worker_id,
            ExplanationAnswer(
                outcome="validation_failed",
                evidence=prepared.all_evidence if prepared else [],
                **_notice_fields("unverified", prepared),
            ),
            validation={
                "deterministic_or_verifier": False,
                "failure_stage": validation_stage,
                "failure_reason": str(exc)
                if isinstance(exc, EvidenceValidationError)
                else type(exc).__name__,
                "expected_verdict_count": expected_verdict_count,
                "verifier_verdict_count": verifier_verdict_count,
            },
            telemetry=telemetry,
        )
    except asyncio.CancelledError:
        telemetry["total_ms"] = round((time.perf_counter() - started) * 1000)
        await asyncio.to_thread(
            _finish,
            run_id,
            worker_id,
            ExplanationAnswer(outcome="cancelled", **_notice_fields("cancelled")),
            telemetry=telemetry,
        )
    except ProviderError, TimeoutError, PgVectorRetrievalError:
        telemetry["total_ms"] = round((time.perf_counter() - started) * 1000)
        await asyncio.to_thread(
            _finish,
            run_id,
            worker_id,
            ExplanationAnswer(
                outcome="provider_failure",
                evidence=prepared.all_evidence if prepared else [],
                **_notice_fields("unavailable", prepared),
            ),
            telemetry=telemetry,
        )
    except Exception:
        telemetry["total_ms"] = round((time.perf_counter() - started) * 1000)
        await asyncio.to_thread(
            _finish,
            run_id,
            worker_id,
            ExplanationAnswer(
                outcome="provider_failure",
                evidence=prepared.all_evidence if prepared else [],
                **_notice_fields("unavailable", prepared),
            ),
            telemetry=telemetry,
        )


def recover_expired() -> None:
    """Retry retrieval crashes; never repeat a call after dispatch is uncertain."""
    failed: list[tuple[uuid.UUID, str]] = []
    with Session(engine) as session:
        expired = session.exec(
            select(GenerationRun)
            .where(
                GenerationRun.status == "running",
                col(GenerationRun.lease_until) < get_datetime_utc(),
            )
            .with_for_update(skip_locked=True)
            .limit(20)
        ).all()
        for run in expired:
            if run.provider_started_at is None and run.attempt_count < 2:
                run.status = "pending"
                run.lease_owner = None
                run.lease_until = None
            else:
                if run.lease_owner:
                    failed.append((run.id, run.lease_owner))
            session.add(run)
        session.commit()
    for run_id, worker_id in failed:
        _finish(
            run_id,
            worker_id,
            ExplanationAnswer(
                outcome="provider_failure",
                **_notice_fields("stalled"),
            ),
        )


def expire_guest_conversations() -> int:
    """Remove inactive guest history and its cascaded evidence and event traces."""
    removed = 0
    with Session(engine) as session:
        now = get_datetime_utc()
        session.exec(
            delete(GenerationAdmission).where(
                col(GenerationAdmission.created_at) < now - timedelta(days=1)
            )
        )
        # Release quota row locks before acquiring conversation or capacity locks.
        session.commit()
        expired = session.exec(
            select(Conversation)
            .where(
                col(Conversation.user_id).is_(None),
                col(Conversation.updated_at) < now - timedelta(days=30),
            )
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        if not expired:
            return 0
        capacity = session.exec(
            select(GenerationCapacity)
            .where(GenerationCapacity.id == 1)
            .with_for_update()
        ).one()
        for conversation in expired:
            active_count = len(
                session.exec(
                    select(GenerationRun.id).where(
                        GenerationRun.conversation_id == conversation.id,
                        col(GenerationRun.status).in_(["pending", "running"]),
                    )
                ).all()
            )
            capacity.active_count = max(0, capacity.active_count - active_count)
            session.delete(conversation)
            removed += 1
        session.add(capacity)
        session.commit()
    return removed


async def run_forever() -> None:
    worker_id = str(uuid.uuid4())
    active: set[asyncio.Task[None]] = set()
    last_retention = 0.0
    while True:
        now = asyncio.get_running_loop().time()
        if now - last_retention >= 3600:
            await asyncio.to_thread(expire_guest_conversations)
            last_retention = now
        await asyncio.to_thread(recover_expired)
        if not settings.CHAT_GENERATION_ENABLED or settings.CHAT_GENERATION_KILL_SWITCH:
            while run_id := await asyncio.to_thread(_claim_run, worker_id):
                await asyncio.to_thread(
                    _finish,
                    run_id,
                    worker_id,
                    ExplanationAnswer(
                        outcome="cancelled",
                        **_notice_fields("disabled"),
                    ),
                )
            await asyncio.sleep(2)
            continue
        while len(active) < settings.CHAT_WORKER_CONCURRENCY:
            run_id = await asyncio.to_thread(_claim_run, worker_id)
            if run_id is None:
                break
            task = asyncio.create_task(process_run(run_id, worker_id))
            active.add(task)
            task.add_done_callback(active.discard)
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(run_forever())
