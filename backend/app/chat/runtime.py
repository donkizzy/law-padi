"""One driver for periodic standalone work and request-woken deployments."""

import asyncio
import uuid
from collections.abc import Callable

from sqlmodel import Session, col, func, select

from app.chat import runs
from app.core.config import settings
from app.core.db import engine
from app.core.heartbeat import Heartbeat
from app.core.logs import configure_logging
from app.core.sentry import init_sentry
from app.ingestion.embedding import close_embedding_providers
from app.legal.models import GenerationRun, get_datetime_utc

# The standalone loop sleeps at most this long between iterations; the
# container health check measures heartbeat staleness in these intervals.
POLL_INTERVAL_SECONDS = 2


def next_lease_delay() -> float | None:
    """Schedule recovery only for a lease already known to be outstanding."""
    now = get_datetime_utc()
    with Session(engine) as session:
        deadline = session.exec(
            select(func.min(GenerationRun.lease_until)).where(
                GenerationRun.status == "running",
                col(GenerationRun.lease_until) > now,
            )
        ).one()
    return (deadline - now).total_seconds() + 0.1 if deadline else None


async def wait_for_work(wakeup: asyncio.Event | None, delay: float | None) -> None:
    if wakeup is None:
        return
    if delay is None:
        await wakeup.wait()
    else:
        try:
            await asyncio.wait_for(wakeup.wait(), timeout=delay)
        except TimeoutError:
            pass
    wakeup.clear()


async def dispatch(
    worker_id: str,
    active: set[asyncio.Task[None]],
    stopping: Callable[[], bool],
    *,
    request_woken: bool,
    disabled: bool,
) -> None:
    while request_woken or disabled or len(active) < settings.CHAT_WORKER_CONCURRENCY:
        if request_woken and stopping():
            return
        run_id = await asyncio.to_thread(runs.claim_run, worker_id)
        if run_id is None or (request_woken and stopping()):
            return
        if request_woken or disabled:
            await runs.execute(
                run_id, worker_id, disabled=None if request_woken else True
            )
        else:
            task = asyncio.create_task(runs.execute(run_id, worker_id, disabled=False))
            active.add(task)
            task.add_done_callback(active.discard)


async def run_worker(
    worker_id: str,
    *,
    wakeup: asyncio.Event | None = None,
    stopping: Callable[[], bool] = lambda: False,
    heartbeat: Heartbeat | None = None,
) -> None:
    request_woken = wakeup is not None
    delay: float | None = None
    # Run retention on the first pass. The loop clock is monotonic and can be
    # below an hour on a freshly booted host, so 0.0 would skip it.
    last_retention = float("-inf")
    active: set[asyncio.Task[None]] = set()
    try:
        while not stopping():
            if heartbeat is not None:
                heartbeat.beat()
            await wait_for_work(wakeup, delay)
            if request_woken:
                await asyncio.to_thread(runs.recover_expired)
            now = asyncio.get_running_loop().time()
            if now - last_retention >= 3600:
                await asyncio.to_thread(runs.expire_guest_conversations)
                last_retention = now
            if not request_woken:
                await asyncio.to_thread(runs.recover_expired)
            disabled = runs.generation_disabled(include_chat_enabled=request_woken)
            await dispatch(
                worker_id,
                active,
                stopping,
                request_woken=request_woken,
                disabled=disabled,
            )
            if request_woken:
                if stopping():
                    return
                delay = await asyncio.to_thread(next_lease_delay)
            else:
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
