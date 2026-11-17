import logging
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.request_id import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    accept_request_id,
)
from tests.utils.logs import captured_logs

API = settings.API_V1_STR


@pytest.mark.parametrize(
    "inbound",
    ["abc", "0f8fad5b-d9cb-469f-a165-70867728950e", "cf-ray.8a1b2c_3", "a" * 64],
)
def test_short_safe_request_ids_are_kept(inbound: str) -> None:
    assert accept_request_id(inbound) == inbound


@pytest.mark.parametrize(
    "inbound",
    [None, "", "a" * 65, "line\nbreak", "has space", "-leading", 'quote"', "é"],
)
def test_other_request_ids_are_replaced(inbound: str | None) -> None:
    generated = accept_request_id(inbound)
    assert generated != inbound
    assert len(generated) == 32 and generated.isalnum()


def test_responses_echo_a_safe_inbound_request_id(client: TestClient) -> None:
    response = client.get(f"{API}/utils/health-check/", headers={"X-Request-ID": "r-1"})
    assert response.headers[REQUEST_ID_HEADER] == "r-1"


def test_responses_carry_a_generated_request_id(client: TestClient) -> None:
    unsafe = client.get("/livez", headers={"X-Request-ID": "bad id\twith tab"})
    plain = client.get("/livez")
    assert len(unsafe.headers[REQUEST_ID_HEADER]) == 32
    assert len(plain.headers[REQUEST_ID_HEADER]) == 32
    assert unsafe.headers[REQUEST_ID_HEADER] != plain.headers[REQUEST_ID_HEADER]


def test_origin_rejections_carry_the_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "a" * 32)
    response = client.get("/livez", headers={"X-Request-ID": "edge-1"})
    assert response.status_code == 403
    assert response.headers[REQUEST_ID_HEADER] == "edge-1"


def test_records_logged_during_a_request_carry_its_id() -> None:
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    logger = logging.getLogger("tests.request_id")

    @application.get("/sync")
    def sync_route() -> dict[str, str]:
        logger.info("in_sync_route")
        return {}

    @application.get("/async")
    async def async_route() -> dict[str, str]:
        logger.info("in_async_route")
        return {}

    with captured_logs("tests.request_id") as records:
        with TestClient(application) as client:
            client.get("/sync", headers={"X-Request-ID": "sync-1"})
            client.get("/async", headers={"X-Request-ID": "async-1"})
        logger.info("outside_a_request")
    ids = {record.getMessage(): record.request_id for record in records}
    assert ids == {
        "in_sync_route": "sync-1",
        "in_async_route": "async-1",
        "outside_a_request": None,
    }


def test_errors_are_tagged_with_the_request_id_when_sentry_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    import sentry_sdk

    from app.core import request_id as request_id_module

    monkeypatch.setattr(request_id_module.sentry_sdk, "is_initialized", lambda: True)

    async def endpoint(_scope: Any, _receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b""}

    async def send(_message: Any) -> None:
        return None

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-request-id", b"tagged-1")],
    }
    # Sentry's ASGI integration forks this scope per request.
    with sentry_sdk.isolation_scope() as isolation:
        asyncio.run(RequestIdMiddleware(endpoint)(scope, receive, send))
        assert isolation._tags["request_id"] == "tagged-1"
