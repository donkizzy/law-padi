"""Atomic Lagos-day/month reservations for every paid DeepSeek request.

The monthly generation allowance also cannot exceed the overall AI allowance.
Query embeddings are disabled for the initial deployment, because metered HF
inference cannot be bounded safely by this token-based provider ledger.
"""

import math
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.config import settings
from app.legal.models import (
    GenerationBudgetDay,
    GenerationBudgetMonth,
    GenerationReservation,
    get_datetime_utc,
)

_LAGOS = ZoneInfo("Africa/Lagos")


class BudgetExhausted(RuntimeError):
    pass


def _lagos_day() -> date:
    return datetime.now(_LAGOS).date()


def _month_ledger(session: Session, month: date) -> GenerationBudgetMonth:
    session.exec(
        insert(GenerationBudgetMonth)
        .values(month=month, reserved_micro_usd=0, spent_micro_usd=0)
        .on_conflict_do_nothing(index_elements=["month"])
    )
    return session.exec(
        select(GenerationBudgetMonth)
        .where(GenerationBudgetMonth.month == month)
        .with_for_update()
    ).one()


def reserve(
    session: Session,
    *,
    run_id: uuid.UUID,
    purpose: str,
    prompt_chars: int,
    max_output_tokens: int,
) -> GenerationReservation:
    """Use a worst-case input estimate and peak pricing, without cache discounts."""
    day = _lagos_day()
    amount = math.ceil(
        prompt_chars * settings.DEEPSEEK_INPUT_USD_PER_MILLION
        + max_output_tokens * settings.DEEPSEEK_OUTPUT_USD_PER_MILLION
    )
    # Every reservation, including those on different days, locks the shared
    # month first. This serializes admission across all API/worker instances.
    month_ledger = _month_ledger(session, day.replace(day=1))
    monthly_limit = min(
        settings.CHAT_MONTHLY_BUDGET_USD, settings.AI_MONTHLY_BUDGET_USD
    )
    if (
        month_ledger.reserved_micro_usd + month_ledger.spent_micro_usd + amount
        > math.floor(monthly_limit * 1_000_000)
    ):
        raise BudgetExhausted("Monthly AI generation budget is exhausted")
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
    month_ledger.reserved_micro_usd += amount
    reservation = GenerationReservation(
        run_id=run_id,
        day=day,
        purpose=purpose,
        reserved_micro_usd=amount,
        created_at=get_datetime_utc(),
    )
    session.add(ledger)
    session.add(month_ledger)
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
    if (prompt_tokens is None) != (completion_tokens is None):
        raise ValueError("Both provider token counts are required for reconciliation")
    if (prompt_tokens is not None and prompt_tokens < 0) or (
        completion_tokens is not None and completion_tokens < 0
    ):
        raise ValueError("Provider token counts cannot be negative")
    reservation = session.exec(
        select(GenerationReservation)
        .where(GenerationReservation.id == reservation_id)
        .with_for_update()
    ).one_or_none()
    if reservation is None or reservation.status not in ("reserved", "uncertain"):
        return
    if uncertain:
        reservation.status = "uncertain"
        session.add(reservation)
        return
    # A timeout or post-dispatch crash may already have been charged. Only
    # confirmed token usage may settle an uncertain reservation; missing usage
    # must never release the held allowance automatically.
    if reservation.status == "uncertain" and prompt_tokens is None:
        return
    month_ledger = _month_ledger(session, reservation.day.replace(day=1))
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
    month_ledger.reserved_micro_usd -= reservation.reserved_micro_usd
    month_ledger.spent_micro_usd += actual
    reservation.actual_micro_usd = actual
    reservation.status = "settled" if prompt_tokens is not None else "released"
    session.add(ledger)
    session.add(month_ledger)
    session.add(reservation)
