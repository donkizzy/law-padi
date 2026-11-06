import uuid

import pytest
from sqlmodel import Session

from app.legal.enums import EvaluationDatasetKind
from app.legal.models import EvaluationDataset
from scripts.load_retrieval_benchmark import retire_superseded


def _dataset(db: Session, slug: str) -> EvaluationDataset:
    dataset = EvaluationDataset(
        version=f"test-{uuid.uuid4().hex}",
        name="Test benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        instrument_slug=slug,
    )
    db.add(dataset)
    db.commit()
    return dataset


def test_superseding_marks_only_the_older_dataset_inactive(db: Session) -> None:
    older, newer = _dataset(db, "test-act"), _dataset(db, "test-act")
    retire_superseded(
        db,
        version=older.version,
        instrument_slug="test-act",
        loaded_version=newer.version,
    )
    db.refresh(older)
    db.refresh(newer)
    assert older.is_active is False
    assert newer.is_active is True


def test_superseding_refuses_another_instrument_or_itself(db: Session) -> None:
    other = _dataset(db, "other-act")
    with pytest.raises(ValueError, match="another instrument"):
        retire_superseded(
            db,
            version=other.version,
            instrument_slug="test-act",
            loaded_version="test-new",
        )
    with pytest.raises(ValueError, match="supersede itself"):
        retire_superseded(
            db,
            version=other.version,
            instrument_slug="other-act",
            loaded_version=other.version,
        )
    db.refresh(other)
    assert other.is_active is True
