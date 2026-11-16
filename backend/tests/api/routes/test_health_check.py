from fastapi.testclient import TestClient

from app.core.config import settings

API = settings.API_V1_STR


def test_public_health_check_reports_readiness_only(client: TestClient) -> None:
    response = client.get(f"{API}/utils/health-check/")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
