from app.core.config import settings


def test_tests_cannot_reach_a_configured_bucket() -> None:
    assert settings.INGESTION_STORAGE_BACKEND == "local"
    assert settings.R2_ENDPOINT_URL is None
    assert settings.R2_ACCESS_KEY_ID is None
    assert settings.R2_SECRET_ACCESS_KEY is None
