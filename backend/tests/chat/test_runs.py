import asyncio
from uuid import UUID, uuid4

import pytest

from app.chat import runs
from app.chat import runtime as chat_runtime
from app.chat.notices import NOTICE
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings


@pytest.mark.parametrize(
    ("disabled_setting", "value"),
    [("CHAT_GENERATION_ENABLED", False), ("CHAT_GENERATION_KILL_SWITCH", True)],
)
def test_disabled_answer_includes_localisable_notice_code(
    monkeypatch: pytest.MonkeyPatch, disabled_setting: str, value: bool
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    monkeypatch.setattr(settings, disabled_setting, value)
    run_id = uuid4()
    pending = [run_id]
    answers: list[ExplanationAnswer] = []
    identities: list[UUID] = []

    def finish(identity: UUID, _worker: str, answer: ExplanationAnswer) -> None:
        identities.append(identity)
        answers.append(answer)

    async def sleep(_delay: float) -> None:
        pass

    monkeypatch.setattr(
        runs, "claim_run", lambda *_: pending.pop() if pending else None
    )
    monkeypatch.setattr(runs, "finish", finish)
    monkeypatch.setattr(runs, "recover_expired", lambda: None)
    monkeypatch.setattr(runs, "expire_guest_conversations", lambda: 0)
    monkeypatch.setattr(chat_runtime.asyncio, "sleep", sleep)

    async def exercise() -> None:
        await chat_runtime.run_worker("disabled-test", stopping=lambda: bool(answers))

    asyncio.run(exercise())
    assert identities == [run_id]
    assert len(answers) == 1
    assert answers[0].outcome == "cancelled"
    assert answers[0].notice == NOTICE["disabled"]
    assert answers[0].notice_code == "disabled"
    assert answers[0].notice_params == {}
