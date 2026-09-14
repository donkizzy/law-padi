import uuid

from sqlmodel import Session

from app.ingestion.evaluation import (
    active_evaluation_item_count,
    load_gold_provisions_for_dataset,
    load_retrieval_evaluation_queries,
)
from app.legal.enums import EvaluationDatasetKind, EvaluationItemKind, ProvisionKind
from app.legal.models import EvaluationDataset, EvaluationItem


def test_load_gold_provisions_from_active_legal_grade_dataset(db: Session) -> None:
    dataset = EvaluationDataset(
        version=f"gold-{uuid.uuid4().hex}",
        name="Constitution gold provisions",
        dataset_kind=EvaluationDatasetKind.LEGAL_GRADE_EXTRACTION,
        language="en",
        jurisdiction="NG",
        content_sha256="a" * 64,
    )
    inactive_dataset = EvaluationDataset(
        version=f"inactive-gold-{uuid.uuid4().hex}",
        name="Inactive gold provisions",
        dataset_kind=EvaluationDatasetKind.LEGAL_GRADE_EXTRACTION,
        language="en",
        jurisdiction="NG",
        is_active=False,
    )
    db.add_all([dataset, inactive_dataset])
    db.commit()
    db.refresh(dataset)
    db.refresh(inactive_dataset)

    db.add_all(
        [
            EvaluationItem(
                dataset_id=dataset.id,
                item_key="section-37",
                item_kind=EvaluationItemKind.GOLD_PROVISION,
                canonical_path="constitution.1999.chapter4.section37",
                provision_kind=ProvisionKind.SECTION,
                section_number="37",
                expected_text="The privacy of citizens is hereby guaranteed.",
                source_page_start=22,
                source_page_end=22,
                source_spans=[
                    {
                        "page_number": 22,
                        "bbox": {
                            "x0": 36.0,
                            "y0": 420.0,
                            "x1": 260.0,
                            "y1": 446.0,
                        },
                    }
                ],
            ),
            EvaluationItem(
                dataset_id=inactive_dataset.id,
                item_key="section-38",
                item_kind=EvaluationItemKind.GOLD_PROVISION,
                canonical_path="constitution.1999.chapter4.section38",
                expected_text="Every person shall be entitled to freedom of thought.",
            ),
        ]
    )
    db.commit()

    gold = load_gold_provisions_for_dataset(db, dataset.version)

    assert len(gold) == 1
    assert gold[0].canonical_path == "constitution.1999.chapter4.section37"
    assert gold[0].section_number == "37"
    assert gold[0].source_page_start == 22
    assert gold[0].source_spans == [
        {
            "page_number": 22,
            "bbox": {"x0": 36.0, "y0": 420.0, "x1": 260.0, "y1": 446.0},
        }
    ]
    assert load_gold_provisions_for_dataset(db, inactive_dataset.version) == []


def test_retrieval_benchmark_queries_and_counts_require_active_dataset(
    db: Session,
) -> None:
    dataset = EvaluationDataset(
        version=f"retrieval-{uuid.uuid4().hex}",
        name="Constitution retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        language="en",
        jurisdiction="NG",
    )
    wrong_kind_dataset = EvaluationDataset(
        version=f"ocr-{uuid.uuid4().hex}",
        name="OCR benchmark",
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
        language="en",
        jurisdiction="NG",
    )
    db.add_all([dataset, wrong_kind_dataset])
    db.commit()
    db.refresh(dataset)
    db.refresh(wrong_kind_dataset)

    db.add_all(
        [
            EvaluationItem(
                dataset_id=dataset.id,
                item_key="privacy-query",
                item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
                query_text="Which provision protects privacy?",
                expected_canonical_paths=["constitution.1999.chapter4.section37"],
                item_metadata={"variant": "exact-reference"},
            ),
            EvaluationItem(
                dataset_id=wrong_kind_dataset.id,
                item_key="ocr-page-1",
                item_kind=EvaluationItemKind.OCR_PAGE,
                source_page_start=1,
                source_page_end=1,
            ),
        ]
    )
    db.commit()

    queries = load_retrieval_evaluation_queries(db, dataset.version)

    assert len(queries) == 1
    assert queries[0].item_key == "privacy-query"
    assert queries[0].expected_canonical_paths == [
        "constitution.1999.chapter4.section37"
    ]
    assert queries[0].metadata == {"variant": "exact-reference"}
    assert (
        active_evaluation_item_count(
            db,
            dataset.version,
            dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
        )
        == 1
    )
    assert (
        active_evaluation_item_count(
            db,
            wrong_kind_dataset.version,
            dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
        )
        == 0
    )
