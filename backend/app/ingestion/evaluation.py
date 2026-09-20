from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, col, func, select

from app.ingestion.quality import GoldProvision
from app.legal.enums import EvaluationDatasetKind, EvaluationItemKind
from app.legal.models import EvaluationDataset, EvaluationItem


@dataclass(frozen=True)
class RetrievalEvaluationQuery:
    item_key: str
    query_text: str
    expected_canonical_paths: list[str]
    language: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class OcrEvaluationPage:
    item_key: str
    expected_text: str
    metadata: dict[str, Any]


def load_gold_provisions_for_dataset(
    session: Session, dataset_version: str
) -> list[GoldProvision]:
    dataset = _active_dataset(
        session,
        version=dataset_version,
        dataset_kind=EvaluationDatasetKind.LEGAL_GRADE_EXTRACTION,
    )
    if not dataset:
        return []
    items = session.exec(
        select(EvaluationItem)
        .where(
            EvaluationItem.dataset_id == dataset.id,
            EvaluationItem.item_kind == EvaluationItemKind.GOLD_PROVISION,
        )
        .order_by(col(EvaluationItem.item_key))
    ).all()
    return [
        GoldProvision(
            canonical_path=str(item.canonical_path),
            text=str(item.expected_text),
            section_number=item.section_number,
            source_page_start=item.source_page_start,
            source_page_end=item.source_page_end,
            source_spans=item.source_spans,
        )
        for item in items
        if item.canonical_path and item.expected_text
    ]


def load_retrieval_evaluation_queries(
    session: Session, dataset_version: str
) -> list[RetrievalEvaluationQuery]:
    dataset = _active_dataset(
        session,
        version=dataset_version,
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
    )
    if not dataset:
        return []
    items = session.exec(
        select(EvaluationItem)
        .where(
            EvaluationItem.dataset_id == dataset.id,
            EvaluationItem.item_kind == EvaluationItemKind.RETRIEVAL_QUERY,
        )
        .order_by(col(EvaluationItem.item_key))
    ).all()
    queries: list[RetrievalEvaluationQuery] = []
    for item in items:
        expected_paths = item.expected_canonical_paths
        if not item.query_text or not isinstance(expected_paths, list):
            continue
        paths = [path for path in expected_paths if isinstance(path, str)]
        if not paths:
            continue
        queries.append(
            RetrievalEvaluationQuery(
                item_key=item.item_key,
                query_text=item.query_text,
                expected_canonical_paths=paths,
                language=dataset.language,
                metadata=item.item_metadata or {},
            )
        )
    return queries


def load_ocr_evaluation_pages(
    session: Session, dataset_version: str
) -> list[OcrEvaluationPage]:
    dataset = _active_dataset(
        session,
        version=dataset_version,
        dataset_kind=EvaluationDatasetKind.OCR_BENCHMARK,
    )
    if not dataset:
        return []
    items = session.exec(
        select(EvaluationItem)
        .where(
            EvaluationItem.dataset_id == dataset.id,
            EvaluationItem.item_kind == EvaluationItemKind.OCR_PAGE,
        )
        .order_by(col(EvaluationItem.item_key))
    ).all()
    pages: list[OcrEvaluationPage] = []
    for item in items:
        if not item.expected_text:
            continue
        pages.append(
            OcrEvaluationPage(
                item_key=item.item_key,
                expected_text=item.expected_text,
                metadata=item.item_metadata or {},
            )
        )
    return pages


def active_evaluation_item_count(
    session: Session,
    dataset_version: str,
    *,
    dataset_kind: EvaluationDatasetKind,
    item_kind: EvaluationItemKind,
) -> int:
    dataset = _active_dataset(
        session, version=dataset_version, dataset_kind=dataset_kind
    )
    if not dataset:
        return 0
    count = session.exec(
        select(func.count())
        .select_from(EvaluationItem)
        .where(
            EvaluationItem.dataset_id == dataset.id,
            EvaluationItem.item_kind == item_kind,
        )
    ).one()
    return int(count or 0)


def _active_dataset(
    session: Session,
    *,
    version: str,
    dataset_kind: EvaluationDatasetKind,
) -> EvaluationDataset | None:
    return session.exec(
        select(EvaluationDataset).where(
            EvaluationDataset.version == version,
            EvaluationDataset.dataset_kind == dataset_kind,
            EvaluationDataset.is_active == True,  # noqa: E712
        )
    ).first()
