"""Translate application failures into the public error contract."""

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.core.errors import DomainError, ErrorCode


class ErrorResponse(BaseModel):
    code: str
    detail: str


class ValidationErrorResponse(BaseModel):
    code: str
    detail: list[dict[str, Any]]


class APIError(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


_STATUS_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limit_exceeded",
    503: "service_unavailable",
}
_DOMAIN_STATUS = {
    ErrorCode.EMAIL_ALREADY_EXISTS: 409,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.BAD_GATEWAY: 502,
}


async def error_response(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, RequestValidationError):
        response = await request_validation_exception_handler(request, exc)
        # Use FastAPI's encoder for errors whose context contains a ValueError.
        content = json.loads(bytes(response.body))
        content["code"] = "validation_error"
        return JSONResponse(content, status_code=response.status_code)
    if isinstance(exc, DomainError):
        headers = (
            {"Retry-After": str(exc.retry_after)}
            if exc.retry_after is not None
            else None
        )
        return JSONResponse(
            {"detail": exc.detail, "code": exc.code},
            status_code=_DOMAIN_STATUS[exc.code],
            headers=headers,
        )
    assert isinstance(exc, HTTPException)
    detail: Any = exc.detail
    code = exc.code if isinstance(exc, APIError) else None
    return JSONResponse(
        {
            "detail": detail,
            "code": code or _STATUS_CODES.get(exc.status_code, "http_error"),
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    for exception in (DomainError, HTTPException, RequestValidationError):
        app.add_exception_handler(exception, error_response)
