class IngestionWorkerError(RuntimeError):
    pass


class IngestionLeaseLost(IngestionWorkerError):
    pass


class IngestionPermanentError(IngestionWorkerError):
    pass


class IngestionTransientError(IngestionWorkerError):
    pass


def retryable_error(exc: Exception) -> bool:
    import httpx
    from fastapi import HTTPException

    from app.ingestion.runtime.retry import retryable_status

    if isinstance(exc, IngestionPermanentError):
        return False
    if isinstance(exc, IngestionTransientError | httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return retryable_status(exc.response.status_code)
    if isinstance(exc, HTTPException):
        return retryable_status(exc.status_code)
    if isinstance(exc.__cause__, Exception):
        return retryable_error(exc.__cause__)
    explicit = getattr(exc, "retryable", None)
    if isinstance(explicit, bool):
        return explicit
    return not isinstance(exc, IngestionWorkerError | ValueError | FileNotFoundError)
