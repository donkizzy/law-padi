from typing import Any

import pytest
import sentry_sdk

from app.core import sentry
from app.core.config import settings
from app.core.sentry import FILTERED, init_sentry, scrub_breadcrumb, scrub_event


def test_scrubbing_drops_bodies_and_filters_personal_fields() -> None:
    event = {
        "request": {
            "url": "https://api.example/api/v1/password-recovery/ada@example.com",
            "data": {"question": "Can my landlord evict me?"},
            "cookies": {"refresh": "secret"},
            "headers": {"Content-Type": "application/json", "Cookie": "x=y"},
        },
        "extra": {
            "email": "ada@example.com",
            "new_password": "hunter2",
            "metrics": {"question": "Can my landlord evict me?", "tokens": 4},
        },
        "exception": {
            "values": [{"value": "Key (email)=(ada@example.com) already exists."}]
        },
        "tags": {"request_id": "abc"},
    }
    scrubbed = scrub_event(event)
    request = scrubbed["request"]
    assert "data" not in request and "cookies" not in request
    assert request["url"].endswith(f"/password-recovery/{FILTERED}")
    assert request["headers"] == {
        "Content-Type": "application/json",
        "Cookie": FILTERED,
    }
    assert scrubbed["extra"]["email"] == FILTERED
    assert scrubbed["extra"]["new_password"] == FILTERED
    assert scrubbed["extra"]["metrics"]["question"] == FILTERED
    assert "ada@example.com" not in str(scrubbed)
    assert scrubbed["tags"] == {"request_id": "abc"}


def test_breadcrumbs_lose_email_addresses() -> None:
    crumb = {"message": "sent mail to ada@example.com", "data": {"email": "x"}}
    assert scrub_breadcrumb(crumb) == {
        "message": f"sent mail to {FILTERED}",
        "data": {"email": FILTERED},
    }


def test_without_a_dsn_sentry_is_never_started(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **kw: calls.append(kw))
    monkeypatch.setattr(settings, "SENTRY_DSN", None)
    monkeypatch.setattr(settings, "FASTAPI_ENV", None)
    assert init_sentry("api") is False
    assert calls == []


def test_sentry_reports_release_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    tags: list[tuple[str, str]] = []
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **kw: calls.append(kw))
    monkeypatch.setattr(sentry.sentry_sdk, "set_tag", lambda k, v: tags.append((k, v)))
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://key@sentry.example/1")
    monkeypatch.setattr(settings, "FASTAPI_ENV", None)
    monkeypatch.setattr(settings, "BUILD_REVISION", "abc123")
    monkeypatch.setattr(settings, "SENTRY_ENVIRONMENT", "staging")
    assert init_sentry("chat-worker") is True
    (options,) = calls
    assert options["release"] == "abc123"
    assert options["environment"] == "staging"
    assert options["send_default_pii"] is False
    assert options["max_request_body_size"] == "never"
    assert options["include_local_variables"] is False
    assert options["before_send"] is scrub_event
    assert tags == [("component", "chat-worker")]


def test_tagged_scope_does_not_leak_tags() -> None:
    before = dict(sentry_sdk.get_isolation_scope()._tags)
    with sentry.tagged_scope(run_id="run-1", request_id=None):
        tags = sentry_sdk.get_isolation_scope()._tags
        assert tags.get("run_id") == "run-1"
        assert tags.get("request_id") == before.get("request_id")
    assert sentry_sdk.get_isolation_scope()._tags == before


def test_requests_do_not_tag_the_shared_scope_without_sentry() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    assert not sentry_sdk.is_initialized()
    before = dict(sentry_sdk.get_isolation_scope()._tags)
    with TestClient(app) as client:
        client.get("/livez", headers={"X-Request-ID": "no-leak"})
    assert sentry_sdk.get_isolation_scope()._tags == before
