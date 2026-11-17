from collections.abc import Callable
from typing import cast

from sqlmodel import Session


def check_stage_continue(session: Session) -> None:
    check = cast(Callable[[], None] | None, session.info.get("ingestion_continue"))
    if check:
        check()
