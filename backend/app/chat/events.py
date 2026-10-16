"""Persist events before notifying listeners; IDs support replay."""

import asyncio
import uuid
from collections import defaultdict

import psycopg
from sqlmodel import Session, func, select

from app.core.config import settings
from app.legal.models import GenerationEvent, GenerationRun

_listeners: dict[uuid.UUID, set[asyncio.Event]] = defaultdict(set)
_listener_task: asyncio.Task[None] | None = None


def emit_event(
    session: Session, run: GenerationRun, event_type: str, payload: dict[str, object]
) -> None:
    session.add(
        GenerationEvent(
            conversation_id=run.conversation_id,
            run_id=run.id,
            event_type=event_type,
            payload=payload,
        )
    )
    session.flush()
    session.exec(select(func.pg_notify("chat_events", str(run.conversation_id))))


async def _listen() -> None:
    dsn = str(settings.DATABASE_LISTENER_URL or settings.DATABASE_URL).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(
                dsn, autocommit=True
            ) as connection:
                await connection.execute("LISTEN chat_events")
                async for notice in connection.notifies():
                    try:
                        conversation_id = uuid.UUID(notice.payload)
                    except ValueError:
                        continue
                    for event in tuple(_listeners.get(conversation_id, ())):
                        event.set()
        except psycopg.Error, OSError:
            await asyncio.sleep(1)


def subscribe(conversation_id: uuid.UUID) -> asyncio.Event:
    global _listener_task
    if _listener_task is None or _listener_task.done():
        _listener_task = asyncio.create_task(_listen())
    event = asyncio.Event()
    _listeners[conversation_id].add(event)
    return event


def unsubscribe(conversation_id: uuid.UUID, event: asyncio.Event) -> None:
    global _listener_task
    _listeners[conversation_id].discard(event)
    if not _listeners[conversation_id]:
        _listeners.pop(conversation_id, None)
    if not _listeners and _listener_task is not None:
        _listener_task.cancel()
        _listener_task = None
