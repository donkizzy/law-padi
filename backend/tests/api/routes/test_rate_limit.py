import pytest
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
