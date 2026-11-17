"""Transport-independent failures shared by account and core services."""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BAD_REQUEST = "bad_request"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    VALIDATION_ERROR = "validation_error"
    BAD_GATEWAY = "bad_gateway"


class DomainError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        detail: Any,
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after
