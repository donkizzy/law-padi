import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import settings
from app.main import app
from tests.utils.utils import random_email

API = settings.API_V1_STR


def test_one_account_is_throttled_across_many_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "p" * 32)
    monkeypatch.setattr(
        rate_limit, "LOGIN_PER_EMAIL", rate_limit.Limit("login-email-test", 2, 900)
    )
    email = random_email()
    statuses = []
    with TestClient(app) as client:
        for address in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
            statuses.append(
                client.post(
                    f"{API}/login/access-token",
                    data={"username": email, "password": "wrong-password"},
                    headers={
                        "x-origin-proxy-secret": "p" * 32,
                        "x-forwarded-for": address,
                    },
                ).status_code
            )
    assert statuses == [400, 400, 429]


def _request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            "client": ("10.0.0.9", 1234),
        }
    )


def test_client_ip_prefers_the_workers_dedicated_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", "p" * 32)
    # A hosting edge may replace X-Forwarded-For with the Worker's address.
    request = _request(
        {"x-origin-client-ip": "203.0.113.7", "x-forwarded-for": "198.51.100.200"}
    )
    assert rate_limit.client_ip(request) == "203.0.113.7"
    fallback = _request({"x-forwarded-for": "203.0.113.8, 198.51.100.200"})
    assert rate_limit.client_ip(fallback) == "203.0.113.8"
    assert rate_limit.client_ip(_request({})) == "10.0.0.9"


def test_client_ip_ignores_forwarding_headers_without_the_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ORIGIN_PROXY_SECRET", None)
    request = _request(
        {"x-origin-client-ip": "203.0.113.7", "x-forwarded-for": "203.0.113.8"}
    )
    assert rate_limit.client_ip(request) == "10.0.0.9"
