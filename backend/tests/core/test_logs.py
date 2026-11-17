import json
import logging
import sys

import pytest

from app.core import logs
from app.core.logs import (
    ContextFilter,
    JsonFormatter,
    TextFormatter,
    configure_logging,
    log_context,
)


def _record(message: str = "chat_run_finished", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        "app.chat.worker", logging.INFO, __file__, 1, message, None, None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    ContextFilter().filter(record)
    return record


def test_json_lines_carry_standard_and_bound_fields() -> None:
    with log_context(request_id="req-1", run_id="run-1"):
        record = _record(metrics={"outcome": "completed"})
    line = json.loads(JsonFormatter().format(record))
    assert line["level"] == "INFO"
    assert line["logger"] == "app.chat.worker"
    assert line["message"] == "chat_run_finished"
    assert line["request_id"] == "req-1"
    assert line["run_id"] == "run-1"
    assert "task_id" not in line
    assert line["metrics"] == {"outcome": "completed"}
    assert line["timestamp"].endswith("+00:00")


def test_explicit_fields_win_over_the_bound_context() -> None:
    with log_context(task_id="bound"):
        record = _record(task_id="explicit")
    assert json.loads(JsonFormatter().format(record))["task_id"] == "explicit"


def test_context_is_restored_when_the_block_exits() -> None:
    with log_context(request_id="outer"):
        with log_context(request_id="inner", run_id="run"):
            assert logs.request_id_var.get() == "inner"
        assert logs.request_id_var.get() == "outer"
        assert logs.run_id_var.get() is None
    assert logs.request_id_var.get() is None


def test_exceptions_are_kept_in_one_json_line() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            "app", logging.ERROR, __file__, 1, "failed", None, sys.exc_info()
        )
    formatted = JsonFormatter().format(record)
    assert "\n" not in formatted
    assert "ValueError: boom" in json.loads(formatted)["exception"]


def test_text_lines_append_fields_after_the_message() -> None:
    with log_context(request_id="req-2"):
        record = _record("processed ingestion task", stage="pages")
    line = TextFormatter().format(record)
    assert line.endswith(
        "INFO app.chat.worker processed ingestion task request_id=req-2 stage=pages"
    )


def test_configure_logging_replaces_basic_config_and_keeps_other_handlers() -> None:
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    basic = logging.StreamHandler()
    capture = logging.NullHandler()
    uvicorn_handler = logging.StreamHandler()
    logging.getLogger("uvicorn.error").addHandler(uvicorn_handler)
    root.addHandler(basic)
    root.addHandler(capture)
    try:
        configure_logging(log_format="json", level="WARNING")
        configure_logging(log_format="json", level="WARNING")
        ours = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
        assert len(ours) == 1
        assert basic not in root.handlers
        assert capture in root.handlers
        assert root.level == logging.WARNING
        server = logging.getLogger("uvicorn.error")
        assert server.handlers == [] and server.propagate
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


@pytest.mark.parametrize(
    ("env", "configured", "expected"),
    [("development", None, "text"), (None, None, "json"), (None, "text", "text")],
)
def test_log_format_follows_settings(
    monkeypatch: pytest.MonkeyPatch,
    env: str | None,
    configured: str | None,
    expected: str,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "FASTAPI_ENV", env)
    monkeypatch.setattr(settings, "LOG_FORMAT", configured)
    assert settings.log_format == expected


def test_handler_redacts_email_addresses_from_access_lines() -> None:
    import io

    from app.core.logs import REDACTED_EMAIL, build_handler

    handler = build_handler("json")
    stream = io.StringIO()
    handler.setStream(stream)  # type: ignore[attr-defined]
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "127.0.0.1:5000",
            "POST",
            "/api/v1/password-recovery/ada@example.com",
            "1.1",
            200,
        ),
        None,
    )
    handler.handle(record)
    line = json.loads(stream.getvalue())
    assert "ada@example.com" not in stream.getvalue()
    assert line["message"].endswith(
        f'/password-recovery/{REDACTED_EMAIL} HTTP/1.1" 200'
    )


def test_configure_logging_keeps_a_disabled_access_log_off() -> None:
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    access = logging.getLogger("uvicorn.access")
    saved_access = (list(access.handlers), access.propagate)
    # What `uvicorn --no-access-log` leaves behind.
    access.handlers.clear()
    access.propagate = False
    try:
        configure_logging(log_format="json")
        assert access.handlers == [] and access.propagate is False
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        access.handlers[:], access.propagate = saved_access
