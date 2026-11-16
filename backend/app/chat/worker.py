"""Dedicated durable chat worker. Run with python -m app.chat.worker."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlmodel import Session, col, delete, select

from app.chat import EXPLANATION_PROMPT_VERSION
from app.chat.budget import BudgetExhausted
from app.chat.events import emit_event
from app.chat.evidence_packet import (
    Prepared,
    edition_notice,
    expand_context,
    fit_prompt,
    prompt_items,
    shown_evidence,
)
from app.chat.history import (
    History,
    is_followup_question,
    is_relative_reference,
    prior_citations,
    prior_section_path,
    relative_query,
)
from app.chat.llm import budgeted
from app.chat.llm.deepseek import DeepSeekClient
from app.chat.llm.protocol import ChatModel, JsonObject, ProviderError, ProviderResult
from app.chat.notices import notice_fields, with_coverage
from app.chat.prompts import explanation, verifier
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
    MessageRole,
)
from app.legal.evidence import (
    default_embedding_provider,
    evidence_item,
    exact_lookup,
    message_code,
    semantic_lookup,
)
from app.legal.instruments import instrument_label
from app.legal.models import (
    Conversation,
    ConversationMessage,
    CorpusRelease,
    EmbeddingProfile,
    GenerationAdmission,
    GenerationCapacity,
    GenerationReservation,
    GenerationRun,
    MessageEvidence,
    ProvisionVersion,
    RetrievalIndexBuild,
    get_datetime_utc,
)
from app.legal.public_corpus import (
    load_ranked_corpus,
    load_reference_corpus,
)
from app.legal.references import (
    CONSTITUTION_SLUG,
    parse_section_reference,
)
from app.legal.release_scope import release_instruments
from app.legal.schemas import CitationOutcome, LegalSearchResponse
from app.legal.topics import related_laws

_PROMPT_VERSION = EXPLANATION_PROMPT_VERSION
_DRAFT_ATTEMPTS = 2
_logger = logging.getLogger(__name__)


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
        history = History(session, conversation.id, question_message)
        conversation_context = history.context
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
                is_followup = is_followup_question(question)
                if is_followup:
                    previous_question = history.previous_question
                    relative = relative_query(
                        session, conversation.id, question, history
                    )
                    if relative:
                        parsed = parse_section_reference(relative)
                    elif previous_question:
                        references = prior_citations(session, conversation.id, history)
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
                        if len(sections) > 1 and is_relative_reference(question):
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
                    prior_path = prior_section_path(session, conversation.id, history)
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
        context = expand_context(session, corpus, selected) if selected else []
        for index, item in enumerate(context, start=len(lookup.evidence) + 1):
            item.evidence_id = f"E{index}"
        all_evidence = [*lookup.evidence, *context]
        prompt_evidence = prompt_items([*selected, *context])
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
        selected, context, prompt_evidence, prompt_bytes = fit_prompt(
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


def _finish(
    run_id: uuid.UUID,
    worker_id: str,
    answer: ExplanationAnswer,
    *,
    provider_result: ProviderResult | None = None,
    validation: JsonObject | None = None,
    telemetry: JsonObject | None = None,
) -> None:
    with Session(engine) as session:
        run = session.exec(
            select(GenerationRun).where(GenerationRun.id == run_id).with_for_update()
        ).first()
        if run is None or run.status != "running" or run.lease_owner != worker_id:
            return
        if run.cancellation_requested or settings.CHAT_GENERATION_KILL_SWITCH:
            answer = ExplanationAnswer(
                outcome="cancelled", **notice_fields("cancelled")
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
    provider: ChatModel,
    run_id: uuid.UUID,
    reader: ReaderQuestion,
    telemetry: JsonObject,
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
                purpose: str, system: str, payload: JsonObject, max_tokens: int
            ) -> ProviderResult:
                return await budgeted.call(
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
    provider: ChatModel,
    run_id: uuid.UUID,
    answer: ExplanationAnswer,
    language: Language,
    telemetry: JsonObject,
    *,
    timeout_seconds: float = 60.0,
) -> None:
    """Attach a checked translation; on any failure the English answer stands."""

    async def call(
        purpose: str, system: str, payload: JsonObject, max_tokens: int
    ) -> ProviderResult:
        return await budgeted.call(
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
    run_id: uuid.UUID, worker_id: str, provider: ChatModel | None = None
) -> None:
    provider = provider or DeepSeekClient()
    started = time.perf_counter()
    telemetry: JsonObject = {}
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
                    outcome="cancelled", **notice_fields("cancelled")
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
                    **notice_fields("too_large", prepared),
                )
            elif not prepared.selected:
                answer = ExplanationAnswer(
                    outcome="insufficient_evidence",
                    evidence=prepared.all_evidence,
                    citation_outcomes=prepared.lookup.citation_outcomes,
                    related_laws=prepared.related_laws,
                    **(
                        {
                            **notice_fields("no_match", prepared),
                            "notice": with_coverage(prepared.lookup.message, prepared),
                            "notice_code": message_code(prepared.lookup.message),
                        }
                        if prepared.lookup.message
                        else notice_fields("no_match", prepared)
                    ),
                )
            else:
                payload: JsonObject = {
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
                        provider_result = await budgeted.call(
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
                                **notice_fields("not_covered", prepared),
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
                        verdict = await budgeted.call(
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
                    edition = edition_notice(
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
                        evidence=shown_evidence(prepared, cited_ids),
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
                **notice_fields("budget"),
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
                **notice_fields("unverified", prepared),
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
            ExplanationAnswer(outcome="cancelled", **notice_fields("cancelled")),
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
                **notice_fields("unavailable", prepared),
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
                **notice_fields("unavailable", prepared),
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
                **notice_fields("stalled"),
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
                        **notice_fields("disabled"),
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
