from app.ingestion.quality import (
    ExtractedProvision,
    GoldProvision,
    evaluate_legal_grade_quality,
)
from app.legal.enums import ProvisionKind

SOURCE_SPAN = {
    "page_number": 12,
    "bbox": {"x0": 36.0, "y0": 120.0, "x1": 260.0, "y1": 144.0},
}


def test_legal_grade_quality_passes_for_exact_gold_section_coverage() -> None:
    report = evaluate_legal_grade_quality(
        gold_dataset_version="ng-constitution-gold-v1",
        gold_provisions=[
            GoldProvision(
                canonical_path="constitution.1999.chapter4.section37",
                section_number="37",
                text="Right to private and family life",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
        extracted_provisions=[
            ExtractedProvision(
                canonical_path="constitution.1999.chapter4.section37",
                kind=ProvisionKind.SECTION,
                number="37",
                text="Right to private and family life",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
    )

    assert report.passed is True
    assert report.character_accuracy == 1.0
    assert report.meaning_changing_token_errors == 0
    assert report.complete_section_number_coverage is True
    assert report.complete_source_coordinate_coverage is True
    assert report.source_coordinate_assertion_count == 1
    assert report.to_policy_metrics()["metrics_source"] == "computed_gold_evaluation"


def test_legal_grade_quality_fails_for_missing_gold_provisions() -> None:
    report = evaluate_legal_grade_quality(
        gold_dataset_version="ng-constitution-gold-v1",
        gold_provisions=[
            GoldProvision(
                canonical_path="constitution.1999.chapter4.section37",
                text="The privacy of citizens is hereby guaranteed and protected.",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
        extracted_provisions=[],
    )

    assert report.passed is False
    assert report.missing_canonical_paths == ["constitution.1999.chapter4.section37"]
    assert report.character_accuracy == 0
    assert report.meaning_changing_token_errors >= 1
    assert report.complete_section_number_coverage is False
    assert report.complete_source_coordinate_coverage is False


def test_legal_grade_quality_fails_on_meaning_changing_token_errors() -> None:
    report = evaluate_legal_grade_quality(
        gold_dataset_version="ng-constitution-gold-v1",
        gold_provisions=[
            GoldProvision(
                canonical_path="constitution.1999.chapter4.section37",
                text="No citizen shall be denied privacy.",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
        extracted_provisions=[
            ExtractedProvision(
                canonical_path="constitution.1999.chapter4.section37",
                kind=ProvisionKind.SECTION,
                number="37",
                text="A citizen may be denied privacy.",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
        min_character_accuracy=0,
    )

    assert report.passed is False
    assert report.meaning_changing_token_errors >= 1
    assert report.complete_section_number_coverage is True
    assert report.complete_source_coordinate_coverage is True


def test_legal_grade_quality_fails_when_gold_lacks_source_coordinates() -> None:
    report = evaluate_legal_grade_quality(
        gold_dataset_version="ng-constitution-gold-v1",
        gold_provisions=[
            GoldProvision(
                canonical_path="constitution.1999.chapter4.section37",
                text="The privacy of citizens is hereby guaranteed.",
                section_number="37",
            )
        ],
        extracted_provisions=[
            ExtractedProvision(
                canonical_path="constitution.1999.chapter4.section37",
                kind=ProvisionKind.SECTION,
                number="37",
                text="The privacy of citizens is hereby guaranteed.",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
    )

    assert report.passed is False
    assert report.missing_source_coordinate_paths == [
        "constitution.1999.chapter4.section37"
    ]


def test_legal_grade_quality_fails_on_source_coordinate_mismatch() -> None:
    report = evaluate_legal_grade_quality(
        gold_dataset_version="ng-constitution-gold-v1",
        gold_provisions=[
            GoldProvision(
                canonical_path="constitution.1999.chapter4.section37",
                text="The privacy of citizens is hereby guaranteed.",
                section_number="37",
                source_page_start=12,
                source_page_end=12,
                source_spans=[SOURCE_SPAN],
            )
        ],
        extracted_provisions=[
            ExtractedProvision(
                canonical_path="constitution.1999.chapter4.section37",
                kind=ProvisionKind.SECTION,
                number="37",
                text="The privacy of citizens is hereby guaranteed.",
                source_page_start=12,
                source_page_end=12,
                source_spans=[
                    {
                        "page_number": 12,
                        "bbox": {
                            "x0": 36.0,
                            "y0": 180.0,
                            "x1": 260.0,
                            "y1": 204.0,
                        },
                    }
                ],
            )
        ],
    )

    assert report.passed is False
    assert report.complete_source_coordinate_coverage is False
    assert report.source_coordinate_errors == [
        {
            "canonical_path": "constitution.1999.chapter4.section37",
            "reason": "source_span_missing",
            "expected": {
                "page_number": 12,
                "bbox": [36.0, 120.0, 260.0, 144.0],
            },
        }
    ]
