import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

API = settings.API_V1_STR


@pytest.mark.usefixtures("corpus")
def test_guest_cookie_stays_on_same_site_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    with TestClient(app, base_url="https://testserver") as guest:
        created = guest.post(f"{API}/conversations", json={})
    assert created.status_code == 201
    cookie = created.headers["set-cookie"].lower()
    assert "samesite=lax" in cookie
