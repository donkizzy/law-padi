import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app.ingestion.admin import runs
from app.ingestion.admin.alerts import read_admin_operational_alerts
from app.legal.enums import EmbeddingProviderKind, IngestionRunStatus, IngestionStage
from app.legal.models import (
    CorpusRelease,
    EmbeddingProfile,
    IdempotencyRecord,
    IngestionEvent,
    IngestionTask,
    TransactionalOutbox,
)
from tests.api.routes.admin.conftest import _source_and_run, _superuser


@pytest.mark.parametrize(
    "command", ["cancel", "resume", "waiting_resume", "retry", "embed"]
)
@pytest.mark.parametrize("interrupt", [False, True])
def test_run_command_commits_state_tasks_events_and_receipt_together(
    db: Session, monkeypatch: pytest.MonkeyPatch, command: str, interrupt: bool
) -> None:
    _source, run = _source_and_run(db)
    user = _superuser(db)
    kwargs: dict[str, Any] = {}
    if command == "cancel":
        mutate: Callable[..., Any] = runs.cancel_ingestion_run
        kwargs["reason"] = "cancel requested"
    elif command == "waiting_resume":
        mutate = runs.resume_ingestion_run
    elif command == "resume":
        run.status = IngestionRunStatus.CANCELLED
        run.current_stage = IngestionStage.NATIVE_EXTRACTION
        mutate = runs.resume_ingestion_run
    elif command == "retry":
        run.status = IngestionRunStatus.FAILED
        run.current_stage = IngestionStage.NATIVE_EXTRACTION
        mutate = runs.retry_ingestion_run
    else:
        run.status = IngestionRunStatus.READY_TO_EMBED
        run.current_stage = IngestionStage.EMBEDDING
        release = CorpusRelease(version=f"atomic-{uuid.uuid4().hex}")
        db.add(release)
        db.add(
            EmbeddingProfile(
                name=f"atomic-{uuid.uuid4().hex}",
                provider=EmbeddingProviderKind.OPENAI,
                model_name="test",
                model_revision="pinned",
                vector_dimensions=1024,
            )
        )
        db.flush()
        monkeypatch.setattr(runs, "release_id_for_run", lambda *_args: release.id)
        mutate = runs.start_embedding
    db.add(run)
    db.commit()
    run_id, initial_status, initial_version = run.id, run.status, run.lock_version
    key = f"atomic-{uuid.uuid4().hex}"
    commits: list[None] = []

    def count_commits(_session: Session) -> None:
        commits.append(None)

    def interrupt_receipt(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("interrupted before receipt")

    if interrupt:
        monkeypatch.setattr(runs, "add_idempotency_record", interrupt_receipt)
    event.listen(db, "after_commit", count_commits)
    try:
        if interrupt:
            with pytest.raises(RuntimeError, match="interrupted"):
                mutate(
                    db,
                    run_id,
                    expected_version=initial_version,
                    idempotency_key=key,
                    current_user=user,
                    **kwargs,
                )
            db.rollback()
        else:
            mutate(
                db,
                run_id,
                expected_version=initial_version,
                idempotency_key=key,
                current_user=user,
                **kwargs,
            )
    finally:
        event.remove(db, "after_commit", count_commits)
    assert len(commits) == (0 if interrupt else 1)
    db.refresh(run)
    events = db.exec(
        select(IngestionEvent).where(IngestionEvent.run_id == run_id)
    ).all()
    tasks = db.exec(select(IngestionTask).where(IngestionTask.run_id == run_id)).all()
    receipts = db.exec(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    ).all()
    outbox = db.exec(
        select(TransactionalOutbox).where(
            TransactionalOutbox.aggregate_id.in_([run_id, *(task.id for task in tasks)])
        )
    ).all()
    if interrupt:
        assert run.status == initial_status
        assert run.lock_version == initial_version
        assert not events and not tasks and not receipts and not outbox
    else:
        assert len(events) == len(receipts) == 1
        assert len(tasks) == (1 if command in {"resume", "retry", "embed"} else 0)
        assert len(outbox) == len(events) + len(tasks)
        assert all(task.step_id is not None for task in tasks)


def test_alerts_report_active_run_without_active_task(db: Session) -> None:
    _source, run = _source_and_run(db)
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = IngestionStage.NATIVE_EXTRACTION
    db.add(run)
    db.commit()
    alerts = read_admin_operational_alerts(db, limit=1000)
    assert any(
        alert.run_id == run.id and alert.alert_type == "missing_active_task"
        for alert in alerts
    )


@pytest.mark.parametrize("command", ["approve", "verify"])
@pytest.mark.parametrize("interrupt", [False, True])
def test_review_completion_is_atomic_with_operator_command(
    db: Session, monkeypatch: pytest.MonkeyPatch, command: str, interrupt: bool
) -> None:
    from app.ingestion.admin import review, review_completion, sources
    from app.legal.enums import (
        ExtractionCandidateStatus,
        ProvisionKind,
        ReviewDecisionType,
        VerificationStatus,
    )
    from app.legal.models import ExtractionCandidate, ReviewDecisionRecord
    from app.legal.schemas import ReviewDecisionCreate

    source, run = _source_and_run(db)
    user = _superuser(db)
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    source.verification_status = (
        VerificationStatus.VERIFIED
        if command == "approve"
        else VerificationStatus.UNVERIFIED
    )
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        canonical_path=f"atomic.section37.{uuid.uuid4().hex}",
        sort_key="037",
        status=(
            ExtractionCandidateStatus.NEEDS_REVIEW
            if command == "approve"
            else ExtractionCandidateStatus.APPROVED
        ),
    )
    db.add_all([source, run, candidate])
    db.commit()
    run_id, source_id, candidate_id = run.id, source.id, candidate.id
    key = f"atomic-review-{uuid.uuid4().hex}"
    commits: list[None] = []

    def count_commits(_session: Session) -> None:
        commits.append(None)

    def interrupt_event(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("interrupted after queueing")

    if interrupt:
        monkeypatch.setattr(review_completion, "append_run_event", interrupt_event)
    event.listen(db, "after_commit", count_commits)
    try:

        def mutate() -> None:
            if command == "approve":
                review.decide_review_candidate(
                    db,
                    candidate_id,
                    ReviewDecisionCreate(
                        idempotency_key=key,
                        expected_version=candidate.lock_version,
                        decision=ReviewDecisionType.APPROVE,
                        reason="Checked source",
                    ),
                    user,
                )
            else:
                sources.verify_source_document(
                    db,
                    source_id,
                    expected_version=source.lock_version,
                    idempotency_key=key,
                    current_user=user,
                    reason="Checked source",
                )

        if interrupt:
            with pytest.raises(RuntimeError, match="interrupted"):
                mutate()
            db.rollback()
        else:
            mutate()
    finally:
        event.remove(db, "after_commit", count_commits)
    assert len(commits) == (0 if interrupt else 1)
    db.refresh(run)
    db.refresh(candidate)
    db.refresh(source)
    tasks = db.exec(select(IngestionTask).where(IngestionTask.run_id == run_id)).all()
    receipts = db.exec(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    ).all()
    decisions = db.exec(
        select(ReviewDecisionRecord).where(
            ReviewDecisionRecord.candidate_id == candidate_id
        )
    ).all()
    if interrupt:
        assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
        assert not tasks and not receipts and not decisions
        if command == "verify":
            assert source.verification_status == VerificationStatus.UNVERIFIED
        else:
            assert candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    else:
        assert run.status == IngestionRunStatus.QUEUED
        assert len(tasks) == len(receipts) == 1
        outbox = db.exec(
            select(TransactionalOutbox).where(
                TransactionalOutbox.aggregate_id == tasks[0].id
            )
        ).one()
        assert outbox.event_type == "ingestion_task.enqueued"
