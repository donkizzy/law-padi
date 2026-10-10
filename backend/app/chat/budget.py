"""Atomic Lagos-day reservations for every DeepSeek request."""

import math
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.config import settings
from app.legal.models import (
    GenerationBudgetDay,
    GenerationReservation,
    get_datetime_utc,
)

_LAGOS = ZoneInfo("Africa/Lagos")


class BudgetExhausted(RuntimeError):
    pass


def reserve(
    session: Session,
    *,
    run_id: uuid.UUID,
    purpose: str,
    prompt_chars: int,
    max_output_tokens: int,
) -> GenerationReservation:
    """Use a worst-case input estimate and peak pricing, without cache discounts."""
    day = datetime.now(_LAGOS).date()
    amount = math.ceil(
        prompt_chars * settings.DEEPSEEK_INPUT_USD_PER_MILLION
        + max_output_tokens * settings.DEEPSEEK_OUTPUT_USD_PER_MILLION
    )
    session.exec(
        insert(GenerationBudgetDay)
        .values(day=day, reserved_micro_usd=0, spent_micro_usd=0)
        .on_conflict_do_nothing(index_elements=["day"])
    )
    ledger = session.exec(
        select(GenerationBudgetDay)
        .where(GenerationBudgetDay.day == day)
        .with_for_update()
    ).one()
    if ledger.reserved_micro_usd + ledger.spent_micro_usd + amount > math.floor(
        settings.CHAT_DAILY_BUDGET_USD * 1_000_000
    ):
        raise BudgetExhausted("Daily generation budget is exhausted")
    ledger.reserved_micro_usd += amount
    reservation = GenerationReservation(
        run_id=run_id,
        day=day,
        purpose=purpose,
        reserved_micro_usd=amount,
        created_at=get_datetime_utc(),
    )
    session.add(ledger)
    session.add(reservation)
    session.flush()
    return reservation


def settle(
    session: Session,
    reservation_id: uuid.UUID,
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    uncertain: bool = False,
) -> None:
    reservation = session.get(GenerationReservation, reservation_id)
    if reservation is None or reservation.status != "reserved":
        return
    if uncertain:
        reservation.status = "uncertain"
        session.add(reservation)
        return
    ledger = session.exec(
        select(GenerationBudgetDay)
        .where(GenerationBudgetDay.day == reservation.day)
        .with_for_update()
    ).one()
    actual = (
        math.ceil(
            prompt_tokens * settings.DEEPSEEK_INPUT_USD_PER_MILLION
            + completion_tokens * settings.DEEPSEEK_OUTPUT_USD_PER_MILLION
        )
        if prompt_tokens is not None and completion_tokens is not None
        else 0
    )
    ledger.reserved_micro_usd -= reservation.reserved_micro_usd
    ledger.spent_micro_usd += actual
    reservation.actual_micro_usd = actual
    reservation.status = "settled" if prompt_tokens is not None else "released"
    session.add(ledger)
    session.add(reservation)
