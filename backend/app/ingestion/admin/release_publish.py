import uuid

from fastapi import HTTPException, status
from sqlmodel import Session, col, select

from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_payload_hash,
    idempotency_record_for_request,
    idempotency_scope,
)
from app.ingestion.admin.queries import check_expected_version, get_release
from app.ingestion.admin.release_gates import (
    ready_retrieval_index_build,
    release_source_and_review_gates,
    retrieval_index_build_validation_gates,
)
from app.ingestion.common import get_datetime_utc
from app.ingestion.pgvector_repository import validate_index_build
from app.ingestion.runtime.queue import (
    append_run_event,
)
from app.legal.enums import (
    AuditSeverity,
    CorpusReleaseStatus,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    InstrumentType,
    ReleasePromotionStatus,
    VectorIndexStatus,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    AuditEvent,
    CorpusRelease,
    CorpusReleaseEntry,
    IngestionRun,
    IngestionStep,
    ReleasePromotionAttempt,
    SourceDocument,
)
from app.legal.release_scope import release_instruments
from app.models import User


def publish_corpus_release(
    session: Session,
    release_id: uuid.UUID,
    *,
    expected_version: int,
    idempotency_key: str,
    current_user: User,
    superuser_override_reason: str | None,
) -> tuple[CorpusRelease, ReleasePromotionAttempt]:
    scope = idempotency_scope("corpus_release.publish", release_id)
    request_hash = idempotency_payload_hash(
        {
            "expected_version": expected_version,
            "release_id": str(release_id),
            "superuser_override_reason": superuser_override_reason,
        }
    )
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if record:
        release = get_release(session, release_id)
        promotion = (
            session.get(ReleasePromotionAttempt, record.result_id)
            if record.result_id
            else None
        )
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent publication result is no longer available",
            )
        return release, promotion
    release = get_release(session, release_id)
    check_expected_version(release.lock_version, expected_version)
    if release.status != CorpusReleaseStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Release must validate cleanly before publication",
        )
    # Publication replaces the whole live corpus, so an Act-only release (a
    # member for composition) would take the Constitution away from readers.
    if InstrumentType.CONSTITUTION not in {
        instrument.instrument_type
        for instrument in release_instruments(session, release.id).values()
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only a release that contains the Constitution can be published; "
                "compose Act releases with the Constitution first"
            ),
        )
    entries = session.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    quality_gates = release_source_and_review_gates(session, entries, release=release)
    if quality_gates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Release source/review gates no longer pass",
                "gates": quality_gates,
            },
        )
    if not ready_retrieval_index_build(session, release.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Release does not have a ready pgvector index build",
        )
    enforce_actor_separation(
        session,
        release,
        current_user,
        superuser_override_reason=superuser_override_reason,
    )
    return publish_pgvector_release(
        session,
        release_id=release_id,
        expected_version=expected_version,
        current_user=current_user,
        idempotency_scope=scope,
        idempotency_key=idempotency_key,
        idempotency_request_hash=request_hash,
    )


def publish_pgvector_release(
    session: Session,
    *,
    release_id: uuid.UUID,
    expected_version: int,
    current_user: User,
    idempotency_scope: str,
    idempotency_key: str,
    idempotency_request_hash: str,
) -> tuple[CorpusRelease, ReleasePromotionAttempt]:
    """Atomically promote a validated pgvector build and its active target."""
    release = session.exec(
        select(CorpusRelease).where(CorpusRelease.id == release_id).with_for_update()
    ).one()
    check_expected_version(release.lock_version, expected_version)
    build = ready_retrieval_index_build(session, release.id)
    if build is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Release does not have a ready pgvector index build",
        )
    report = validate_index_build(
        session,
        build=build,
        expected_segment_count=build.expected_segment_count,
    )
    build.validation_report = report
    if not report["is_valid"] or retrieval_index_build_validation_gates(build):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="pgvector index validation no longer passes",
        )
    index_kind = build.index_kind
    target = session.exec(
        select(ActiveRetrievalTarget)
        .where(ActiveRetrievalTarget.index_kind == index_kind)
        .with_for_update()
    ).first()
    # During the expand/migrate period a production release may have been
    # published by the legacy backend without an active pgvector target. Lock
    # the canonical production row as well so the single-production invariant
    # is preserved across the backend cutover.
    previous_release = session.exec(
        select(CorpusRelease)
        .where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION,
            CorpusRelease.id != release.id,
        )
        .with_for_update()
    ).first()
    if previous_release is None and target is not None:
        target_release = session.get(CorpusRelease, target.release_id)
        if target_release is not None and target_release.id != release.id:
            previous_release = target_release
    now = get_datetime_utc()
    promotion = ReleasePromotionAttempt(
        release_id=release.id,
        retrieval_index_build_id=build.id,
        index_kind=index_kind,
        requested_by=current_user.id,
        status=ReleasePromotionStatus.PUBLISHING,
        previous_release_id=previous_release.id if previous_release else None,
        started_at=now,
    )
    session.add(promotion)
    session.flush()
    if target is None:
        target = ActiveRetrievalTarget(
            index_kind=index_kind,
            release_id=release.id,
            embedding_run_id=build.embedding_run_id,
            retrieval_index_build_id=build.id,
            profile_id=build.profile_id,
            lock_version=1,
            activated_by=current_user.id,
            activated_at=now,
            updated_at=now,
        )
    else:
        target.release_id = release.id
        target.embedding_run_id = build.embedding_run_id
        target.retrieval_index_build_id = build.id
        target.profile_id = build.profile_id
        target.lock_version += 1
        target.activated_by = current_user.id
        target.activated_at = now
        target.updated_at = now
    if previous_release and previous_release.id != release.id:
        previous_release.status = CorpusReleaseStatus.RETIRED
        previous_release.lock_version += 1
        session.add(previous_release)
        # Preserve atomic promotion while satisfying the immediate unique index
        # regardless of the UUID order SQLAlchemy uses for pending updates.
        session.flush()
    release.status = CorpusReleaseStatus.PRODUCTION
    release.approved_by = current_user.id
    release.approved_at = now
    release.lock_version += 1
    build.status = VectorIndexStatus.PROMOTED
    build.updated_at = now
    promotion.status = ReleasePromotionStatus.SUCCEEDED
    promotion.completed_at = now
    composition = (release.validation_report or {}).get("composition")
    contributing_runs = select(CorpusReleaseEntry.ingestion_run_id).where(
        CorpusReleaseEntry.release_id == release.id,
        col(CorpusReleaseEntry.ingestion_run_id).is_not(None),
    )
    if composition and previous_release is not None:
        # Runs inherited from production already have their publication history.
        carried_runs = select(CorpusReleaseEntry.ingestion_run_id).where(
            CorpusReleaseEntry.release_id == previous_release.id,
            col(CorpusReleaseEntry.ingestion_run_id).is_not(None),
        )
        contributing_runs = contributing_runs.where(
            col(CorpusReleaseEntry.ingestion_run_id).not_in(carried_runs)
        )
    contributing_run_ids = set(session.exec(contributing_runs.distinct()).all())
    if composition:
        contributing_run_ids.add(uuid.UUID(composition["run_id"]))
    for run_id in contributing_run_ids:
        if run_id is None:
            continue
        contributing_run = session.exec(
            select(IngestionRun).where(IngestionRun.id == run_id).with_for_update()
        ).one_or_none()
        if contributing_run is None:
            continue
        publishing_step = session.exec(
            select(IngestionStep)
            .where(
                IngestionStep.run_id == contributing_run.id,
                IngestionStep.stage == IngestionStage.PUBLISHING,
            )
            .with_for_update()
        ).first()
        if publishing_step is not None:
            publishing_step.status = IngestionStepStatus.SUCCEEDED
            publishing_step.completed_at = now
            publishing_step.updated_at = now
            publishing_step.lock_version += 1
            session.add(publishing_step)
        contributing_run.status = IngestionRunStatus.PUBLISHED
        contributing_run.current_stage = IngestionStage.PUBLISHING
        contributing_run.completed_at = now
        contributing_run.updated_at = now
        contributing_run.lock_version += 1
        session.add(contributing_run)
        append_run_event(
            session,
            contributing_run,
            event_type="release_published",
            message="Corpus release published to the active pgvector target",
            step=publishing_step,
            stage=IngestionStage.PUBLISHING,
            payload={
                "release_id": str(release.id),
                "retrieval_index_build_id": str(build.id),
                "index_kind": index_kind,
            },
            commit=False,
        )
    session.add_all([target, release, build, promotion])
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="corpus_release.publish",
            entity_type="corpus_release",
            entity_id=release.id,
            severity=AuditSeverity.INFO,
            payload={
                "backend": "pgvector",
                "index_kind": index_kind,
                "retrieval_index_build_id": str(build.id),
                "active_target_lock_version": target.lock_version,
            },
        )
    )
    add_idempotency_record(
        session,
        scope=idempotency_scope,
        idempotency_key=idempotency_key,
        request_hash=idempotency_request_hash,
        result_type="release_promotion_attempt",
        result_id=promotion.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(release)
    session.refresh(promotion)
    return release, promotion


def enforce_actor_separation(
    session: Session,
    release: CorpusRelease,
    current_user: User,
    *,
    superuser_override_reason: str | None,
) -> None:
    entries = session.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    source_ids = [
        entry.source_document_id for entry in entries if entry.source_document_id
    ]
    sources = session.exec(
        select(SourceDocument).where(col(SourceDocument.id).in_(source_ids))
    ).all()
    uploader_ids = {source.created_by for source in sources if source.created_by}
    if current_user.id not in uploader_ids:
        return
    if current_user.is_superuser and superuser_override_reason:
        session.add(
            AuditEvent(
                actor_user_id=current_user.id,
                action="corpus_release.publish_override",
                entity_type="corpus_release",
                entity_id=release.id,
                severity=AuditSeverity.HIGH,
                reason=superuser_override_reason,
                payload={
                    "source_upload_actor_ids": sorted(str(uid) for uid in uploader_ids)
                },
            )
        )
        session.commit()
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Publisher must differ from the source uploader",
    )
