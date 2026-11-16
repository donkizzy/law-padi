import asyncio
from uuid import UUID, uuid4

import pytest

from app.chat import runs
from app.chat import runtime as chat_runtime
from app.chat.notices import NOTICE
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings
from app.deployment.render_app import RequestWorker


@pytest.mark.parametrize(
    "disabled_setting", ["CHAT_ENABLED", "CHAT_GENERATION_ENABLED"]
)
def test_render_disabled_answer_includes_localisable_notice_code(
    monkeypatch: pytest.MonkeyPatch, disabled_setting: str
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    monkeypatch.setattr(settings, disabled_setting, False)
    run_id = uuid4()
    pending = [run_id]
    answers: list[ExplanationAnswer] = []
    identities: list[UUID] = []

    def finish(identity: UUID, _worker: str, answer: ExplanationAnswer) -> None:
        identities.append(identity)
        answers.append(answer)

    monkeypatch.setattr(
        runs, "claim_run", lambda *_: pending.pop() if pending else None
    )
    monkeypatch.setattr(runs, "finish", finish)
    monkeypatch.setattr(runs, "recover_expired", lambda: None)
    monkeypatch.setattr(runs, "expire_guest_conversations", lambda: 0)
    monkeypatch.setattr(chat_runtime, "next_lease_delay", lambda: None)

    async def exercise() -> None:
        runtime = RequestWorker()
        runtime.start()
        try:
            async with asyncio.timeout(2):
                while not answers:
                    await asyncio.sleep(0)
        finally:
            await runtime.close()

    asyncio.run(exercise())
    assert identities == [run_id]
    assert len(answers) == 1
    assert answers[0].outcome == "cancelled"
    assert answers[0].notice == NOTICE["disabled"]
    assert answers[0].notice_code == "disabled"
    assert answers[0].notice_params == {}
