import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.legal.enums import (
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    ReviewIssueSeverity,
    ReviewIssueStatus,
)
from app.legal.models import (
    AuditEvent,
    CandidateRevision,
    ExtractionCandidate,
    IngestionRun,
    IngestionTask,
    ReviewIssue,
    SourcePage,
)
from tests.api.routes.admin.conftest import _source_and_run


def test_imported_review_boundaries_preserve_review_and_block_excluded_text(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    run.status = IngestionRunStatus.WAITING_FOR_REVIEW
    run.current_stage = IngestionStage.REVIEW
    run.pipeline_config = {
        "review_import_complete": True,
        "provisional_page_boundaries": True,
    }
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=number,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        )
        for number in range(1, 4)
    ]
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="142",
        canonical_path=f"boundaries-{uuid.uuid4().hex}.section142",
        sort_key="142",
        raw_text="Citation sentence. Authentication text.",
        source_page_start=2,
        source_page_end=3,
        source_spans=[
            {"page_number": 2, "text": "Citation sentence."},
            {"page_number": 3, "text": "Authentication text."},
        ],
    )
    db.add_all([run, *pages, candidate])
    db.commit()
    boundary_issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="provisional_page_boundaries",
        severity=ReviewIssueSeverity.BLOCKING,
        blocking=True,
        message="Confirm imported boundaries",
    )
    db.add(boundary_issue)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"boundaries-{uuid.uuid4().hex}",
            "expected_run_version": run.lock_version,
            "pages": [
                {
                    "page_number": page.page_number,
                    "expected_version": page.lock_version,
                    "inclusion_status": "included"
                    if page.page_number == 2
                    else "excluded",
                    "inclusion_reason": "Checked legal body against front and authentication matter.",
                }
                for page in pages
            ],
        },
    )
    assert response.status_code == 200
    db.expire_all()
    retained_run = db.get(IngestionRun, run.id)
    assert retained_run and retained_run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert retained_run.current_stage == IngestionStage.REVIEW
    assert retained_run.pipeline_config["provisional_page_boundaries"] is False
    assert db.get(ReviewIssue, boundary_issue.id).status == ReviewIssueStatus.RESOLVED
    excluded = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "excluded_source_page",
        )
    ).one()
    assert excluded.status == ReviewIssueStatus.OPEN
    assert not db.exec(
        select(IngestionTask).where(IngestionTask.run_id == run.id)
    ).all()
    retained_candidate = db.get(ExtractionCandidate, candidate.id)
    assert retained_candidate
    fixed = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"repair-{uuid.uuid4().hex}",
            "expected_version": retained_candidate.lock_version,
            "source_page_end": 2,
            "source_spans": [{"page_number": 2, "text": "Citation sentence."}],
            "revised_text": "Citation sentence.",
            "reason": "Removed authentication material from the provision mapping.",
        },
    )
    assert fixed.status_code == 200
    assert (
        next(
            issue
            for issue in fixed.json()["issues"]
            if issue["issue_type"] == "excluded_source_page"
        )["status"]
        == "resolved"
    )
    assert fixed.json()["source_document"]["verification_status"] != "verified"


def test_recover_missing_provision_preserves_origin_and_requires_review(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    original = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="142",
        canonical_path=f"recovery-{uuid.uuid4().hex}.section142",
        sort_key="142",
        raw_text="Citation sentence.\nSCHEDULE\nSchedule wording.",
        source_page_start=1,
        source_page_end=3,
    )
    db.add(original)
    db.commit()
    body = {
        "idempotency_key": f"recover-{uuid.uuid4().hex}",
        "expected_version": 1,
        "kind": "schedule",
        "number": "1",
        "heading": "SCHEDULE",
        "canonical_path": original.canonical_path.replace("section142", "schedule1"),
        "sort_key": "143",
        "source_page_start": 3,
        "source_page_end": 3,
        "source_spans": [
            {
                "page_number": 3,
                "text": "Schedule wording.",
                "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
            }
        ],
        "revised_text": "Schedule wording.",
        "reason": "Recovered the separate Schedule from the source scan.",
    }
    endpoint = f"{settings.API_V1_STR}/admin/review-items/{original.id}/derived-items"
    response = client.post(endpoint, headers=superuser_token_headers, json=body)
    assert response.status_code == 200
    recovered = response.json()
    assert recovered["id"] != str(original.id)
    assert recovered["status"] == "needs_review"
    assert recovered["kind"] == "schedule"
    assert recovered["raw_text"] == original.raw_text
    assert recovered["latest_revision_text"] == "Schedule wording."
    assert recovered["source_document"]["verification_status"] != "verified"
    assert (
        recovered["revisions"][0]["before_snapshot"]["canonical_path"]
        == original.canonical_path
    )
    assert recovered["revisions"][0]["changed_fields"][
        "derived_from_candidate_id"
    ] == str(original.id)
    repeated = client.post(endpoint, headers=superuser_token_headers, json=body)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == recovered["id"]
    duplicate = client.post(
        endpoint,
        headers=superuser_token_headers,
        json={**body, "idempotency_key": f"new-key-{uuid.uuid4().hex}"},
    )
    assert duplicate.status_code == 409
    db.expire_all()
    retained = db.get(ExtractionCandidate, original.id)
    assert retained and retained.lock_version == 1
    assert retained.raw_text == "Citation sentence.\nSCHEDULE\nSchedule wording."
    assert db.exec(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(recovered["id"]),
            AuditEvent.action == "review_item.derived",
        )
    ).first()


@pytest.mark.parametrize("kind", ["part", "chapter", "cross_heading", "section"])
def test_recovered_structure_does_not_inherit_origin_body(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    kind: str,
) -> None:
    source, run = _source_and_run(db)
    original = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        canonical_path=f"structural-{uuid.uuid4().hex}.section1",
        sort_key="001",
        raw_text="Original section body.",
        source_page_start=1,
        source_page_end=1,
    )
    db.add(original)
    db.commit()
    body = {
        "idempotency_key": f"recover-{uuid.uuid4().hex}",
        "expected_version": 1,
        "kind": kind,
        "heading": "PRINTED STRUCTURAL HEADING",
        "canonical_path": original.canonical_path.replace("section1", "structure"),
        "sort_key": "002",
        "source_page_start": 1,
        "source_page_end": 1,
        "source_spans": [{"page_number": 1, "text": "PRINTED STRUCTURAL HEADING"}],
        "reason": "Recover a printed structural heading without inventing body text.",
    }
    blank_heading = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{original.id}/derived-items",
        headers=superuser_token_headers,
        json={**body, "heading": "   "},
    )
    assert blank_heading.status_code == 422
    response = client.post(
        f"{settings.API_V1_STR}/admin/review-items/{original.id}/derived-items",
        headers=superuser_token_headers,
        json=body,
    )
    if kind == "section":
        assert response.status_code == 422
        return
    assert response.status_code == 200
    recovered = response.json()
    assert recovered["raw_text"] is None
    assert recovered["latest_revision_text"] is None
    assert recovered["status"] == "needs_review"
    assert recovered["revisions"][0]["previous_text"] == original.raw_text
    assert (
        recovered["revisions"][0]["before_snapshot"]["revised_text"]
        == original.raw_text
    )


def test_review_structure_patch_preserves_raw_and_audits_nullable_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="14",
        heading="Wrong heading",
        canonical_path=f"review-{uuid.uuid4().hex}.section14",
        sort_key="0014",
        raw_text="In this Act:",
        source_page_start=1,
        source_page_end=3,
    )
    db.add(candidate)
    db.commit()
    original = candidate.canonical_path
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"structure-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "number": "141",
            "heading": "Interpretation",
            "canonical_path": original.replace("section14", "section141"),
            "source_page_start": 2,
            "source_page_end": 3,
            "reason": "Compared the section marker and heading with the original scan.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["number"] == "141"
    assert payload["heading"] == "Interpretation"
    assert payload["raw_text"] == "In this Act:"
    assert payload["latest_revision_text"] == "In this Act:"
    assert payload["revisions"][0]["before_snapshot"]["number"] == "14"
    assert payload["revisions"][0]["after_snapshot"]["number"] == "141"
    clear = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"clear-{uuid.uuid4().hex}",
            "expected_version": payload["lock_version"],
            "heading": None,
            "reason": "Remove an unsupported heading pending source review.",
        },
    )
    assert clear.status_code == 200
    assert clear.json()["heading"] is None
    parent = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.PART,
        canonical_path=f"review-parent-{uuid.uuid4().hex}",
        sort_key="0013",
        heading="Printed Part heading",
        source_page_start=2,
        source_page_end=2,
    )
    db.add(parent)
    db.commit()
    reparented = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"reparent-{uuid.uuid4().hex}",
            "expected_version": clear.json()["lock_version"],
            "parent_candidate_id": str(parent.id),
            "reason": "Recover the distinct printed parent structure.",
        },
    )
    assert reparented.status_code == 200
    assert reparented.json()["parent_candidate_id"] == str(parent.id)
    latest = max(
        reparented.json()["revisions"], key=lambda item: item["revision_number"]
    )
    assert latest["changed_fields"]["parent_candidate_id"] == str(parent.id)


@pytest.mark.parametrize(
    "invalid",
    [
        "duplicate",
        "cycle",
        "foreign_parent",
        "page_range",
        "span_range",
        "materialized",
    ],
)
def test_review_structure_patch_rejects_invalid_graph_changes(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    invalid: str,
) -> None:
    source, run = _source_and_run(db)
    other_source, other_run = _source_and_run(db)
    prefix = f"review-{uuid.uuid4().hex}"
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="1",
        canonical_path=f"{prefix}.section1",
        sort_key="001",
        raw_text="Original wording.",
        source_page_start=2,
        source_page_end=3,
    )
    sibling = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="2",
        canonical_path=f"{prefix}.section2",
        sort_key="002",
    )
    foreign = ExtractionCandidate(
        run_id=other_run.id,
        source_document_id=other_source.id,
        kind=ProvisionKind.SECTION,
        number="3",
        canonical_path=f"{prefix}.section3",
        sort_key="003",
    )
    db.add_all([candidate, sibling, foreign])
    db.commit()
    patches: dict[str, dict[str, object]] = {
        "duplicate": {"canonical_path": sibling.canonical_path},
        "cycle": {"parent_candidate_id": str(candidate.id)},
        "foreign_parent": {"parent_candidate_id": str(foreign.id)},
        "page_range": {"source_page_start": 4},
        "span_range": {"source_spans": [{"page_number": 1, "text": "outside range"}]},
        "materialized": {"heading": "Cannot alter a materialized candidate"},
    }
    if invalid == "materialized":
        candidate.status = ExtractionCandidateStatus.MATERIALIZED
        db.add(candidate)
        db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/admin/review-items/{candidate.id}",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"invalid-{uuid.uuid4().hex}",
            "expected_version": candidate.lock_version,
            "reason": "Attempt invalid structure edit",
            **patches[invalid],
        },
    )
    assert response.status_code in {409, 422}
    db.expire_all()
    retained = db.get(ExtractionCandidate, candidate.id)
    assert retained
    assert retained.canonical_path == f"{prefix}.section1"
    assert retained.lock_version == 1
    assert not db.exec(
        select(CandidateRevision).where(CandidateRevision.candidate_id == candidate.id)
    ).all()
