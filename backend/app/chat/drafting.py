"""Draft, deterministic grounding, verification and the bounded rewrite stage."""

import asyncio
import time
import uuid
from dataclasses import dataclass

from app.chat import runs
from app.chat.evidence_packet import Prepared, edition_notice, shown_evidence
from app.chat.llm import budgeted
from app.chat.llm.protocol import ChatModel, JsonObject, ProviderResult
from app.chat.notices import notice_fields
from app.chat.pipeline_state import Generated, RunState, ValidationStage
from app.chat.prompts import explanation, verifier
from app.chat.schemas import ExplanationAnswer, ExplanationDraft
from app.chat.validation import (
    EvidenceValidationError,
    validate_draft,
    validate_verifier,
)
from app.core.config import settings
from app.legal.schemas import EvidenceItem

_DRAFT_ATTEMPTS = 2


@dataclass(frozen=True)
class Drafted:
    draft: ExplanationDraft
    follow_ups: list[str]
    result: ProviderResult


@dataclass(frozen=True)
class CheckedDraft:
    drafted: Drafted
    dropped: dict[int, str]


@dataclass(frozen=True)
class Verified:
    checked: CheckedDraft
    rejected: set[int]
    started: float


def generation_payload(prepared: Prepared) -> JsonObject:
    return {
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


async def draft_answer(
    provider: ChatModel,
    run_id: uuid.UUID,
    payload: JsonObject,
    state: RunState,
    started: float,
) -> Drafted:
    state.validation_stage = ValidationStage.GENERATION
    result = await budgeted.call(
        provider,
        run_id,
        "generation",
        explanation.TEXT,
        payload,
        max_tokens=settings.DEEPSEEK_GENERATION_MAX_OUTPUT_TOKENS,
        thinking=settings.DEEPSEEK_GENERATION_THINKING,
    )
    state.add_usage(result)
    state.telemetry["generation_ms"] = round((time.perf_counter() - started) * 1000)
    state.validation_stage = ValidationStage.GENERATION_SCHEMA
    draft = ExplanationDraft.model_validate(result.value)
    state.telemetry["direct_answer"] = draft.direct_answer
    follow_ups = [
        question.strip()
        for question in draft.follow_up_questions[:3]
        if question.strip()
    ]
    return Drafted(draft, follow_ups, result)


async def check_draft(
    run_id: uuid.UUID,
    drafted: Drafted,
    prepared: Prepared,
    allowed_evidence: list[EvidenceItem],
    state: RunState,
) -> CheckedDraft:
    state.validation_stage = ValidationStage.DETERMINISTIC
    dropped = validate_draft(
        drafted.draft,
        allowed_evidence,
        release_id=prepared.release_id,
        question=prepared.question,
    )
    if await asyncio.to_thread(runs.cancelled, run_id):
        raise asyncio.CancelledError
    return CheckedDraft(drafted, dropped)


async def verify_answer(
    provider: ChatModel,
    run_id: uuid.UUID,
    checked: CheckedDraft,
    prepared: Prepared,
    state: RunState,
) -> Verified:
    draft = checked.drafted.draft
    await asyncio.to_thread(runs.emit_progress, run_id, "verification.started")
    started = time.perf_counter()
    state.expected_verdict_count = len(draft.blocks)
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
    state.add_usage(verdict)
    state.validation_stage = ValidationStage.VERIFICATION
    verdict_rows = verdict.value.get("verdicts")
    state.verifier_verdict_count = (
        len(verdict_rows) if isinstance(verdict_rows, list) else None
    )
    rejected = validate_verifier(verdict.value, block_count=len(draft.blocks))
    return Verified(checked, rejected, started)


def unsupported_answer(prepared: Prepared, drafted: Drafted) -> ExplanationAnswer:
    return ExplanationAnswer(
        outcome="insufficient_evidence",
        follow_up_questions=drafted.follow_ups,
        citation_outcomes=prepared.lookup.citation_outcomes,
        evidence=prepared.all_evidence,
        related_laws=prepared.related_laws,
        **notice_fields("not_covered", prepared),
    )


def verified_answer(
    prepared: Prepared, verified: Verified, state: RunState, attempt: int
) -> ExplanationAnswer:
    state.telemetry["verification_ms"] = round(
        (time.perf_counter() - verified.started) * 1000
    )
    state.telemetry["draft_attempts"] = attempt + 1
    dropped = verified.checked.dropped
    removed = set(dropped) | verified.rejected
    state.telemetry["removed_blocks"] = len(removed)
    if dropped:
        state.telemetry["removed_block_reasons"] = sorted(set(dropped.values()))
    drafted = verified.checked.drafted
    draft = drafted.draft
    kept_blocks = [
        block for index, block in enumerate(draft.blocks) if index not in removed
    ]
    cited_ids = {
        identifier for block in kept_blocks for identifier in block.evidence_ids
    }
    edition = edition_notice(
        [item for item in prepared.all_evidence if item.evidence_id in cited_ids]
    )
    return ExplanationAnswer(
        outcome="partial_evidence"
        if any(row.status != "resolved" for row in prepared.lookup.citation_outcomes)
        else "completed",
        blocks=kept_blocks,
        missing_facts=draft.missing_facts[:4],
        follow_up_questions=drafted.follow_ups,
        citation_outcomes=prepared.lookup.citation_outcomes,
        evidence=shown_evidence(prepared, cited_ids),
        related_laws=prepared.related_laws,
        notice=edition,
        notice_code="edition" if edition else None,
    )


async def generate_answer(
    provider: ChatModel, run_id: uuid.UUID, prepared: Prepared, state: RunState
) -> Generated:
    payload = generation_payload(prepared)
    allowed_ids = {str(item["id"]) for item in prepared.prompt_evidence}
    allowed_evidence = [
        item for item in prepared.all_evidence if item.evidence_id in allowed_ids
    ]
    await asyncio.to_thread(runs.emit_progress, run_id, "generation.started")
    started = time.perf_counter()
    answer: ExplanationAnswer | None = None
    # A rejected draft gets one rewrite with the reason; a second rejection fails closed.
    for attempt in range(_DRAFT_ATTEMPTS):
        try:
            drafted = await draft_answer(provider, run_id, payload, state, started)
            if not drafted.draft.blocks:
                answer = unsupported_answer(prepared, drafted)
                break
            checked = await check_draft(
                run_id, drafted, prepared, allowed_evidence, state
            )
            verified = await verify_answer(provider, run_id, checked, prepared, state)
        except (EvidenceValidationError, ValueError) as exc:
            if attempt + 1 >= _DRAFT_ATTEMPTS:
                raise
            reason = (
                str(exc)
                if isinstance(exc, EvidenceValidationError)
                else "The response did not match the required JSON shape"
            )
            state.telemetry["revision_reason"] = reason
            payload = {**payload, "revision_reason": reason}
            continue
        answer = verified_answer(prepared, verified, state, attempt)
        break
    assert answer is not None
    result = ProviderResult(
        value=drafted.result.value,
        prompt_tokens=state.prompt_tokens,
        completion_tokens=state.completion_tokens,
        model=drafted.result.model,
    )
    return Generated(answer, result)
