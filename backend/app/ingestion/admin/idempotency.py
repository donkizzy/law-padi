import hashlib
import json
import uuid
from typing import cast

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.legal.models import (
    IdempotencyRecord,
)


def idempotency_scope(operation: str, entity_id: uuid.UUID) -> str:
    return f"{operation}:{entity_id}"


def idempotency_request_hash(body: object) -> str:
    model_dump = getattr(body, "model_dump", None)
    if callable(model_dump):
        return idempotency_payload_hash(model_dump(mode="json"))
    return idempotency_payload_hash(body)


def idempotency_payload_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def idempotency_record_for_request(
    session: Session,
    *,
    scope: str,
    idempotency_key: str,
    request_hash: str,
) -> IdempotencyRecord | None:
    record = session.exec(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    ).first()
    if not record:
        return None
    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different request",
        )
    return record


def add_idempotency_record(
    session: Session,
    *,
    scope: str,
    idempotency_key: str,
    request_hash: str,
    result_type: str,
    result_id: uuid.UUID | None,
    created_by: uuid.UUID | None,
    result_payload: dict[str, object] | None = None,
) -> None:
    session.add(
        IdempotencyRecord(
            scope=scope,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            result_type=result_type,
            result_id=result_id,
            result_payload=result_payload,
            created_by=created_by,
        )
    )


def idempotency_result_payload(record: IdempotencyRecord) -> dict[str, object]:
    payload = record.result_payload
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotent mutation result is no longer available",
        )
    return cast(dict[str, object], payload)
