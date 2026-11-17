import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from app.chat import drafting, pipeline, runs
from app.chat.budget import BudgetExhausted
from app.chat.evidence_packet import Prepared
from app.chat.llm.protocol import ChatModel, JsonObject, ProviderResult
from app.chat.pipeline_state import RunState, Understood
from app.chat.prompts import explanation
from app.chat.schemas import ExplanationAnswer
from app.languages.codes import Language
from tests.chat.test_generation import FakeProvider, _answer_section_37


def _fail_preparation(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> tuple[list[ExplanationAnswer], list[JsonObject | None], list[JsonObject | None]]:
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
    return answers, validations, diagnostics


@pytest.mark.parametrize(
    ("error", "outcome", "notice"),
    [
        (BudgetExhausted("budget"), "budget_exhausted", "budget"),
        (runs.RunCancelled(), "cancelled", "cancelled"),
        (TimeoutError(), "provider_failure", "unavailable"),
    ],
)
def test_expected_preparation_failures_keep_their_outcomes(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, outcome: str, notice: str
) -> None:
    answers, validations, diagnostics = _fail_preparation(monkeypatch, error)
    asyncio.run(pipeline.process_run(uuid4(), "test-worker"))
    assert len(answers) == 1
    assert answers[0].outcome == outcome
    assert answers[0].notice_code == notice
    assert answers[0].evidence == []
    assert validations == [None]
    assert diagnostics[0] is not None and set(diagnostics[0]) == {"total_ms"}


@pytest.mark.parametrize("error", [ValueError("defect"), TypeError("defect")])
def test_a_defect_is_logged_and_recorded_as_internal_not_as_a_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    answers, validations, _diagnostics = _fail_preparation(monkeypatch, error)
    run_id = uuid4()
    with caplog.at_level(logging.ERROR, logger="app.chat.pipeline"):
        asyncio.run(pipeline.process_run(run_id, "test-worker"))
    assert [answer.outcome for answer in answers] == ["provider_failure"]
    assert answers[0].notice_code == "unavailable"
    assert validations == [
        {"failure_stage": "internal", "error_type": type(error).__name__}
    ]
    [record] = caplog.records
    assert record.getMessage() == f"chat_run_failed run_id={run_id} stage=preparation"
    assert record.exc_info is not None and record.exc_info[1] is error


def test_a_run_deleted_mid_answer_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    answers, _validations, _diagnostics = _fail_preparation(
        monkeypatch, runs.RunNotFound("Generation run was not found")
    )
    with caplog.at_level(logging.INFO, logger="app.chat.pipeline"):
        asyncio.run(pipeline.process_run(uuid4(), "test-worker"))
    assert answers == []
    assert all(record.levelno < logging.ERROR for record in caplog.records)


@pytest.mark.usefixtures("corpus")
def test_a_defect_while_checking_a_draft_is_not_retried_as_a_rejection(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def defect(*_args: Any, **_kwargs: Any) -> dict[int, str]:
        raise ValueError("defect")

    monkeypatch.setattr(drafting, "validate_draft", defect)
    provider = FakeProvider()
    run, message = _answer_section_37(db, monkeypatch, provider)
    assert run.outcome == "provider_failure"
    assert provider.calls == [explanation.TEXT]
    assert message.validation_result is not None
    assert message.validation_result["failure_stage"] == "internal"
    assert message.validation_result["error_type"] == "ValueError"


class MalformedDrafts(FakeProvider):
    async def complete_json(self, **kwargs: Any) -> ProviderResult:
        result = await super().complete_json(**kwargs)
        return ProviderResult(
            value={**result.value, "blocks": "not a list"},
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            model=result.model,
        )


@pytest.mark.usefixtures("corpus")
def test_a_draft_that_twice_breaks_the_schema_is_still_a_validation_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = MalformedDrafts()
    run, message = _answer_section_37(db, monkeypatch, provider)
    assert run.outcome == "validation_failed"
    assert provider.calls == [explanation.TEXT, explanation.TEXT]
    assert provider.payloads[1]["revision_reason"] == (
        "The response did not match the required JSON shape"
    )
    assert message.validation_result is not None
    assert message.validation_result["failure_stage"] == "generation_schema"
    assert message.validation_result["failure_reason"] == "ValidationError"
