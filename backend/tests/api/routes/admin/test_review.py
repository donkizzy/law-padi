import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.legal.enums import (
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    ProvisionKind,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    VerificationStatus,
)
from app.legal.models import (
    AuditEvent,
    CandidateRevision,
    ExtractionCandidate,
    IdempotencyRecord,
    IngestionEvent,
    IngestionStep,
    IngestionTask,
    ReviewDecisionRecord,
    ReviewIssue,
)
from tests.api.routes.admin.conftest import _source_and_run, _superuser


def test_review_item_revision_and_decision_enforce_blocking_issues(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to privacy",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Every citizen is entitled to privacy.",
        normalized_text="Every citizen is entitled to privacy.",
        source_page_start=2,
        source_page_end=2,
        parser_confidence=0.62,
        extractor_confidence=0.71,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=1,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="low_confidence",
        severity=ReviewIssueSeverity.BLOCKING,
        status=ReviewIssueStatus.OPEN,
        blocking=True,
        message="Parser confidence fell below the publication threshold",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    list_response = client.get(
        f"{settings.API_V1_STR}/admin/review-items"
        f"?issue=low_confidence&confidence_lte=0.75&page=2&path=section.37",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["data"]] == [str(candidate.id)]

    blocked_decision = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"decision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "decision": ReviewDecisionType.APPROVE,
            "reason": "Approved too early",
        },
    )
    assert blocked_decision.status_code == 409

    revision_key = f"review-{uuid.uuid4().hex}"
    revision_body = {
        "idempotency_key": revision_key,
        "expected_version": candidate.lock_version,
        "revised_text": "Every citizen is entitled to private and family life.",
        "reason": "Corrected extracted constitutional text.",
    }
    revision_response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json=revision_body,
    )
    assert revision_response.status_code == 200
    revised = revision_response.json()
    assert revised["latest_revision_text"] == (
        "Every citizen is entitled to private and family life."
    )
    assert revised["revision_number"] == 2
    repeated_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json=revision_body,
    )
    assert repeated_revision.status_code == 200
    assert repeated_revision.json()["revision_number"] == 2
    assert (
        db.exec(
            select(func.count())
            .select_from(CandidateRevision)
            .where(CandidateRevision.candidate_id == candidate.id)
        ).one()
        == 1
    )
    conflicting_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={**revision_body, "revised_text": "Different text with same key."},
    )
    assert conflicting_revision.status_code == 409
    assert conflicting_revision.json()["detail"] == (
        "Idempotency key was already used for a different request"
    )

    issue.status = ReviewIssueStatus.RESOLVED
    issue.resolved_by = _superuser(db).id
    issue.resolved_at = datetime.now(UTC)
    candidate.blocking_issue_count = 0
    db.add(issue)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    decision_key = f"decision-{uuid.uuid4().hex}"
    decision_body = {
        "idempotency_key": decision_key,
        "expected_version": candidate.lock_version,
        "decision": ReviewDecisionType.APPROVE,
        "reason": "Reviewed against source pages.",
    }
    decision_response = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json=decision_body,
    )

    assert decision_response.status_code == 200
    decided = decision_response.json()
    assert decided["status"] == ExtractionCandidateStatus.APPROVED
    assert decided["decisions"][0]["decision"] == ReviewDecisionType.APPROVE
    assert db.exec(
        select(ReviewDecisionRecord).where(
            ReviewDecisionRecord.candidate_id == candidate.id
        )
    ).one()
    repeated_decision = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json=decision_body,
    )
    assert repeated_decision.status_code == 200
    assert repeated_decision.json()["status"] == ExtractionCandidateStatus.APPROVED
    assert (
        db.exec(
            select(func.count())
            .select_from(ReviewDecisionRecord)
            .where(ReviewDecisionRecord.candidate_id == candidate.id)
        ).one()
        == 1
    )
    assert (
        db.exec(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(
                col(IdempotencyRecord.idempotency_key).in_([revision_key, decision_key])
            )
        ).one()
        == 2
    )


def test_review_revision_reruns_unit_validators_and_resolves_fixed_issue(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to privacy",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Every citizen is entitled to privacy.",
        normalized_text="Every citizen is entitled to privacy.",
        source_page_start=2,
        source_page_end=2,
        parser_confidence=0.9,
        extractor_confidence=0.9,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=0,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    bad_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"revision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "Every citizen is entitled to privacy (",
            "reason": "Testing correction validation",
        },
    )
    assert bad_revision.status_code == 200
    bad_payload = bad_revision.json()
    assert bad_payload["blocking_issue_count"] == 1
    assert [
        issue["issue_type"]
        for issue in bad_payload["issues"]
        if issue["status"] == ReviewIssueStatus.OPEN
    ] == ["revision_unbalanced_punctuation"]
    blocked_decision = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"decision-{uuid.uuid4().hex}",
            "expected_version": bad_payload["lock_version"],
            "decision": ReviewDecisionType.APPROVE,
            "reason": "Still malformed",
        },
    )
    assert blocked_decision.status_code == 409

    db.refresh(candidate)
    fixed_revision = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"revision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "Every citizen is entitled to privacy.",
            "reason": "Fixed punctuation after validator rerun",
        },
    )

    assert fixed_revision.status_code == 200
    fixed_payload = fixed_revision.json()
    assert fixed_payload["blocking_issue_count"] == 0
    issue = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "revision_unbalanced_punctuation",
        )
    ).one()
    assert issue.status == ReviewIssueStatus.RESOLVED
    assert issue.resolved_by == _superuser(db).id
    assert issue.resolved_at is not None


@pytest.mark.parametrize("source_matches", [True, False])
def test_revision_revalidates_original_coverage_without_waiving_unrelated_issues(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    source_matches: bool,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        canonical_path=f"constitution.1999.section37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Each Secretariat shall su bmit a Report.",
        source_page_start=2,
        source_page_end=2,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=2,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    coverage = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="source_span_coverage",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Source coverage",
    )
    unrelated = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="graph_numbering_gap",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Numbering gap",
    )
    db.add_all([coverage, unrelated])
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"formatting-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "Each Secretariat shall submit a Report.",
            "source_spans": [
                {
                    "text": "Each Secretariat shall su bmit a Report."
                    if source_matches
                    else "An unrelated paragraph.",
                    "page_number": 2,
                    "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                }
            ],
            "reason": "Whitespace-only source-verified revision",
        },
    )
    assert response.status_code == 200
    db.refresh(coverage)
    db.refresh(unrelated)
    db.refresh(candidate)
    assert candidate.raw_text == "Each Secretariat shall su bmit a Report."
    assert candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    assert coverage.status == (
        ReviewIssueStatus.RESOLVED if source_matches else ReviewIssueStatus.OPEN
    )
    assert unrelated.status == ReviewIssueStatus.OPEN
    assert candidate.blocking_issue_count == (1 if source_matches else 2)
    revision = db.exec(
        select(CandidateRevision).where(CandidateRevision.candidate_id == candidate.id)
    ).one()
    assert revision.previous_text == candidate.raw_text
    assert revision.diff
    if source_matches:
        assert coverage.resolution_evidence is not None
        assert coverage.resolution_evidence["exact_source_character_match"] is True


def test_formatting_revision_does_not_duplicate_original_punctuation_blocker(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        canonical_path=f"constitution.1999.section54.{uuid.uuid4().hex}",
        sort_key="054",
        raw_text="(3 The decision shall be made.",
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=1,
    )
    db.add(candidate)
    db.commit()
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="unbalanced_punctuation",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Malformed punctuation in source",
    )
    db.add(issue)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"formatting-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "revised_text": "(3 The decision shall be made.",
            "reason": "Preserve punctuation exactly as in source",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["blocking_issue_count"] == 1
    assert [
        item["issue_type"] for item in payload["issues"] if item["status"] == "open"
    ] == ["unbalanced_punctuation"]


def test_final_review_approval_requires_explicit_source_verification(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    review_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.REVIEW,
        )
    ).one()
    review_step.status = IngestionStepStatus.BLOCKED
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to privacy",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
        raw_text="Every citizen is entitled to privacy.",
        normalized_text="every citizen is entitled to privacy.",
        source_page_start=2,
        source_page_end=2,
        source_spans=[
            {"page": 2, "bbox": {"x0": 36.0, "y0": 440.0, "x1": 220.0, "y1": 460.0}}
        ],
        parser_confidence=0.94,
        extractor_confidence=0.96,
        status=ExtractionCandidateStatus.NEEDS_REVIEW,
        blocking_issue_count=0,
    )
    # A rejected duplicate scan and its open finding must not hold the run back.
    rejected = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        canonical_path=f"constitution.1999.rejected-duplicate.{uuid.uuid4().hex}",
        sort_key="999",
        raw_text="Every citizen is entitled (to privacy.",
        status=ExtractionCandidateStatus.REJECTED,
        blocking_issue_count=1,
    )
    db.add_all([run, review_step, candidate, rejected])
    db.commit()
    db.add(
        ReviewIssue(
            candidate_id=rejected.id,
            issue_type="unbalanced_punctuation",
            blocking=True,
            message="Unbalanced brackets in a rejected duplicate.",
        )
    )
    db.commit()
    db.refresh(candidate)

    response = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}/decision",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"decision-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "decision": ReviewDecisionType.APPROVE,
            "reason": "Reviewed against source pages.",
        },
    )

    assert response.status_code == 200
    db.refresh(source)
    db.refresh(run)
    db.refresh(review_step)
    assert source.verification_status == VerificationStatus.UNVERIFIED
    assert source.verified_by is None
    assert review_step.status == IngestionStepStatus.BLOCKED
    assert review_step.metrics == {
        "candidate_count": 1,
        "source_verification_required": True,
    }
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW
    assert (
        db.exec(
            select(IngestionTask).where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.MATERIALIZING.value,
            )
        ).first()
        is None
    )
    source_event = db.exec(
        select(IngestionEvent).where(
            IngestionEvent.run_id == run.id,
            IngestionEvent.event_type == "source_verification_required",
        )
    ).one()
    assert source_event.payload == {
        "candidate_count": 1,
        "source_document_id": str(source.id),
    }

    verification_body = {
        "idempotency_key": f"verify-source-{uuid.uuid4().hex}",
        "expected_version": source.lock_version,
        "reason": "Verified source URL, hash, and page evidence.",
    }
    verify_response = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=superuser_token_headers,
        json=verification_body,
    )

    assert verify_response.status_code == 200
    verify_payload = verify_response.json()
    assert verify_payload["verification_status"] == VerificationStatus.VERIFIED.value
    assert verify_payload["verified_by"] == str(_superuser(db).id)
    assert verify_payload["lock_version"] == 2
    repeated_verify = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=superuser_token_headers,
        json=verification_body,
    )
    assert repeated_verify.status_code == 200
    assert repeated_verify.json()["lock_version"] == 2
    db.refresh(source)
    db.refresh(run)
    db.refresh(review_step)
    assert source.verification_status == VerificationStatus.VERIFIED
    assert source.verified_by == _superuser(db).id
    assert review_step.status == IngestionStepStatus.SUCCEEDED
    assert run.status == IngestionRunStatus.QUEUED
    assert run.current_stage == IngestionStage.MATERIALIZING
    materializing_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.MATERIALIZING.value,
        )
    ).one()
    assert materializing_task.status == IngestionTaskStatus.PENDING
    event = db.exec(
        select(IngestionEvent).where(
            IngestionEvent.run_id == run.id,
            IngestionEvent.event_type == "review_completed",
        )
    ).one()
    assert event.payload == {"candidate_count": 1}
    audit_events = db.exec(
        select(AuditEvent).where(
            AuditEvent.action == "source_document.verified",
            AuditEvent.entity_id == source.id,
        )
    ).all()
    assert len(audit_events) == 1
    audit_event = audit_events[0]
    assert audit_event.actor_user_id == _superuser(db).id
    assert audit_event.payload == {
        "reason": "Verified source URL, hash, and page evidence."
    }
