"""Pinned corpus loading, follow-up lookup and evidence packet assembly."""

import uuid
from dataclasses import dataclass, field

from sqlmodel import Session

from app.chat import runs
from app.chat.evidence_packet import Prepared, expand_context, fit_prompt, prompt_items
from app.chat.history import (
    History,
    is_followup_question,
    is_relative_reference,
    prior_citations,
    prior_section_path,
    relative_query,
)
from app.core.config import settings
from app.ingestion.pgvector_repository import PgVectorRetrievalError
from app.legal.enums import CorpusReleaseStatus
from app.legal.evidence import (
    default_embedding_provider,
    evidence_item,
    exact_lookup,
    semantic_lookup,
)
from app.legal.instruments import instrument_label
from app.legal.models import (
    Conversation,
    ConversationMessage,
    CorpusRelease,
    EmbeddingProfile,
    GenerationRun,
    ProvisionVersion,
    RetrievalIndexBuild,
)
from app.legal.public_corpus import (
    PublicCorpus,
    load_ranked_corpus,
    load_reference_corpus,
)
from app.legal.references import (
    CONSTITUTION_SLUG,
    ReferenceParse,
    parse_section_reference,
)
from app.legal.release_scope import release_instruments
from app.legal.schemas import CitationOutcome, EvidenceItem, LegalSearchResponse
from app.legal.topics import related_laws


@dataclass(frozen=True)
class PinnedRun:
    run: GenerationRun
    conversation: Conversation
    message: ConversationMessage
    release: CorpusRelease
    build: RetrievalIndexBuild


@dataclass
class ResolvedQuestion:
    semantic_query: str
    parsed: ReferenceParse | None = None
    previous_question: str | None = None
    is_followup: bool = False
    clarification_choices: list[str] = field(default_factory=list)


@dataclass
class EvidenceSelection:
    corpus: PublicCorpus
    lookup: LegalSearchResponse
    selected: list[EvidenceItem]


def load_pinned_run(session: Session, run_id: uuid.UUID) -> PinnedRun:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise runs.RunNotFound("Generation run was not found")
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
    return PinnedRun(run, conversation, question_message, release, build)


def selected_evidence(session: Session, pinned: PinnedRun) -> EvidenceSelection:
    selected_id = pinned.run.selected_provision_version_id
    assert selected_id is not None
    corpus = load_ranked_corpus(
        session,
        pinned.release,
        [selected_id],
        index_kind=pinned.conversation.index_kind,
    )
    version = session.get(ProvisionVersion, selected_id)
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
        release_version=pinned.release.version,
        edition_label=corpus.edition_label,
        citation_outcomes=[
            CitationOutcome(
                reference=result.citation, status="resolved", evidence_ids=["E1"]
            )
        ],
        evidence=[item],
    )
    return EvidenceSelection(corpus, lookup, [item])


def resolve_question(question: str, history: History) -> ResolvedQuestion:
    parsed = parse_section_reference(question)
    result = ResolvedQuestion(semantic_query=question, parsed=parsed)
    if not parsed.references and not parsed.error:
        result.is_followup = is_followup_question(question)
        if result.is_followup:
            result.previous_question = history.previous_question
            relative = relative_query(
                history.session, history.conversation_id, question, history
            )
            if relative:
                result.parsed = parse_section_reference(relative)
            elif result.previous_question:
                references = prior_citations(
                    history.session, history.conversation_id, history
                )
                sections = {
                    (parsed_ref.reference.instrument_slug, parsed_ref.reference.section)
                    for citation in references
                    if (parsed_ref := parse_section_reference(citation)).reference
                    is not None
                }
                if len(sections) > 1 and is_relative_reference(question):
                    result.clarification_choices = references
                result.semantic_query = f"{result.previous_question} {question}"
    return result


def exact_evidence(
    session: Session,
    pinned: PinnedRun,
    question: str,
    resolved: ResolvedQuestion,
    history: History,
) -> EvidenceSelection:
    assert resolved.parsed is not None
    corpus = load_reference_corpus(
        session,
        pinned.release,
        resolved.parsed.references,
        index_kind=pinned.conversation.index_kind,
    )
    lookup = exact_lookup(corpus, resolved.parsed, question).response
    if resolved.is_followup and lookup.outcome == "ambiguous":
        prior_path = prior_section_path(session, pinned.conversation.id, history)
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
                release_version=pinned.release.version,
                edition_label=corpus.edition_label,
                citation_outcomes=[
                    CitationOutcome(
                        reference=item.citation, status="resolved", evidence_ids=["E1"]
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
    selected = [item for item in lookup.evidence if item.evidence_id in resolved_ids]
    return EvidenceSelection(corpus, lookup, selected)


def lookup_question(
    session: Session,
    pinned: PinnedRun,
    question: str,
    resolved: ResolvedQuestion,
    history: History,
) -> EvidenceSelection:
    if resolved.clarification_choices:
        corpus = load_reference_corpus(
            session, pinned.release, [], index_kind=pinned.conversation.index_kind
        )
        lookup = LegalSearchResponse(
            data=[],
            count=0,
            outcome="not_found",
            retrieval_mode="exact",
            release_version=pinned.release.version,
            edition_label=corpus.edition_label,
        )
        return EvidenceSelection(corpus, lookup, [])
    assert resolved.parsed is not None
    if resolved.parsed.references or resolved.parsed.error:
        return exact_evidence(session, pinned, question, resolved, history)
    profile = session.get(EmbeddingProfile, pinned.build.profile_id)
    if profile is None:
        raise PgVectorRetrievalError("Pinned search profile is unavailable")
    lookup = semantic_lookup(
        session,
        pinned.release,
        profile=profile,
        embedding_run_id=pinned.build.embedding_run_id,
        query=resolved.semantic_query,
        top_k=6,
        index_kind=pinned.conversation.index_kind,
        embedding_provider=default_embedding_provider,
    )
    selected = lookup.evidence
    corpus = load_ranked_corpus(
        session,
        pinned.release,
        [item.provision_version_id for item in selected],
        index_kind=pinned.conversation.index_kind,
    )
    return EvidenceSelection(corpus, lookup, selected)


def covered_laws_for_release(
    session: Session, release_id: uuid.UUID, index_kind: str
) -> tuple[list[dict[str, str]], set[str]]:
    available_instruments = release_instruments(
        session, release_id, index_kind=index_kind
    )
    available_slugs = {instrument.slug for instrument in available_instruments.values()}
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
    return covered_laws, available_slugs


def pack_evidence(
    session: Session,
    pinned: PinnedRun,
    question: str,
    history: History,
    resolved: ResolvedQuestion,
    selection: EvidenceSelection,
) -> Prepared:
    corpus, lookup, selected = selection.corpus, selection.lookup, selection.selected
    context = expand_context(session, corpus, selected) if selected else []
    for index, item in enumerate(context, start=len(lookup.evidence) + 1):
        item.evidence_id = f"E{index}"
    all_evidence = [*lookup.evidence, *context]
    prompt_evidence = prompt_items([*selected, *context])
    covered_laws, available_slugs = covered_laws_for_release(
        session, pinned.release.id, corpus.index_kind
    )
    selected, context, prompt_evidence, prompt_bytes = fit_prompt(
        selected,
        context,
        {
            "question": question,
            "previous_question": resolved.previous_question,
            "conversation_context": history.context,
            "covered_laws": covered_laws,
        },
        settings.CHAT_EVIDENCE_MAX_CHARS,
    )
    all_evidence = [*lookup.evidence, *context]
    return Prepared(
        run_id=pinned.run.id,
        conversation_id=pinned.conversation.id,
        release_id=pinned.release.id,
        question=question,
        previous_question=resolved.previous_question,
        lookup=lookup,
        selected=selected,
        all_evidence=all_evidence,
        prompt_evidence=prompt_evidence,
        too_large=prompt_bytes > settings.CHAT_EVIDENCE_MAX_CHARS,
        conversation_context=history.context,
        clarification_choices=resolved.clarification_choices,
        related_laws=related_laws(question, instrument_slugs=available_slugs)
        or (
            related_laws(resolved.previous_question, instrument_slugs=available_slugs)
            if resolved.previous_question
            else []
        ),
        covered_laws=covered_laws,
    )
