"""Atomic Lagos-day/month reservations for every paid model request.

Each call is priced by its provider; DeepSeek prices are the default.

The monthly generation allowance also cannot exceed the overall AI allowance.
Query embeddings are not priced in this ledger: their provider bills by
inference time, not tokens. They are bounded separately by a daily call count
(QUERY_EMBEDDING_DAILY_LIMIT, enforced in app.legal.evidence).
"""

import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, func, select

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


@dataclass(frozen=True)
class ProviderPricing:
    input_usd_per_million: float
    output_usd_per_million: float

    def micro_usd(self, input_units: int, output_tokens: int) -> int:
        return math.ceil(
            input_units * self.input_usd_per_million
            + output_tokens * self.output_usd_per_million
        )


def deepseek_pricing() -> ProviderPricing:
    return ProviderPricing(
        settings.DEEPSEEK_INPUT_USD_PER_MILLION,
        settings.DEEPSEEK_OUTPUT_USD_PER_MILLION,
    )


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


# Purposes that may only use part of the shared daily budget.
SEARCH_UNDERSTANDING = "search_understanding"


def _purpose_daily_limit_usd(purpose: str) -> float | None:
    if purpose == SEARCH_UNDERSTANDING:
        return settings.SEARCH_TRANSLATION_DAILY_BUDGET_USD
    return None


def _purpose_used_micro_usd(session: Session, day: date, purpose: str) -> int:
    """Held reservations at their reserved amount, settled ones at actual cost."""
    held = col(GenerationReservation.status).in_(("reserved", "uncertain"))
    used = session.exec(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (held, col(GenerationReservation.reserved_micro_usd)),
                        else_=func.coalesce(
                            col(GenerationReservation.actual_micro_usd), 0
                        ),
                    )
                ),
                0,
            )
        ).where(
            GenerationReservation.day == day,
            GenerationReservation.purpose == purpose,
        )
    ).one()
    return int(used)


def reserve(
    session: Session,
    *,
    run_id: uuid.UUID | None,
    purpose: str,
    prompt_chars: int,
    max_output_tokens: int,
    pricing: ProviderPricing | None = None,
) -> GenerationReservation:
    """Use a worst-case input estimate and peak pricing, without cache discounts."""
    day = _lagos_day()
    amount = (pricing or deepseek_pricing()).micro_usd(prompt_chars, max_output_tokens)
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
    purpose_limit = _purpose_daily_limit_usd(purpose)
    # The month lock above serializes this read with every other reservation.
    if purpose_limit is not None and _purpose_used_micro_usd(
        session, day, purpose
    ) + amount > math.floor(purpose_limit * 1_000_000):
        raise BudgetExhausted(f"Daily {purpose} budget is exhausted")
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
    pricing: ProviderPricing | None = None,
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
        (pricing or deepseek_pricing()).micro_usd(prompt_tokens, completion_tokens)
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
