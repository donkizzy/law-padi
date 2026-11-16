import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.legal.enums import (
    EvaluationDatasetKind,
    EvaluationItemKind,
)
from app.legal.models import (
    EvaluationDataset,
    EvaluationItem,
)


def test_ocr_benchmark_evaluate_scores_providers(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    dataset = EvaluationDataset(
        version=f"ocr-bench-{uuid.uuid4().hex}",
        name="OCR bench",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
        is_active=True,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="page-1",
            item_kind=EvaluationItemKind.OCR_PAGE,
            expected_text="Right to private and family life",
        )
    )
    db.commit()
    response = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{dataset.version}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": dataset.version,
            "samples": [
                {
                    "item_key": "page-1",
                    "provider": "google_document_ai",
                    "text": "Right to private and family life",
                },
                {
                    "item_key": "page-1",
                    "provider": "azure_document_intelligence",
                    "text": "Right to private and family live",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["winner"] == "google_document_ai"
    assert body["sample_count"] == 1


def test_ocr_benchmark_read_reports_dataset_counts(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    version = f"ocr-read-{uuid.uuid4().hex}"
    dataset = EvaluationDataset(
        version=version,
        name="OCR read bench",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
        is_active=True,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="page-1",
            item_kind=EvaluationItemKind.OCR_PAGE,
            expected_text="Section 37",
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{version}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 1
    assert body["active_dataset_items"] == 1
    assert body["winner"] is None


def test_ocr_benchmark_evaluate_rejects_bad_requests(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    version = f"ocr-bad-{uuid.uuid4().hex}"
    dataset = EvaluationDataset(
        version=version,
        name="OCR bad bench",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
        is_active=True,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="page-1",
            item_kind=EvaluationItemKind.OCR_PAGE,
            expected_text="Section 37",
        )
    )
    db.commit()

    mismatch = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{version}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": "other-version",
            "samples": [],
        },
    )
    assert mismatch.status_code == 400

    unknown_provider = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/{version}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": version,
            "samples": [
                {
                    "item_key": "page-1",
                    "provider": "mystery_ocr",
                    "text": "Section 37",
                }
            ],
        },
    )
    assert unknown_provider.status_code == 400

    missing = client.post(
        f"{settings.API_V1_STR}/admin/ocr-benchmarks/missing-{uuid.uuid4().hex}/evaluate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"ocr-{uuid.uuid4().hex}",
            "expected_version": 1,
            "dataset_version": "missing-version",
            "samples": [],
        },
    )
    assert missing.status_code in (400, 404)
