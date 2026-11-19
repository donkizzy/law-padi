"""The chat worker loop, run by python -m app.chat.worker."""

import asyncio
import uuid
from collections.abc import Callable

from app.chat import runs
from app.core.config import settings
from app.core.heartbeat import Heartbeat
from app.core.logs import configure_logging
from app.core.sentry import init_sentry
from app.ingestion.embedding import close_embedding_providers

# The standalone loop sleeps at most this long between iterations; the
# container health check measures heartbeat staleness in these intervals.
POLL_INTERVAL_SECONDS = 2


async def dispatch(
    worker_id: str, active: set[asyncio.Task[None]], *, disabled: bool
) -> None:
    while disabled or len(active) < settings.CHAT_WORKER_CONCURRENCY:
        run_id = await asyncio.to_thread(runs.claim_run, worker_id)
        if run_id is None:
            return
        if disabled:
            await runs.execute(run_id, worker_id, disabled=True)
        else:
            task = asyncio.create_task(runs.execute(run_id, worker_id, disabled=False))
            active.add(task)
            task.add_done_callback(active.discard)


async def run_worker(
    worker_id: str,
    *,
    stopping: Callable[[], bool] = lambda: False,
    heartbeat: Heartbeat | None = None,
) -> None:
    # Run retention on the first pass. The loop clock is monotonic and can be
    # below an hour on a freshly booted host, so 0.0 would skip it.
    last_retention = float("-inf")
    active: set[asyncio.Task[None]] = set()
    try:
        while not stopping():
            if heartbeat is not None:
                heartbeat.beat()
            now = asyncio.get_running_loop().time()
            if now - last_retention >= 3600:
                await asyncio.to_thread(runs.expire_guest_conversations)
                last_retention = now
            await asyncio.to_thread(runs.recover_expired)
            # The API refuses new questions while CHAT_ENABLED is off, so the
            # worker only checks the generation switches.
            disabled = runs.generation_disabled(include_chat_enabled=False)
            await dispatch(worker_id, active, disabled=disabled)
            await asyncio.sleep(POLL_INTERVAL_SECONDS if disabled else 0.5)
    finally:
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        await asyncio.to_thread(close_embedding_providers)


async def run_forever() -> None:
    configure_logging()
    init_sentry("chat-worker")
    await run_worker(
        str(uuid.uuid4()),
        heartbeat=Heartbeat(settings.CHAT_WORKER_HEARTBEAT_FILE),
    )
