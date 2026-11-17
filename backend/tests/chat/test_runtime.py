import asyncio
from uuid import UUID, uuid4

import pytest

from app.chat import runs, runtime
from app.core.config import settings


@pytest.mark.parametrize("disabled", [False, True])
def test_standalone_driver_preserves_polling_and_lifecycle_order(
    monkeypatch: pytest.MonkeyPatch, disabled: bool
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", False)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", not disabled)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    monkeypatch.setattr(settings, "CHAT_WORKER_CONCURRENCY", 2)
    pending = [uuid4(), uuid4()]
    expected = list(pending)
    calls: list[str] = []
    executed: list[tuple[UUID, bool | None]] = []
    stopped = False
    release = asyncio.Event()

    def claim(_identity: str) -> UUID | None:
        calls.append("claim")
        return pending.pop(0) if pending else None

    async def execute(identity: UUID, _worker: str, *, disabled: bool | None) -> None:
        executed.append((identity, disabled))
        if not disabled:
            await release.wait()

    async def sleep(delay: float) -> None:
        nonlocal stopped
        assert delay == (2 if disabled else 0.5)
        stopped = True
        release.set()
        # Permit tasks scheduled by dispatch to finish before the driver exits.
        await original_sleep(0)

    original_sleep = asyncio.sleep
    monkeypatch.setattr(runs, "claim_run", claim)
    monkeypatch.setattr(runs, "execute", execute)
    monkeypatch.setattr(
        runs, "expire_guest_conversations", lambda: calls.append("retention")
    )
    monkeypatch.setattr(runs, "recover_expired", lambda: calls.append("recover"))
    monkeypatch.setattr(runtime.asyncio, "sleep", sleep)
    asyncio.run(runtime.run_worker("test-worker", stopping=lambda: stopped))
    assert calls[:2] == ["retention", "recover"]
    assert executed == [(identity, disabled) for identity in expected]
    assert len(calls) == (5 if disabled else 4)
