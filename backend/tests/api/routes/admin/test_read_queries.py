"""Admin reads keep a constant number of round trips as their result sets grow."""

import uuid
from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    IngestionArtifactType,
    ProvisionKind,
    ReviewDecisionType,
    ReviewIssueSeverity,
)
from app.legal.models import (
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    ExtractionCandidate,
    IngestionArtifact,
    Provision,
    ProvisionVersion,
    ReviewDecisionRecord,
    ReviewIssue,
    SourcePage,
)
from tests.api.routes.admin.conftest import (
    _retire_existing_production_release,
    _source_and_run,
    _superuser,
)
from tests.factories.pdf import sha256_text

API = settings.API_V1_STR


def _query_count(call: Callable[[], object]) -> int:
    statements = []

    def record(*args: object) -> None:
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(statements)


def test_review_and_page_queries_stay_constant(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    source, run = _source_and_run(db)
    run_id, source_id = run.id, source.id
    actor_id = _superuser(db).id
    expected: dict[str, tuple[str, str]] = {}

    def add_candidate(number: int) -> None:
        page = SourcePage(
            run_id=run_id, source_document_id=source_id, page_number=number
        )
        candidate = ExtractionCandidate(
            run_id=run_id,
            source_document_id=source_id,
            kind=ProvisionKind.SECTION,
            canonical_path=f"query-test-{uuid.uuid4().hex}",
            sort_key=str(number),
            raw_text="Original",
            normalized_text="Original",
            source_page_start=number,
        )
        db.add_all([page, candidate])
        db.flush()
        artifact = IngestionArtifact(
            run_id=run_id,
            source_page_id=page.id,
            artifact_type=IngestionArtifactType.PAGE_THUMBNAIL,
            storage_key=f"thumb-{uuid.uuid4().hex}.png",
            mime_type="image/png",
        )
        db.add(artifact)
        for revision_number in (1, 2):
            db.add(
                CandidateRevision(
                    candidate_id=candidate.id,
                    revision_number=revision_number,
                    revised_text=f"Revision {revision_number}",
                    reason="Reviewed",
                    revised_by=actor_id,
                )
            )
        db.add(
            ReviewIssue(
                candidate_id=candidate.id,
                issue_type="query-count",
                severity=ReviewIssueSeverity.LOW,
                message="Review",
            )
        )
        db.add(
            ReviewDecisionRecord(
                candidate_id=candidate.id,
                decision=ReviewDecisionType.APPROVE,
                reason="Reviewed",
                decided_by=actor_id,
            )
        )
        db.commit()
        expected[str(candidate.id)] = (str(artifact.id), str(page.id))

    def read_reviews() -> None:
        response = client.get(
            f"{API}/admin/review-items?run_id={run_id}", headers=superuser_token_headers
        )
        assert response.status_code == 200
        rows = response.json()["data"]
        assert len(rows) == len(expected)
        for row in rows:
            assert row["latest_revision_text"] == "Revision 2"
            assert [r["revision_number"] for r in row["revisions"]] == [1, 2]
            assert len(row["issues"]) == len(row["decisions"]) == 1
            assert row["source_document"]["id"] == str(source_id)
            assert expected[row["id"]][0] in row["source_page_thumbnail_url"]

    def read_pages() -> None:
        response = client.get(
            f"{API}/admin/ingestion-runs/{run_id}/pages",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        rows = response.json()["data"]
        assert len(rows) == len(expected)
        thumbnails = {
            page_id: artifact_id for artifact_id, page_id in expected.values()
        }
        for row in rows:
            assert thumbnails[row["id"]] in row["thumbnail_url"]

    add_candidate(1)
    small = (_query_count(read_reviews), _query_count(read_pages))
    for number in range(2, 7):
        add_candidate(number)
    large = (_query_count(read_reviews), _query_count(read_pages))
    assert small == large
    assert large[0] <= 9
    assert large[1] <= 3


def test_release_and_benchmark_queries_stay_constant(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    source, run = _source_and_run(db)
    source_id, run_id, instrument_id = source.id, run.id, source.legal_instrument_id
    _retire_existing_production_release(db)
    production = CorpusRelease(
        version=f"query-test-{uuid.uuid4().hex}",
        status=CorpusReleaseStatus.PRODUCTION,
        source_manifest_hash="a" * 64,
        parser_version="test",
    )
    db.add(production)
    db.commit()
    production_id = production.id
    expected_versions: set[str] = set()
    expected_profiles: set[str] = set()

    def add_rows(number: int) -> None:
        provision = Provision(
            instrument_id=instrument_id,
            kind=ProvisionKind.SECTION,
            canonical_path=f"query-test-{uuid.uuid4().hex}",
            sort_key=str(number),
        )
        profile = EmbeddingProfile(
            name=f"query-test-{uuid.uuid4().hex}",
            provider=EmbeddingProviderKind.OPENAI,
            model_name="test",
            model_revision="test",
            vector_dimensions=1024,
        )
        release = CorpusRelease(
            version=f"query-test-{uuid.uuid4().hex}",
            source_manifest_hash="b" * 64,
            parser_version="test",
        )
        db.add_all([provision, profile, release])
        db.flush()
        version = ProvisionVersion(
            provision_id=provision.id,
            text="Text",
            normalized_text="Text",
            valid_from=date(2000, 1, 1),
            source_document_id=source_id,
            text_sha256=sha256_text("Text"),
        )
        db.add(version)
        db.flush()
        for release_id in (production_id, release.id):
            db.add(
                CorpusReleaseEntry(
                    release_id=release_id,
                    provision_version_id=version.id,
                    source_document_id=source_id,
                    ingestion_run_id=run_id,
                )
            )
        db.add(EmbeddingRun(release_id=production_id, profile_id=profile.id))
        db.commit()
        expected_versions.add(str(version.id))
        expected_profiles.add(str(profile.id))

    def read_releases() -> None:
        response = client.get(
            f"{API}/admin/corpus-releases?limit=200", headers=superuser_token_headers
        )
        assert response.status_code == 200
        row = next(
            row for row in response.json()["data"] if row["id"] == str(production_id)
        )
        assert row["evidence_count"] == len(expected_versions)
        assert len(row["instrument_slugs"]) == len(row["instrument_types"]) == 1

    def read_benchmark() -> None:
        response = client.get(
            f"{API}/admin/embedding-benchmarks/{production_id}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        assert {
            row["profile_id"] for row in response.json()["results"]
        } == expected_profiles

    def read_production() -> None:
        response = client.get(
            f"{API}/admin/corpus-releases/production/provision-versions",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        assert {row["id"] for row in response.json()["data"]} == expected_versions

    add_rows(1)
    reads = (read_releases, read_benchmark, read_production)
    small = tuple(_query_count(read) for read in reads)
    for number in range(2, 6):
        add_rows(number)
    large = tuple(_query_count(read) for read in reads)
    assert small == large
    assert max(large) <= 5
    first = client.get(
        f"{API}/admin/corpus-releases/production/provision-versions?limit=2",
        headers=superuser_token_headers,
    ).json()
    second = client.get(
        f"{API}/admin/corpus-releases/production/provision-versions?limit=2&skip=2",
        headers=superuser_token_headers,
    ).json()
    assert first["count"] == second["count"] == 5
    assert len(first["data"]) == len(second["data"]) == 2
    assert {row["id"] for row in first["data"]}.isdisjoint(
        row["id"] for row in second["data"]
    )


def test_metrics_use_one_read(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    def read() -> None:
        response = client.get(f"{API}/admin/metrics", headers=superuser_token_headers)
        assert response.status_code == 200

    assert _query_count(read) == 2  # Authenticate the user, then read the metrics.


@pytest.mark.parametrize(
    "path",
    [
        "/users/",
        "/admin/audit-events",
        "/admin/ingestion-runs",
        "/admin/review-items",
        "/admin/corpus-releases",
        "/admin/corpus-releases/production/provision-versions",
    ],
)
@pytest.mark.parametrize("limit", [0, -1, 201])
def test_list_limits_are_bounded(
    client: TestClient, superuser_token_headers: dict[str, str], path: str, limit: int
) -> None:
    response = client.get(
        f"{API}{path}", params={"limit": limit}, headers=superuser_token_headers
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/users/",
        "/admin/ingestion-runs",
        "/admin/review-items",
        "/admin/corpus-releases",
        "/admin/corpus-releases/production/provision-versions",
    ],
)
def test_list_offsets_cannot_be_negative(
    client: TestClient, superuser_token_headers: dict[str, str], path: str
) -> None:
    assert (
        client.get(f"{API}{path}?skip=-1", headers=superuser_token_headers).status_code
        == 422
    )
