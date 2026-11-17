"""Typed understanding, retrieval, grounding and translation stages for a run."""

import asyncio
import logging
import time
import uuid
from typing import Literal

from sqlmodel import Session

from app.chat import runs
from app.chat.budget import BudgetExhausted
from app.chat.drafting import GroundingFailed, generate_answer
from app.chat.evidence_packet import Prepared
from app.chat.history import History
from app.chat.llm.deepseek import DeepSeekClient
from app.chat.llm.protocol import ChatModel, JsonObject, ProviderError, ProviderResult
from app.chat.notices import notice_fields, with_coverage
from app.chat.pipeline_state import RunState, Translated, Understood
from app.chat.preparation import (
    ResolvedQuestion,
    load_pinned_run,
    lookup_question,
    pack_evidence,
    resolve_question,
    selected_evidence,
)
from app.chat.reader import reader_languages, reader_question, translate
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings
from app.core.db import engine
from app.ingestion.pgvector_repository import PgVectorRetrievalError
from app.languages.codes import Language
from app.legal.evidence import message_code
from app.legal.release_scope import release_scope_cache

_logger = logging.getLogger(__name__)


def prepare_run(run_id: uuid.UUID) -> Prepared:
    with Session(engine) as session, release_scope_cache(session):
        pinned = load_pinned_run(session, run_id)
        question = pinned.message.english_text or pinned.message.content
        history = History(session, pinned.conversation.id, pinned.message)
        # Read the bounded conversation window before selecting any evidence.
        _ = history.context
        if pinned.run.selected_provision_version_id is not None:
            selection = selected_evidence(session, pinned)
            resolved = ResolvedQuestion(semantic_query=question)
        else:
            resolved = resolve_question(question, history)
            selection = lookup_question(session, pinned, question, resolved, history)
        return pack_evidence(session, pinned, question, history, resolved, selection)


async def understand_run(
    provider: ChatModel, run_id: uuid.UUID, state: RunState
) -> Understood:
    reader = await asyncio.to_thread(reader_question, run_id)
    question_language, answer_language = await reader_languages(
        provider, run_id, reader, state.telemetry
    )
    return Understood(question_language, answer_language)


async def retrieve_run(run_id: uuid.UUID, state: RunState) -> Prepared:
    prepared = await asyncio.to_thread(prepare_run, run_id)
    state.prepared = prepared
    state.telemetry["retrieval_ms"] = round(
        (time.perf_counter() - state.started) * 1000
    )
    state.telemetry["retrieval_mode"] = prepared.lookup.retrieval_mode
    state.telemetry["retrieval_fallback"] = prepared.lookup.retrieval_mode == "lexical"
    await asyncio.to_thread(runs.emit_sources, prepared)
    return prepared


async def early_answer(
    run_id: uuid.UUID, prepared: Prepared
) -> ExplanationAnswer | None:
    if await asyncio.to_thread(runs.cancelled, run_id):
        return ExplanationAnswer(outcome="cancelled", **notice_fields("cancelled"))
    if prepared.clarification_choices:
        return ExplanationAnswer(
            outcome="clarification_required",
            notice="Which section do you mean: "
            + ", ".join(prepared.clarification_choices)
            + "?",
            notice_code="clarify_section",
            notice_params={"choices": prepared.clarification_choices},
            follow_up_questions=[
                f"Explain {citation}" for citation in prepared.clarification_choices
            ],
        )
    if prepared.too_large:
        return ExplanationAnswer(
            outcome="clarification_required",
            evidence=prepared.all_evidence,
            citation_outcomes=prepared.lookup.citation_outcomes,
            **notice_fields("too_large", prepared),
        )
    if not prepared.selected:
        return ExplanationAnswer(
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
    return None


async def translate_run(
    provider: ChatModel,
    run_id: uuid.UUID,
    answer: ExplanationAnswer,
    understood: Understood,
    state: RunState,
) -> Translated:
    answer.question_language = understood.question_language
    answer.answer_language = understood.answer_language
    if understood.answer_language != Language.ENGLISH and answer.blocks:
        await translate(
            provider,
            run_id,
            answer,
            understood.answer_language,
            state.telemetry,
            timeout_seconds=min(
                60.0,
                max(
                    0.0,
                    settings.CHAT_RUN_TIMEOUT_SECONDS
                    - (time.perf_counter() - state.started)
                    - 5.0,
                ),
            ),
        )
    return Translated(answer)


async def persist_answer(
    run_id: uuid.UUID,
    worker_id: str,
    answer: ExplanationAnswer,
    result: ProviderResult | None,
    state: RunState,
) -> None:
    state.telemetry["total_ms"] = round((time.perf_counter() - state.started) * 1000)
    await asyncio.to_thread(
        runs.finish,
        run_id,
        worker_id,
        answer,
        provider_result=result,
        validation={"deterministic": True, "verifier": True} if answer.blocks else None,
        telemetry=state.telemetry,
    )


async def finish_failure(
    run_id: uuid.UUID,
    worker_id: str,
    state: RunState,
    *,
    outcome: Literal[
        "budget_exhausted", "validation_failed", "cancelled", "provider_failure"
    ],
    notice: str,
    validation: JsonObject | None = None,
) -> None:
    state.telemetry["total_ms"] = round((time.perf_counter() - state.started) * 1000)
    prepared = state.prepared
    answer = ExplanationAnswer(
        outcome=outcome,
        evidence=prepared.all_evidence if prepared and outcome != "cancelled" else [],
        **notice_fields(
            notice,
            # Only the unavailable and unverified notices describe coverage.
            prepared if notice in ("unavailable", "unverified") else None,
        ),
    )
    await asyncio.to_thread(
        runs.finish,
        run_id,
        worker_id,
        answer,
        validation=validation,
        telemetry=state.telemetry,
    )


async def release_interrupted(
    run_id: uuid.UUID, worker_id: str, state: RunState
) -> None:
    """Hand back a run whose worker is stopping, for a deploy or restart.

    A run that has not dispatched a paid call goes back to the queue. One
    that may have been charged is finished as stalled; repeating it could
    pay twice.
    """
    if not await asyncio.to_thread(runs.requeue_interrupted, run_id, worker_id):
        await finish_failure(
            run_id,
            worker_id,
            state,
            outcome="provider_failure",
            notice="stalled",
            validation={"failure_stage": "interrupted"},
        )


async def process_run(
    run_id: uuid.UUID, worker_id: str, provider: ChatModel | None = None
) -> None:
    provider = provider or DeepSeekClient()
    state = RunState(started=time.perf_counter())
    try:
        async with asyncio.timeout(settings.CHAT_RUN_TIMEOUT_SECONDS):
            understood = await understand_run(provider, run_id, state)
            prepared = await retrieve_run(run_id, state)
            answer = await early_answer(run_id, prepared)
            result: ProviderResult | None = None
            if answer is None:
                generated = await generate_answer(provider, run_id, prepared, state)
                answer, result = generated.answer, generated.provider_result
            translated = await translate_run(
                provider, run_id, answer, understood, state
            )
            await persist_answer(run_id, worker_id, translated.answer, result, state)
    except runs.RunNotFound:
        # The conversation was deleted mid-answer; there is nothing to finish.
        _logger.info("chat_run_missing run_id=%s", run_id)
    except BudgetExhausted:
        await finish_failure(
            run_id, worker_id, state, outcome="budget_exhausted", notice="budget"
        )
    except GroundingFailed as exc:
        await finish_failure(
            run_id,
            worker_id,
            state,
            outcome="validation_failed",
            notice="unverified",
            validation={
                "deterministic_or_verifier": False,
                "failure_stage": state.validation_stage.value,
                "failure_reason": exc.reason,
                "expected_verdict_count": state.expected_verdict_count,
                "verifier_verdict_count": state.verifier_verdict_count,
            },
        )
    except runs.RunCancelled:
        await finish_failure(
            run_id, worker_id, state, outcome="cancelled", notice="cancelled"
        )
    except asyncio.CancelledError:
        # The worker is being stopped, not the reader's answer.
        await release_interrupted(run_id, worker_id, state)
        raise
    except (ProviderError, TimeoutError, PgVectorRetrievalError) as exc:
        _logger.warning(
            "chat_run_unavailable run_id=%s error_type=%s",
            run_id,
            type(exc).__name__,
        )
        await finish_failure(
            run_id, worker_id, state, outcome="provider_failure", notice="unavailable"
        )
    except Exception as exc:
        # A defect, not a provider outage: keep the trace and tell the two apart.
        _logger.exception(
            "chat_run_failed run_id=%s stage=%s", run_id, state.validation_stage.value
        )
        await finish_failure(
            run_id,
            worker_id,
            state,
            outcome="provider_failure",
            notice="unavailable",
            validation={"failure_stage": "internal", "error_type": type(exc).__name__},
        )
