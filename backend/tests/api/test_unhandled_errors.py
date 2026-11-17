import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.main import app
from tests.utils.logs import captured_logs


def _application() -> FastAPI:
    application = FastAPI()
    register_error_handlers(application)
    application.add_middleware(RequestIdMiddleware)

    @application.get("/broken/{item}")
    def broken(item: str) -> None:
        raise RuntimeError(f"defect while handling {item}")

    @application.get("/missing")
    def missing() -> None:
        raise HTTPException(status_code=404, detail="Not found")

    return application


def test_unexpected_errors_return_a_generic_500_with_the_request_id() -> None:
    with captured_logs("app.api.errors") as records:
        with TestClient(_application(), raise_server_exceptions=False) as client:
            response = client.get(
                "/broken/ada@example.com", headers={"X-Request-ID": "req-500"}
            )
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal Server Error",
        "code": "internal_error",
        "request_id": "req-500",
    }
    assert response.headers[REQUEST_ID_HEADER] == "req-500"
    (record,) = records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "unhandled_exception"
    assert record.request_id == "req-500"
    assert record.route == "/broken/{item}"
    assert record.error_type == "RuntimeError"
    assert record.exc_info is not None


def test_unexpected_errors_still_reach_the_server() -> None:
    # Starlette re-raises after responding so the server and Sentry see it.
    with TestClient(_application()) as client:
        with pytest.raises(RuntimeError):
            client.get("/broken/x")


def test_handled_errors_keep_their_shape() -> None:
    with TestClient(_application()) as client:
        response = client.get("/missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found", "code": "not_found"}


def test_api_errors_keep_their_shape_and_gain_the_header() -> None:
    with TestClient(app) as client:
        anonymous = client.get("/api/v1/users/me", headers={"X-Request-ID": "r"})
        invalid = client.post("/api/v1/login/access-token", data={})
    assert anonymous.status_code == 401
    assert anonymous.json() == {
        "detail": "Not authenticated",
        "code": "not_authenticated",
    }
    assert anonymous.headers[REQUEST_ID_HEADER] == "r"
    assert invalid.status_code == 422
    assert set(invalid.json()) == {"detail", "code"}
    assert invalid.json()["code"] == "validation_error"
