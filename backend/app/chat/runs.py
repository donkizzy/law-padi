"""Public durable run lifecycle: claim, execute, finish, recovery and retention."""

import asyncio
import json
import logging
import uuid
from datetime import timedelta

from sqlmodel import Session, col, delete, select

from app.chat import EXPLANATION_PROMPT_VERSION
from app.chat.events import emit_event
from app.chat.evidence_packet import (
    Prepared,
)
from app.chat.llm.protocol import JsonObject, ProviderResult
from app.chat.notices import notice_fields
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings
from app.core.db import engine
from app.legal.enums import (
    AnswerStatus,
    EvidenceRole,
    MessageRole,
)
from app.legal.models import (
    Conversation,
    ConversationMessage,
    GenerationAdmission,
    GenerationCapacity,
    GenerationReservation,
    GenerationRun,
    MessageEvidence,
    get_datetime_utc,
)

_logger = logging.getLogger("app.chat.worker")


class RunNotFound(LookupError):
    """The run was deleted, with its conversation, after it was claimed."""


class RunCancelled(Exception):
    """The reader stopped the answer, or explanations were switched off.

    Distinct from asyncio.CancelledError, which means the worker itself is
    being stopped.
    """


def claim_run(worker_id: str, *, run_id: uuid.UUID | None = None) -> uuid.UUID | None:
    with Session(engine) as session:
        statement = (
            select(GenerationRun)
            .where(GenerationRun.status == "pending")
            .with_for_update(skip_locked=True)
        )
        if run_id is not None:
            statement = statement.where(GenerationRun.id == run_id)
        else:
            statement = statement.order_by(
                col(GenerationRun.created_at), col(GenerationRun.id)
            )
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


def cancelled(run_id: uuid.UUID) -> bool:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        return (
            run is None
            or run.cancellation_requested
            or settings.CHAT_GENERATION_KILL_SWITCH
        )


def requeue_interrupted(run_id: uuid.UUID, worker_id: str) -> bool:
    """Return a run to the queue when its worker stops before any paid call.

    Returns False when the run must be finished instead: a call may already
    have been charged, it has used its retry, or the reader asked to stop it.
    The rule matches recover_expired, so a graceful stop and a crash agree.
    """
    with Session(engine) as session:
        run = session.exec(
            select(GenerationRun).where(GenerationRun.id == run_id).with_for_update()
        ).first()
        if run is None or run.status != "running" or run.lease_owner != worker_id:
            return True
        if (
            run.provider_started_at is not None
            or run.attempt_count >= 2
            or run.cancellation_requested
        ):
            return False
        run.status = "pending"
        run.lease_owner = None
        run.lease_until = None
        run.updated_at = get_datetime_utc()
        session.add(run)
        session.commit()
        return True


def emit_sources(prepared: Prepared) -> None:
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


def emit_progress(run_id: uuid.UUID, event_type: str) -> None:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        if run and run.status == "running":
            emit_event(session, run, event_type, {"run_id": str(run_id)})
            session.commit()


def answer_message(
    run: GenerationRun,
    answer: ExplanationAnswer,
    provider_result: ProviderResult | None,
    validation: JsonObject | None,
    telemetry: JsonObject | None,
) -> ConversationMessage:
    content = "\n\n".join(block.text for block in answer.blocks)
    return ConversationMessage(
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
        evidence_snapshot=[item.model_dump(mode="json") for item in answer.evidence],
        prompt_version=EXPLANATION_PROMPT_VERSION,
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


def finish(
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
        message = answer_message(run, answer, provider_result, validation, telemetry)
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
        finish(
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


def generation_disabled(*, include_chat_enabled: bool = True) -> bool:
    return (
        (include_chat_enabled and not settings.CHAT_ENABLED)
        or not settings.CHAT_GENERATION_ENABLED
        or settings.CHAT_GENERATION_KILL_SWITCH
    )


async def execute(
    run_id: uuid.UUID, worker_id: str, *, disabled: bool | None = None
) -> None:
    """Execute a claimed run, including the reader-visible disabled outcome."""
    if generation_disabled() if disabled is None else disabled:
        await asyncio.to_thread(
            finish,
            run_id,
            worker_id,
            ExplanationAnswer(outcome="cancelled", **notice_fields("disabled")),
        )
    else:
        from app.chat import pipeline

        await pipeline.process_run(run_id, worker_id)
