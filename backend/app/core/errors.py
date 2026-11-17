"""Transport-independent failures shared by account and core services."""

from enum import StrEnum


class ErrorCode(StrEnum):
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class DomainError(Exception):
    def __init__(
        self, code: ErrorCode, detail: str, *, retry_after: int | None = None
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after
