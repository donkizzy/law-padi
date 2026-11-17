"""One logging configuration for the API, the chat worker and the ingestion worker.

Production writes one JSON object per line so a log collector can index the
fields; development writes readable text. Every record carries the request,
run and task identifiers bound for the current context, so a reader's request,
the chat run it created and the worker's logs for that run can be joined.

Log messages are operational: identifiers, counts, outcomes and error types.
Never pass secrets, email addresses or a reader's question text to a logger.
"""

import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Literal

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)

CONTEXT_FIELDS: dict[str, ContextVar[str | None]] = {
    "request_id": request_id_var,
    "run_id": run_id_var,
    "task_id": task_id_var,
}

# Attributes every LogRecord has; anything else on a record came from `extra=`.
_RECORD_ATTRIBUTES = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}

_HANDLER_NAME = "app.core.logs"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REDACTED_EMAIL = "[email]"


@contextmanager
def log_context(**fields: object) -> Iterator[None]:
    """Bind request_id, run_id or task_id to every record logged inside."""
    tokens = []
    for name, value in fields.items():
        var = CONTEXT_FIELDS[name]
        tokens.append((var, var.set(None if value is None else str(value))))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class RedactEmailFilter(logging.Filter):
    """Remove email addresses from messages written by code we do not own.

    Uvicorn's access line includes the request path, and password recovery
    puts the address in the path.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _EMAIL.search(message):
            record.msg = _EMAIL.sub(REDACTED_EMAIL, message)
            record.args = None
        return True


class ContextFilter(logging.Filter):
    """Copy the bound identifiers onto the record unless `extra=` set them."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name, var in CONTEXT_FIELDS.items():
            if getattr(record, name, None) is None:
                setattr(record, name, var.get())
        return True


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RECORD_ATTRIBUTES
        and key not in CONTEXT_FIELDS
        and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in CONTEXT_FIELDS:
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = {
            name: getattr(record, name, None)
            for name in CONTEXT_FIELDS
            if getattr(record, name, None) is not None
        }
        fields.update(_extra_fields(record))
        if not fields:
            return line
        suffix = " ".join(f"{key}={value}" for key, value in fields.items())
        head, newline, rest = line.partition("\n")
        return f"{head} {suffix}{newline}{rest}"


def build_handler(log_format: Literal["json", "text"]) -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter() if log_format == "json" else TextFormatter())
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactEmailFilter())
    return handler


def configure_logging(
    *,
    log_format: Literal["json", "text"] | None = None,
    level: str | int | None = None,
) -> None:
    """Install the shared handler on the root logger; safe to call repeatedly.

    Plain stream handlers left by `logging.basicConfig` are replaced so each
    record is written once. Other handlers, such as test capture, are kept.
    Uvicorn's loggers lose their own handlers and propagate here, so server
    errors and access lines use the same format; a logger Uvicorn switched
    off stays off.
    """
    from app.core.config import settings

    root = logging.getLogger()
    for existing in list(root.handlers):
        if (
            existing.get_name() == _HANDLER_NAME
            or type(existing) is logging.StreamHandler
        ):
            root.removeHandler(existing)
    root.addHandler(build_handler(log_format or settings.log_format))
    root.setLevel(level or settings.LOG_LEVEL)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        if not server_logger.handlers and not server_logger.propagate:
            # `uvicorn --no-access-log` disables the access logger this way.
            continue
        server_logger.handlers.clear()
        server_logger.propagate = True
