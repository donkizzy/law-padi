import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlmodel import Session, delete

from app.chat import budget, worker
from app.chat.provider import DeepSeekClient, ProviderError
from app.core.config import settings
from app.core.db import engine, init_db
from app.legal.enums import MessageRole
from app.legal.models import (
    Conversation,
    ConversationMessage,
    GenerationBudgetDay,
    GenerationBudgetMonth,
    GenerationReservation,
    GenerationRun,
)
from tests.conftest import _cleanup_db


@pytest.fixture
def budget_db(db: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    _cleanup_db(db)
    init_db(db)
    monkeypatch.setattr(settings, "CHAT_DAILY_BUDGET_USD", 1.0)
    monkeypatch.setattr(settings, "CHAT_MONTHLY_BUDGET_USD", 1.0)
    monkeypatch.setattr(settings, "AI_MONTHLY_BUDGET_USD", 1.0)
    monkeypatch.setattr(settings, "DEEPSEEK_INPUT_USD_PER_MILLION", 1.0)
    monkeypatch.setattr(settings, "DEEPSEEK_OUTPUT_USD_PER_MILLION", 1.0)
    monkeypatch.setattr(budget, "_lagos_day", lambda: date(2030, 10, 14))
    return db


def _run(db: Session) -> GenerationRun:
    conversation = Conversation(anonymous_session_id=uuid4().hex)
    db.add(conversation)
    db.flush()
    message = ConversationMessage(
        conversation_id=conversation.id, role=MessageRole.USER, content="Section 37"
    )
    db.add(message)
    db.flush()
    run = GenerationRun(
        conversation_id=conversation.id,
        user_message_id=message.id,
        idempotency_key=uuid4().hex,
    )
    db.add(run)
    db.commit()
    return run


def _reserve(db: Session, run_id: UUID) -> GenerationReservation:
    return budget.reserve(
        db,
        run_id=run_id,
        purpose="generation",
        prompt_chars=1000,
        max_output_tokens=1000,
    )


@pytest.mark.parametrize(
    "ceiling", ["CHAT_MONTHLY_BUDGET_USD", "AI_MONTHLY_BUDGET_USD"]
)
def test_monthly_limit_includes_prior_days_and_overall_allowance(
    budget_db: Session, monkeypatch: pytest.MonkeyPatch, ceiling: str
) -> None:
    monkeypatch.setattr(settings, ceiling, 0.003)
    run = _run(budget_db)
    first = _reserve(budget_db, run.id)
    budget_db.commit()
    assert first.reserved_micro_usd == 2000
    monkeypatch.setattr(budget, "_lagos_day", lambda: date(2030, 10, 15))
    with pytest.raises(budget.BudgetExhausted, match="Monthly"):
        _reserve(budget_db, run.id)
    budget_db.rollback()
    monthly = budget_db.get(GenerationBudgetMonth, date(2030, 10, 1))
    assert monthly is not None and monthly.reserved_micro_usd == 2000


def test_parallel_admission_cannot_exceed_monthly_cap(
    budget_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_MONTHLY_BUDGET_USD", 0.003)
    run_ids = [_run(budget_db).id, _run(budget_db).id]
    barrier = Barrier(2)

    def admit(run_id: UUID) -> bool:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                _reserve(session, run_id)
                session.commit()
                return True
            except budget.BudgetExhausted:
                session.rollback()
                return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(admit, run_ids)) == [False, True]
    budget_db.expire_all()
    monthly = budget_db.get(GenerationBudgetMonth, date(2030, 10, 1))
    assert monthly is not None and monthly.reserved_micro_usd == 2000


def test_uncertain_charge_survives_deletion_and_reconciles_once(
    budget_db: Session,
) -> None:
    run = _run(budget_db)
    reservation = _reserve(budget_db, run.id)
    budget_db.commit()
    reservation_id = reservation.id
    budget.settle(budget_db, reservation_id, uncertain=True)
    budget_db.commit()
    budget_db.exec(delete(Conversation).where(Conversation.id == run.conversation_id))
    budget_db.commit()
    budget_db.expire_all()
    retained = budget_db.get(GenerationReservation, reservation_id)
    assert retained is not None and retained.run_id is None

    # An unknown invoice must retain the full held allowance.
    budget.settle(budget_db, reservation_id)
    budget_db.commit()
    monthly = budget_db.get(GenerationBudgetMonth, date(2030, 10, 1))
    assert monthly is not None and monthly.reserved_micro_usd == 2000
    assert retained.status == "uncertain"

    for _ in range(2):
        budget.settle(
            budget_db, reservation_id, prompt_tokens=100, completion_tokens=40
        )
        budget_db.commit()
    assert monthly.reserved_micro_usd == 0
    assert monthly.spent_micro_usd == 140
    assert retained.status == "settled"
    daily = budget_db.get(GenerationBudgetDay, date(2030, 10, 14))
    assert daily is not None and daily.spent_micro_usd == 140


def test_new_month_resets_admission_but_settlement_uses_original_month(
    budget_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_MONTHLY_BUDGET_USD", 0.002)
    run = _run(budget_db)
    monkeypatch.setattr(budget, "_lagos_day", lambda: date(2030, 10, 31))
    october = _reserve(budget_db, run.id)
    budget_db.commit()
    monkeypatch.setattr(budget, "_lagos_day", lambda: date(2030, 11, 1))
    november = _reserve(budget_db, run.id)
    budget_db.commit()
    budget.settle(budget_db, october.id, prompt_tokens=100, completion_tokens=40)
    budget_db.commit()
    original_month = budget_db.get(GenerationBudgetMonth, date(2030, 10, 1))
    current_month = budget_db.get(GenerationBudgetMonth, date(2030, 11, 1))
    assert original_month is not None and original_month.spent_micro_usd == 140
    assert original_month.reserved_micro_usd == 0
    assert current_month is not None and current_month.reserved_micro_usd == 2000
    assert november.day == date(2030, 11, 1)


def test_month_boundary_uses_lagos_time(monkeypatch: pytest.MonkeyPatch) -> None:
    class Clock:
        @staticmethod
        def now(tz: Any) -> datetime:
            return datetime(2030, 10, 31, 23, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(budget, "datetime", Clock)
    assert budget._lagos_day() == date(2030, 11, 1)


def test_uncertain_provider_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    settlements: list[bool] = []

    class UncertainProvider:
        async def complete_json(self, **_kwargs: Any) -> None:
            calls.append("provider")
            raise ProviderError("timeout", retryable=True, uncertain_charge=True)

    monkeypatch.setattr(worker, "_reserve_call", lambda *_args: uuid4())
    monkeypatch.setattr(
        worker,
        "_settle_call",
        lambda *_args, uncertain: settlements.append(uncertain),
    )
    with pytest.raises(ProviderError):
        asyncio.run(
            worker._call(
                UncertainProvider(),  # type: ignore[arg-type]
                uuid4(),
                "generation",
                "system",
                {},
                max_tokens=10,
            )
        )
    assert calls == ["provider"]
    assert settlements == [True]


@pytest.mark.parametrize(
    "response_body",
    [
        {"choices": [{"finish_reason": "length"}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": "bad JSON"}}]},
        {
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            "usage": {"prompt_tokens": -1, "completion_tokens": 1},
        },
    ],
)
def test_invalid_success_response_retains_possible_provider_charge(
    monkeypatch: pytest.MonkeyPatch, response_body: dict[str, Any]
) -> None:
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")

    async def call() -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response_body)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderError) as error:
                await DeepSeekClient(client).complete_json(system="system", payload={})
            assert error.value.uncertain_charge is True

    asyncio.run(call())
