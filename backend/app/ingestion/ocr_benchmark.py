"""Benchmark managed OCR providers on a shared versioned page set.

V1 scores precomputed provider outputs (no live provider calls here) so the
same OCR_PAGE evaluation dataset versions the comparison. The winner is
activated through MANAGED_OCR_PROVIDER configuration, never automatically.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.ingestion.quality import _levenshtein_distance


@dataclass(frozen=True)
class OcrBenchmarkSample:
    item_key: str
    expected_text: str
    provider_texts: Mapping[str, str]
    provider_confidence: Mapping[str, float | None] | None = None
    provider_cost_usd: Mapping[str, float | None] | None = None
    provider_timing_ms: Mapping[str, float | None] | None = None
    provider_failures: Mapping[str, str] | None = None


@dataclass(frozen=True)
class OcrProviderBenchmark:
    provider: str
    page_count: int
    failure_count: int
    mean_character_accuracy: float
    mean_confidence: float | None
    total_cost_usd: float | None
    mean_timing_ms: float | None


@dataclass(frozen=True)
class OcrBenchmarkResult:
    dataset_version: str
    sample_count: int
    providers: list[OcrProviderBenchmark]
    winner: str | None

    def to_metrics(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "sample_count": self.sample_count,
            "winner": self.winner,
            "providers": [
                {
                    "provider": item.provider,
                    "page_count": item.page_count,
                    "failure_count": item.failure_count,
                    "mean_character_accuracy": item.mean_character_accuracy,
                    "mean_confidence": item.mean_confidence,
                    "total_cost_usd": item.total_cost_usd,
                    "mean_timing_ms": item.mean_timing_ms,
                }
                for item in self.providers
            ],
        }


def character_accuracy(expected: str, actual: str) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    distance = _levenshtein_distance(expected, actual)
    denom = max(len(expected), len(actual))
    return round(max(0.0, 1 - distance / denom), 6)


def evaluate_ocr_benchmark(
    *,
    dataset_version: str,
    samples: Sequence[OcrBenchmarkSample],
    providers: Sequence[str] = ("google_document_ai", "azure_document_intelligence"),
) -> OcrBenchmarkResult:
    if not samples:
        raise ValueError("OCR benchmark dataset does not contain samples")
    ranked: list[OcrProviderBenchmark] = []
    for provider in providers:
        accuracies: list[float] = []
        confidences: list[float] = []
        timings: list[float] = []
        costs: list[float] = []
        failures = 0
        pages = 0
        for sample in samples:
            failure = (sample.provider_failures or {}).get(provider)
            text = (sample.provider_texts or {}).get(provider)
            if failure or text is None:
                failures += 1
                accuracies.append(0.0)
                continue
            pages += 1
            accuracies.append(character_accuracy(sample.expected_text, text))
            confidence = (sample.provider_confidence or {}).get(provider)
            if isinstance(confidence, bool):
                pass
            elif isinstance(confidence, int | float):
                confidences.append(float(confidence))
            timing = (sample.provider_timing_ms or {}).get(provider)
            if isinstance(timing, bool):
                pass
            elif isinstance(timing, int | float):
                timings.append(float(timing))
            cost = (sample.provider_cost_usd or {}).get(provider)
            if isinstance(cost, bool):
                pass
            elif isinstance(cost, int | float):
                costs.append(float(cost))
        ranked.append(
            OcrProviderBenchmark(
                provider=provider,
                page_count=len(samples),
                failure_count=failures,
                mean_character_accuracy=round(sum(accuracies) / len(accuracies), 6)
                if accuracies
                else 0.0,
                mean_confidence=round(sum(confidences) / len(confidences), 4)
                if confidences
                else None,
                total_cost_usd=round(sum(costs), 6) if costs else None,
                mean_timing_ms=round(sum(timings) / len(timings), 3)
                if timings
                else None,
            )
        )
    winner = _select_winner(ranked)
    return OcrBenchmarkResult(
        dataset_version=dataset_version,
        sample_count=len(samples),
        providers=sorted(ranked, key=lambda item: -item.mean_character_accuracy),
        winner=winner,
    )


def _select_winner(providers: Sequence[OcrProviderBenchmark]) -> str | None:
    eligible = [item for item in providers if item.failure_count == 0]
    pool = eligible or list(providers)
    if not pool:
        return None
    best = sorted(
        pool,
        key=lambda item: (
            -item.mean_character_accuracy,
            item.failure_count,
            item.total_cost_usd if item.total_cost_usd is not None else float("inf"),
            item.mean_timing_ms if item.mean_timing_ms is not None else float("inf"),
        ),
    )[0]
    return best.provider
