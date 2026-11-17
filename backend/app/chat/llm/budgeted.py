"""Reserve, dispatch and settle each durable run's paid completion."""

import asyncio
import json
import uuid

from sqlmodel import Session, select

from app.chat import runs
from app.chat.budget import reserve, settle
from app.chat.llm.protocol import (
    ChatModel,
    JsonObject,
    ProviderError,
    ProviderResult,
    TokenUsage,
)
from app.core.config import settings
from app.core.db import engine
from app.legal.models import GenerationRun, get_datetime_utc

# The pause before the single retry when the provider does not name one.
_RETRY_DELAY_SECONDS = 1.0
# A provider that asks for a longer pause than this has failed the answer.
_MAX_RETRY_DELAY_SECONDS = 10.0
# How often an in-flight call checks whether its run was cancelled.
CANCEL_POLL_SECONDS = 1.0


def reserve_call(
    run_id: uuid.UUID,
    purpose: str,
    system: str,
    payload: JsonObject,
    max_tokens: int,
) -> uuid.UUID:
    with Session(engine) as session:
        run = session.exec(
            select(GenerationRun).where(GenerationRun.id == run_id).with_for_update()
        ).one()
        if run.cancellation_requested or settings.CHAT_GENERATION_KILL_SWITCH:
            raise runs.RunCancelled
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


def settle_call(
    reservation_id: uuid.UUID, usage: TokenUsage | None, *, uncertain: bool
) -> None:
    with Session(engine) as session:
        settle(
            session,
            reservation_id,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            uncertain=uncertain,
        )
        session.commit()


def retry_delay(error: ProviderError) -> float | None:
    """Seconds to wait before retrying, or None when a retry is not safe.

    Only a failure the provider reports as uncharged is retried, so a retry
    can never pay twice for one answer.
    """
    if not error.retryable or error.uncertain_charge:
        return None
    delay = _RETRY_DELAY_SECONDS if error.retry_after is None else error.retry_after
    return delay if delay <= _MAX_RETRY_DELAY_SECONDS else None


async def complete_unless_cancelled(
    provider: ChatModel,
    run_id: uuid.UUID,
    *,
    system: str,
    payload: JsonObject,
    max_tokens: int,
    thinking: bool,
) -> ProviderResult:
    """Await a completion, abandoning it once the run is cancelled.

    The cancel request is a database flag that may be set by another process,
    so it is polled while the call is in flight.
    """
    completion = asyncio.ensure_future(
        provider.complete_json(
            system=system, payload=payload, max_tokens=max_tokens, thinking=thinking
        )
    )
    try:
        while True:
            done, _pending = await asyncio.wait(
                {completion}, timeout=CANCEL_POLL_SECONDS
            )
            if done:
                return completion.result()
            if await asyncio.to_thread(runs.cancelled, run_id):
                raise runs.RunCancelled
    finally:
        if not completion.done():
            completion.cancel()
            await asyncio.gather(completion, return_exceptions=True)


async def call(
    provider: ChatModel,
    run_id: uuid.UUID,
    purpose: str,
    system: str,
    payload: JsonObject,
    *,
    max_tokens: int,
    thinking: bool = False,
) -> ProviderResult:
    for attempt in range(2):
        reservation_id = await asyncio.to_thread(
            reserve_call, run_id, purpose, system, payload, max_tokens
        )
        try:
            result = await complete_unless_cancelled(
                provider,
                run_id,
                system=system,
                payload=payload,
                max_tokens=max_tokens,
                thinking=thinking,
            )
        except ProviderError as exc:
            await asyncio.to_thread(
                settle_call, reservation_id, exc.usage, uncertain=exc.uncertain_charge
            )
            delay = retry_delay(exc) if attempt == 0 else None
            if delay is None:
                raise
            await asyncio.sleep(delay)
            continue
        except BaseException:
            # Cancelled, interrupted or failed after dispatch: it may be charged.
            await asyncio.to_thread(settle_call, reservation_id, None, uncertain=True)
            raise
        await asyncio.to_thread(
            settle_call, reservation_id, result.usage, uncertain=False
        )
        return result
    raise ProviderError("DeepSeek request failed")
