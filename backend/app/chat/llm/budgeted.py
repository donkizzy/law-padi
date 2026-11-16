"""Reserve, dispatch and settle each durable run's paid completion."""

import asyncio
import json
import uuid

from sqlmodel import Session, select

from app.chat.budget import reserve, settle
from app.chat.llm.protocol import ChatModel, JsonObject, ProviderError, ProviderResult
from app.core.config import settings
from app.core.db import engine
from app.legal.models import GenerationRun, get_datetime_utc


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


def settle_call(
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
            result = await provider.complete_json(
                system=system,
                payload=payload,
                max_tokens=max_tokens,
                thinking=thinking,
            )
        except ProviderError as exc:
            await asyncio.to_thread(
                settle_call, reservation_id, None, uncertain=exc.uncertain_charge
            )
            if exc.retryable and not exc.uncertain_charge and attempt == 0:
                continue
            raise
        except BaseException:
            await asyncio.to_thread(settle_call, reservation_id, None, uncertain=True)
            raise
        await asyncio.to_thread(settle_call, reservation_id, result, uncertain=False)
        return result
    raise ProviderError("DeepSeek request failed")
