from collections.abc import Callable
from typing import cast

from sqlmodel import Session


def check_stage_continue(session: Session) -> None:
    """Stop at a checkpoint when asked, and record that the stage progressed."""
    beat = cast(Callable[[], None] | None, session.info.get("ingestion_heartbeat"))
    if beat:
        beat()
    check = cast(Callable[[], None] | None, session.info.get("ingestion_continue"))
    if check:
        check()
