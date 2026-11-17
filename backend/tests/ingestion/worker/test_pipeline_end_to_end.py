import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.runtime.runner import run_until_idle
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    IngestionRunStatus,
    IngestionStage,
    InstrumentStatus,
    PageInclusionStatus,
    ReviewDecisionType,
    SourceTier,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    IngestionRun,
    Provision,
    ProvisionVersion,
    ReleasePromotionAttempt,
    SourceDocument,
    SourcePage,
    SourceUpload,
)
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.factories.pdf import sha256 as _sha256
from tests.ingestion.worker.conftest import _create_retrieval_benchmark_dataset
from tests.utils.legal import register_fixture_citation_names


def test_api_upload_worker_publish_and_production_search_end_to_end(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise one source across the real API, worker, release, and search paths."""
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "RETRIEVAL_INDEX_BACKEND", "pgvector")

    for profile in db.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active == True)  # noqa: E712
    ).all():
        profile.is_active = False
        db.add(profile)
    db.commit()

    pdf = _pdf_with_pages(
        [
            "37. Right to private and family life. The privacy of citizens, their homes and correspondence is guaranteed."
        ]
    )
    slug = f"constitution-e2e-{uuid.uuid4().hex}"
    register_fixture_citation_names(slug)
    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"upload-{uuid.uuid4().hex}",
            "expected_size": len(pdf),
            "expected_sha256": _sha256(pdf),
            "original_filename": "constitution.pdf",
            "mime_type": "application/pdf",
            "instrument_slug": slug,
            "instrument_title": "Constitution of the Federal Republic of Nigeria 1999",
            "instrument_short_title": "CFRN 1999",
            "instrument_year": 1999,
            "instrument_status": InstrumentStatus.ENACTED.value,
            "enacted_at": "1999-05-29",
            "effective_at": "1999-05-29",
            "source_title": "Official Constitution PDF",
            "authority": "Official Gazette",
            "source_url": f"https://example.test/{slug}.pdf",
            "source_tier": SourceTier.OFFICIAL.value,
            "published_at": "1999-05-29",
            "retrieved_at": date.today().isoformat(),
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    upload = upload_response.json()
    upload_id = uuid.UUID(upload["id"])
    put_response = client.put(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/object",
        headers={**superuser_token_headers, "content-type": "application/pdf"},
        content=pdf,
    )
    assert put_response.status_code == 204, put_response.text
    upload_record = db.get(SourceUpload, upload_id)
    assert upload_record
    db.refresh(upload_record)
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": upload_record.lock_version,
            "actual_sha256": _sha256(pdf),
        },
    )
    assert complete_response.status_code == 200, complete_response.text
    completion = complete_response.json()
    assert completion["source_document"] is None
    run_id = uuid.UUID(completion["run"]["id"])

    first_results = run_until_idle(db, worker_id="e2e-worker", max_tasks=20)
    assert first_results
    run = db.get(IngestionRun, run_id)
    assert run
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    source = db.exec(
        select(SourceDocument).where(SourceDocument.id == run.source_document_id)
    ).one()
    pages = db.exec(
        select(SourcePage)
        .where(SourcePage.run_id == run.id)
        .order_by(SourcePage.page_number)
    ).all()
    assert pages
    page_selection = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"pages-{uuid.uuid4().hex}",
            "expected_run_version": run.lock_version,
            "pages": [
                {
                    "page_number": page.page_number,
                    "inclusion_status": PageInclusionStatus.INCLUDED.value,
                    "inclusion_reason": "Included by end-to-end acceptance test",
                    "expected_version": page.lock_version,
                }
                for page in pages
            ],
        },
    )
    assert page_selection.status_code == 200, page_selection.text

    run_until_idle(db, worker_id="e2e-worker", max_tasks=30)
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    review_response = client.get(
        f"{settings.API_V1_STR}/admin/review-items",
        headers=superuser_token_headers,
        params={"run_id": str(run.id)},
    )
    assert review_response.status_code == 200, review_response.text
    review_items = review_response.json()["data"]
    assert review_items
    for item in review_items:
        decision_response = client.post(
            f"{settings.API_V1_STR}/admin/review-items/{item['id']}/decision",
            headers=superuser_token_headers,
            json={
                "idempotency_key": f"approve-{item['id']}-{uuid.uuid4().hex}",
                "expected_version": item["lock_version"],
                "decision": ReviewDecisionType.APPROVE.value,
                "reason": "Approved by end-to-end acceptance test",
            },
        )
        assert decision_response.status_code == 200, decision_response.text

    db.refresh(source)
    verify_response = client.post(
        f"{settings.API_V1_STR}/admin/source-documents/{source.id}/verify",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"verify-{uuid.uuid4().hex}",
            "expected_version": source.lock_version,
            "reason": "Official source reviewed by end-to-end acceptance test",
        },
    )
    assert verify_response.status_code == 200, verify_response.text

    run_until_idle(db, worker_id="e2e-worker", max_tasks=30)
    db.refresh(run)
    assert run.status == IngestionRunStatus.READY_TO_EMBED
    release = db.exec(
        select(CorpusRelease)
        .join(CorpusReleaseEntry)
        .where(CorpusReleaseEntry.ingestion_run_id == run.id)
    ).one()
    version = db.exec(
        select(ProvisionVersion).where(ProvisionVersion.source_document_id == source.id)
    ).one()
    provision = db.get(Provision, version.provision_id)
    assert provision

    benchmark_version = f"e2e-retrieval-{uuid.uuid4().hex}"
    _create_retrieval_benchmark_dataset(
        db, version=benchmark_version, canonical_path=provision.canonical_path
    )
    profile = EmbeddingProfile(
        name=f"e2e-profile-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="fake-e2e",
        model_revision="pinned-e2e",
        vector_dimensions=1024,
        is_active=True,
        configuration={"benchmark_dataset_version": benchmark_version},
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    class FakeEmbeddingProvider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            return EmbeddingBatch(
                provider="fake",
                model_name="fake-e2e",
                model_revision="pinned-e2e",
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
                cost_usd=0.01 * len(texts),
            )

    monkeypatch.setattr(
        "app.ingestion.stages.embedding.embedding_provider_for_profile",
        lambda _profile: FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(
        "app.api.routes.search._query_embedding_provider",
        lambda _profile: FakeEmbeddingProvider(),
    )
    db.refresh(run)
    start_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/start-embedding",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"start-embedding-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
        },
    )
    assert start_response.status_code == 200, start_response.text
    embedding_results = run_until_idle(db, worker_id="e2e-worker", max_tasks=5)
    assert [result.stage for result in embedding_results] == [
        IngestionStage.EMBEDDING,
        IngestionStage.INDEXING,
        IngestionStage.VALIDATING_INDEX,
    ]
    db.refresh(run)
    db.refresh(release)
    assert run.status == IngestionRunStatus.READY_TO_PUBLISH
    assert release.status in {
        CorpusReleaseStatus.BUILDING,
        CorpusReleaseStatus.VALIDATING,
    }

    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert validate_response.status_code == 200, validate_response.text
    assert validate_response.json()["status"] == CorpusReleaseStatus.APPROVED.value
    db.refresh(release)
    expected_release_version = release.lock_version

    def publish_once() -> int:
        response = client.post(
            f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
            headers=superuser_token_headers,
            json={
                "idempotency_key": f"publish-{uuid.uuid4().hex}",
                "expected_version": expected_release_version,
                "superuser_override_reason": "Acceptance test actor-separation override",
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        publish_statuses = list(executor.map(lambda _index: publish_once(), range(2)))
    assert sorted(publish_statuses) == [200, 409]

    db.refresh(run)
    db.refresh(release)
    assert run.status == IngestionRunStatus.PUBLISHED
    assert release.status == CorpusReleaseStatus.PRODUCTION
    assert db.exec(
        select(ActiveRetrievalTarget).where(
            ActiveRetrievalTarget.release_id == release.id,
            ActiveRetrievalTarget.index_kind == "enacted",
        )
    ).one()
    assert (
        db.exec(
            select(ReleasePromotionAttempt).where(
                ReleasePromotionAttempt.release_id == release.id
            )
        )
        .one()
        .status
        == "succeeded"
    )

    search_response = client.post(
        f"{settings.API_V1_STR}/legal/search",
        json={"query": "Which section protects privacy?", "top_k": 1},
    )
    assert search_response.status_code == 200, search_response.text
    result = search_response.json()["data"][0]
    assert result["canonical_path"] == provision.canonical_path
    assert result["authoritative_text"] == version.text
    assert result["source_document_id"] == str(source.id)
