import asyncio
from uuid import UUID, uuid4

import pytest

from app.chat import pipeline, runs
from app.chat.budget import BudgetExhausted
from app.chat.evidence_packet import Prepared
from app.chat.llm.protocol import ChatModel, JsonObject
from app.chat.pipeline_state import RunState, Understood
from app.chat.schemas import ExplanationAnswer
from app.languages.codes import Language


@pytest.mark.parametrize(
    ("error", "outcome", "notice"),
    [
        (ValueError("missing run"), "validation_failed", "unverified"),
        (TypeError("unexpected bug"), "provider_failure", "unavailable"),
        (BudgetExhausted("budget"), "budget_exhausted", "budget"),
        (asyncio.CancelledError(), "cancelled", "cancelled"),
        (TimeoutError(), "provider_failure", "unavailable"),
    ],
)
def test_preparation_failures_keep_existing_outcomes_and_diagnostics(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, outcome: str, notice: str
) -> None:
    answers: list[ExplanationAnswer] = []
    validations: list[JsonObject | None] = []
    diagnostics: list[JsonObject | None] = []

    async def understood(
        _provider: ChatModel, _identity: UUID, _state: RunState
    ) -> Understood:
        return Understood(Language.ENGLISH, Language.ENGLISH)

    def prepare(_identity: UUID) -> Prepared:
        raise error

    def finish(
        _identity: UUID,
        _worker: str,
        answer: ExplanationAnswer,
        *,
        validation: JsonObject | None = None,
        telemetry: JsonObject | None = None,
    ) -> None:
        answers.append(answer)
        validations.append(validation)
        diagnostics.append(telemetry)

    monkeypatch.setattr(pipeline, "understand_run", understood)
    monkeypatch.setattr(pipeline, "prepare_run", prepare)
    monkeypatch.setattr(runs, "finish", finish)
    asyncio.run(pipeline.process_run(uuid4(), "test-worker"))
    assert len(answers) == 1
    assert answers[0].outcome == outcome
    assert answers[0].notice_code == notice
    assert answers[0].evidence == []
    assert validations == (
        [
            {
                "deterministic_or_verifier": False,
                "failure_stage": "preparation",
                "failure_reason": "ValueError",
                "expected_verdict_count": None,
                "verifier_verdict_count": None,
            }
        ]
        if isinstance(error, ValueError)
        else [None]
    )
    assert diagnostics[0] is not None and set(diagnostics[0]) == {"total_ms"}
