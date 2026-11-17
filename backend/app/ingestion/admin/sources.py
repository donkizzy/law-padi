import uuid

from sqlmodel import Session

from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_payload_hash,
    idempotency_record_for_request,
    idempotency_scope,
)
from app.ingestion.admin.queries import check_expected_version, get_source_document
from app.ingestion.admin.review_completion import (
    queue_materialization_for_verified_source,
)
from app.ingestion.common import get_datetime_utc
from app.legal.enums import (
    AuditSeverity,
    VerificationStatus,
)
from app.legal.models import (
    AuditEvent,
    SourceDocument,
)
from app.models import User


def verify_source_document(
    session: Session,
    source_document_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    reason: str,
    current_user: User,
) -> SourceDocument:
    scope = idempotency_scope("source_document.verify", source_document_id)
    request_hash = idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "reason": reason,
            "source_document_id": str(source_document_id),
        }
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_source_document(session, source_document_id)

    source = get_source_document(session, source_document_id)
    check_expected_version(source.lock_version, expected_version)
    if source.verification_status != VerificationStatus.VERIFIED:
        now = get_datetime_utc()
        source.verification_status = VerificationStatus.VERIFIED
        source.verified_by = current_user.id
        source.verified_at = now
        source.lock_version += 1
        session.add(source)
        session.add(
            AuditEvent(
                actor_user_id=current_user.id,
                action="source_document.verified",
                entity_type="source_document",
                entity_id=source.id,
                severity=AuditSeverity.INFO,
                payload={"reason": reason},
            )
        )

    queue_materialization_for_verified_source(session, source=source)
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="source_document",
        result_id=source.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(source)
    return source


def correct_source_document_title(
    session: Session,
    source_document_id: uuid.UUID,
    *,
    title: str,
    expected_version: int,
    idempotency_key: str,
    reason: str,
    current_user: User,
) -> SourceDocument:
    """Correct the display title; stored files, hashes and manifests are unchanged."""
    scope = idempotency_scope("source_document.correct_title", source_document_id)
    request_hash = idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "reason": reason,
            "source_document_id": str(source_document_id),
            "title": title,
        }
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        return get_source_document(session, source_document_id)

    source = get_source_document(session, source_document_id)
    check_expected_version(source.lock_version, expected_version)
    previous_title = source.title
    source.title = title
    source.lock_version += 1
    session.add(source)
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="source_document.title_corrected",
            entity_type="source_document",
            entity_id=source.id,
            severity=AuditSeverity.INFO,
            reason=reason,
            payload={"previous_title": previous_title, "title": title},
        )
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_type="source_document",
        result_id=source.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(source)
    return source
