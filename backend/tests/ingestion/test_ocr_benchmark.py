from app.ingestion.ocr_benchmark import (
    OcrBenchmarkSample,
    character_accuracy,
    evaluate_ocr_benchmark,
)


def test_character_accuracy_scores_exact_and_empty() -> None:
    assert character_accuracy("Section 37", "Section 37") == 1.0
    assert character_accuracy("", "") == 1.0
    assert character_accuracy("abc", "") == 0.0
    assert 0 < character_accuracy("Section 37", "Section 38") < 1.0


def test_ocr_benchmark_selects_more_accurate_provider() -> None:
    samples = [
        OcrBenchmarkSample(
            item_key="page-1",
            expected_text="Right to private and family life",
            provider_texts={
                "google_document_ai": "Right to private and family life",
                "azure_document_intelligence": "Right to private and family live",
            },
            provider_cost_usd={
                "google_document_ai": 0.02,
                "azure_document_intelligence": 0.01,
            },
        ),
        OcrBenchmarkSample(
            item_key="page-2",
            expected_text="Every person is entitled to privacy",
            provider_texts={
                "google_document_ai": "Every person is entitled to privacy",
                "azure_document_intelligence": "Every person is entitled to privacy",
            },
        ),
    ]

    result = evaluate_ocr_benchmark(dataset_version="ocr-v1", samples=samples)

    assert result.sample_count == 2
    assert result.winner == "google_document_ai"
    assert result.providers[0].provider == "google_document_ai"
    assert result.providers[0].mean_character_accuracy == 1.0
    assert result.to_metrics()["winner"] == "google_document_ai"


def test_ocr_benchmark_counts_failures() -> None:
    samples = [
        OcrBenchmarkSample(
            item_key="page-1",
            expected_text="Section 37",
            provider_texts={"google_document_ai": "Section 37"},
            provider_failures={"azure_document_intelligence": "timeout"},
        )
    ]

    result = evaluate_ocr_benchmark(dataset_version="ocr-v1", samples=samples)

    azure = next(
        item
        for item in result.providers
        if item.provider == "azure_document_intelligence"
    )
    assert azure.failure_count == 1
    assert azure.mean_character_accuracy == 0.0


def test_ocr_benchmark_rejects_empty_samples() -> None:
    import pytest

    with pytest.raises(ValueError, match="does not contain samples"):
        evaluate_ocr_benchmark(dataset_version="ocr-v1", samples=[])


def test_ocr_benchmark_breaks_accuracy_ties_by_cost() -> None:
    samples = [
        OcrBenchmarkSample(
            item_key="page-1",
            expected_text="Section 37 protects privacy",
            provider_texts={
                "google_document_ai": "Section 37 protects privacy",
                "azure_document_intelligence": "Section 37 protects privacy",
            },
            provider_cost_usd={
                "google_document_ai": 0.05,
                "azure_document_intelligence": 0.01,
            },
            provider_timing_ms={
                "google_document_ai": 900.0,
                "azure_document_intelligence": 800.0,
            },
        )
    ]

    result = evaluate_ocr_benchmark(dataset_version="ocr-v1", samples=samples)

    assert result.winner == "azure_document_intelligence"
    azure = next(
        item
        for item in result.providers
        if item.provider == "azure_document_intelligence"
    )
    assert azure.total_cost_usd == 0.01
    assert azure.mean_timing_ms == 800.0


def test_ocr_benchmark_still_ranks_when_every_provider_fails_a_page() -> None:
    samples = [
        OcrBenchmarkSample(
            item_key="page-1",
            expected_text="Section 37",
            provider_texts={"google_document_ai": "Section 37"},
            provider_failures={"azure_document_intelligence": "timeout"},
        ),
        OcrBenchmarkSample(
            item_key="page-2",
            expected_text="Section 38",
            provider_texts={
                "google_document_ai": "Section 38",
                "azure_document_intelligence": "Section 38",
            },
        ),
    ]

    result = evaluate_ocr_benchmark(dataset_version="ocr-v1", samples=samples)

    assert result.winner == "google_document_ai"
    google = next(
        item for item in result.providers if item.provider == "google_document_ai"
    )
    assert google.failure_count == 0
    assert google.mean_character_accuracy == 1.0
