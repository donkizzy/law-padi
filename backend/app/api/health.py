"""Liveness and readiness probes, served outside the versioned API.

- `/livez` answers from memory: the process is up and serving requests.
- `/readyz` also proves the database answers within a short timeout and that
  its schema is at this build's Alembic head.
- `/healthz` is the same probe as `/livez`. Render's `healthCheckPath` uses it,
  and a failing Render health check restarts the service or blocks a deploy.
  A restart cannot fix a database outage or a pending migration, and probing
  the database would wake a suspended Neon database on every check, so the
  platform probe must not depend on the database. Readiness is for operators
  and for routers that can hold traffic back, such as Traefik under Compose.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import app
from app.core.db import engine

READINESS_TIMEOUT_SECONDS = 3.0
_NO_STORE = {"Cache-Control": "no-store"}
_logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"], include_in_schema=False)


@lru_cache(maxsize=1)
def migration_heads() -> frozenset[str]:
    """Alembic heads shipped with this build; read from disk once."""
    script = ScriptDirectory(str(Path(app.__file__).parent / "alembic"))
    return frozenset(script.get_heads())


class _SchemaState:
    # Migrations only move forward and a new build means a new process, so once
    # this process has seen the database at its head it need not ask again.
    at_head = False


def reset_schema_cache() -> None:
    _SchemaState.at_head = False
    migration_heads.cache_clear()


def readiness_failure() -> str | None:
    """Return why the service is not ready, or None when it is."""
    timeout_ms = int(READINESS_TIMEOUT_SECONDS * 1000)
    try:
        with engine.connect() as connection:
            connection.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            connection.execute(text("SELECT 1"))
            if not _SchemaState.at_head:
                versions = frozenset(
                    connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalars()
                )
                if versions != migration_heads():
                    return "migrations_pending"
                _SchemaState.at_head = True
    except SQLAlchemyError as exc:
        _logger.warning(
            "readiness_database_error", extra={"error_type": type(exc).__name__}
        )
        return "database_unavailable"
    return None


def _probe(status: str, status_code: int = 200, **fields: str) -> JSONResponse:
    return JSONResponse(
        {"status": status, **fields}, status_code=status_code, headers=_NO_STORE
    )


@router.get("/livez")
@router.get("/healthz")
async def livez() -> JSONResponse:
    return _probe("ok")


@router.get("/readyz")
async def readyz() -> JSONResponse:
    try:
        failure = await asyncio.wait_for(
            asyncio.to_thread(readiness_failure), timeout=READINESS_TIMEOUT_SECONDS
        )
    except TimeoutError:
        _logger.warning("readiness_database_timeout")
        failure = "database_timeout"
    if failure is not None:
        return _probe("unavailable", 503, reason=failure)
    return _probe("ok")
