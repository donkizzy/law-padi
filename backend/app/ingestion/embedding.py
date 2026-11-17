import math
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol, cast

import httpx

from app.ingestion.runtime.retry import request_with_retries, retryable_status
from app.legal.enums import EmbeddingProviderKind, EmbeddingRunStatus
from app.legal.models import EmbeddingRun


class EmbeddingProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class EmbeddingBenchmarkError(RuntimeError):
    pass


class EmbeddingProviderUnavailable(EmbeddingProviderError):
    pass


@dataclass(frozen=True)
class EmbeddingBatch:
    provider: str
    model_name: str
    model_revision: str | None
    vectors: list[list[float]]
    cost_usd: float | None = None
    metrics: dict[str, Any] | None = None

    @property
    def dimensions(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


@dataclass(frozen=True)
class EmbeddingBenchmarkQuery:
    item_key: str
    query_text: str
    expected_canonical_paths: list[str]


@dataclass(frozen=True)
class EmbeddingBenchmarkResult:
    query_count: int
    recall_at_10: float
    ndcg_at_10: float
    per_query: list[dict[str, Any]]

    def to_metrics(self) -> dict[str, Any]:
        return {
            "benchmark_query_count": self.query_count,
            "recall_at_10": self.recall_at_10,
            "ndcg_at_10": self.ndcg_at_10,
            "per_query": self.per_query,
        }


class DenseEmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Embed a batch of retrieval texts."""


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        model_name: str = "text-embedding-3-large",
        model_revision: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.model_name = model_name
        self.model_revision = model_revision
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not self.api_key:
            raise EmbeddingProviderUnavailable("OpenAI API key is not configured")
        response = request_with_retries(
            lambda remaining: self.client.post(
                "/embeddings",
                timeout=min(self.timeout_seconds, remaining),
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model_name,
                    "input": list(texts),
                    "dimensions": 1024,
                },
            )
        )
        if response.status_code >= 400:
            raise EmbeddingProviderError(
                f"OpenAI embedding request failed: {response.status_code}",
                retryable=retryable_status(response.status_code),
            )
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            raise EmbeddingProviderError("OpenAI embedding response missing data")
        items: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingProviderError(
                    "OpenAI embedding response contained a non-object item"
                )
            items.append(cast(dict[str, Any], item))
        ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
        vectors = [_coerce_vector(item.get("embedding")) for item in ordered]
        return EmbeddingBatch(
            provider="openai",
            model_name=self.model_name,
            model_revision=self.model_revision,
            vectors=vectors,
            metrics={"token_usage": payload.get("usage")},
        )


RETRYABLE_TEI_STATUSES = frozenset({429, 502, 503, 504})
DEFAULT_EMBEDDING_BATCH_SIZE = 128


def batched_embed(
    provider: DenseEmbeddingProvider,
    texts: Sequence[str],
    *,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
) -> EmbeddingBatch:
    """Embed large corpora in bounded batches while preserving input order."""
    size = max(1, batch_size)
    if len(texts) <= size:
        return provider.embed(texts)
    batches = [list(texts[i : i + size]) for i in range(0, len(texts), size)]
    combined: list[list[float]] = []
    first: EmbeddingBatch | None = None
    for batch_texts in batches:
        batch = provider.embed(batch_texts)
        if first is None:
            first = batch
        combined.extend(batch.vectors)
    assert first is not None
    return EmbeddingBatch(
        provider=first.provider,
        model_name=first.model_name,
        model_revision=first.model_revision,
        vectors=combined,
        cost_usd=first.cost_usd,
        metrics={**(first.metrics or {}), "batched_batches": len(batches)},
    )


class HuggingFaceTeiEmbeddingProvider:
    def __init__(
        self,
        *,
        endpoint_url: str | None,
        api_token: str | None,
        model_name: str = "BAAI/bge-m3",
        model_revision: str | None = None,
        timeout_seconds: float = 60,
        max_attempts: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.endpoint_url = endpoint_url.rstrip("/") if endpoint_url else None
        self.api_token = api_token
        self.model_name = model_name
        self.model_revision = model_revision
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not self.endpoint_url:
            raise EmbeddingProviderUnavailable(
                "Hugging Face TEI endpoint is not configured"
            )
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        response = request_with_retries(
            lambda remaining: self.client.post(
                self.endpoint_url or "",
                headers=headers,
                json={"inputs": list(texts), "truncate": True},
                timeout=min(self.timeout_seconds, remaining),
            ),
            max_attempts=self.max_attempts,
            sleep=self.sleep,
        )
        if response.status_code >= 400:
            raise EmbeddingProviderError(
                f"Hugging Face TEI request failed: {response.status_code}",
                retryable=retryable_status(response.status_code),
            )
        vectors = _parse_tei_vectors(response.json())
        return EmbeddingBatch(
            provider="huggingface_tei",
            model_name=self.model_name,
            model_revision=self.model_revision,
            vectors=vectors,
            metrics={"attempts": response.extensions["ingestion_attempts"]},
        )


_provider_lock = Lock()
_providers: dict[
    tuple[object, ...], OpenAIEmbeddingProvider | HuggingFaceTeiEmbeddingProvider
] = {}


def shared_embedding_provider(
    *,
    profile_id: uuid.UUID,
    provider: EmbeddingProviderKind,
    model_name: str,
    model_revision: str | None,
    api_key: str | None,
    endpoint_url: str | None,
    api_token: str | None,
    timeout_seconds: float,
    max_attempts: int = 5,
) -> OpenAIEmbeddingProvider | HuggingFaceTeiEmbeddingProvider:
    """Keep a connection pool per profile and effective provider configuration.

    Query and ingestion callers retain their own timeouts and retry budgets.
    The lock also prevents simultaneous first queries creating duplicate pools.
    """
    key = (
        profile_id,
        provider,
        model_name,
        model_revision,
        api_key,
        endpoint_url,
        api_token,
        timeout_seconds,
        max_attempts,
    )
    with _provider_lock:
        existing = _providers.get(key)
        if existing is not None:
            return existing
        created: OpenAIEmbeddingProvider | HuggingFaceTeiEmbeddingProvider
        if provider == EmbeddingProviderKind.OPENAI:
            created = OpenAIEmbeddingProvider(
                api_key=api_key,
                model_name=model_name,
                model_revision=model_revision,
                timeout_seconds=timeout_seconds,
            )
        else:
            created = HuggingFaceTeiEmbeddingProvider(
                endpoint_url=endpoint_url,
                api_token=api_token,
                model_name=model_name,
                model_revision=model_revision,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
            )
        _providers[key] = created
        return created


def close_embedding_providers() -> None:
    """Close connection pools after the process's embedding work has stopped."""
    with _provider_lock:
        providers = list(_providers.values())
        _providers.clear()
    for provider in providers:
        provider.client.close()


def select_best_embedding_run(
    runs: Sequence[EmbeddingRun], *, min_recall_at_10: float = 0.95
) -> EmbeddingRun | None:
    eligible = [
        run
        for run in runs
        if run.status == EmbeddingRunStatus.SUCCEEDED
        and run.recall_at_10 is not None
        and run.recall_at_10 >= min_recall_at_10
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda run: (
            -(run.recall_at_10 or 0),
            -(run.ndcg_at_10 or 0),
            run.cost_usd if run.cost_usd is not None else math.inf,
            run.p95_latency_ms if run.p95_latency_ms is not None else math.inf,
        ),
    )[0]


def evaluate_embedding_benchmark(
    *,
    documents: Sequence[Mapping[str, Any]],
    document_vectors: Sequence[Sequence[float]],
    queries: Sequence[EmbeddingBenchmarkQuery],
    query_vectors: Sequence[Sequence[float]],
    top_k: int = 10,
) -> EmbeddingBenchmarkResult:
    if not queries:
        raise EmbeddingBenchmarkError("Benchmark dataset does not contain queries")
    if len(documents) != len(document_vectors):
        raise EmbeddingBenchmarkError("Document and vector counts do not match")
    if len(queries) != len(query_vectors):
        raise EmbeddingBenchmarkError("Query and vector counts do not match")

    document_rows = [
        (
            document,
            list(vector),
            _document_canonical_path(document),
        )
        for document, vector in zip(documents, document_vectors, strict=True)
    ]
    if any(path is None for _document, _vector, path in document_rows):
        raise EmbeddingBenchmarkError("Benchmark document is missing canonical_path")

    per_query: list[dict[str, Any]] = []
    recall_scores: list[float] = []
    ndcg_scores: list[float] = []
    for query, query_vector in zip(queries, query_vectors, strict=True):
        expected_paths = sorted(set(query.expected_canonical_paths))
        if not expected_paths:
            raise EmbeddingBenchmarkError(
                f"Benchmark query {query.item_key} has no expected paths"
            )
        ranked = sorted(
            (
                (
                    _cosine_similarity(query_vector, document_vector),
                    str(canonical_path),
                    str(document.get("id") or document.get("segment_id") or ""),
                )
                for document, document_vector, canonical_path in document_rows
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        top_hits = ranked[:top_k]
        top_paths = [path for _score, path, _document_id in top_hits]
        matched_paths = sorted(
            {
                expected
                for path in top_paths
                if (expected := _expected_path_covering(path, expected_paths))
            }
        )
        recall = len(matched_paths) / len(expected_paths)
        ndcg = _ndcg_at_k(top_paths=top_paths, expected_paths=expected_paths)
        recall_scores.append(recall)
        ndcg_scores.append(ndcg)
        per_query.append(
            {
                "item_key": query.item_key,
                "expected_canonical_paths": expected_paths,
                "top_canonical_paths": top_paths,
                "matched_canonical_paths": matched_paths,
                "recall_at_10": round(recall, 6),
                "ndcg_at_10": round(ndcg, 6),
                "top_scores": [round(score, 6) for score, _path, _id in top_hits],
            }
        )

    return EmbeddingBenchmarkResult(
        query_count=len(queries),
        recall_at_10=round(sum(recall_scores) / len(recall_scores), 6),
        ndcg_at_10=round(sum(ndcg_scores) / len(ndcg_scores), 6),
        per_query=per_query,
    )


def _parse_tei_vectors(payload: object) -> list[list[float]]:
    if isinstance(payload, list):
        return [_coerce_vector(vector) for vector in payload]
    if isinstance(payload, dict):
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list):
            return [_coerce_vector(vector) for vector in embeddings]
        data = payload.get("data")
        if isinstance(data, list):
            vectors: list[list[float]] = []
            for item in data:
                if not isinstance(item, dict):
                    raise EmbeddingProviderError(
                        "TEI data response contained a non-object item"
                    )
                vectors.append(_coerce_vector(item.get("embedding")))
            return vectors
    raise EmbeddingProviderError("TEI embedding response did not contain vectors")


def _coerce_vector(value: object) -> list[float]:
    if not isinstance(value, list):
        raise EmbeddingProviderError("Embedding vector was not a list")
    vector: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise EmbeddingProviderError("Embedding vector contained a non-number")
        vector.append(float(item))
    return vector


def _document_canonical_path(document: Mapping[str, Any]) -> str | None:
    payload = document.get("payload")
    if isinstance(payload, Mapping):
        canonical_path = payload.get("canonical_path")
        if isinstance(canonical_path, str) and canonical_path:
            return canonical_path
    canonical_path = document.get("canonical_path")
    return (
        canonical_path if isinstance(canonical_path, str) and canonical_path else None
    )


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise EmbeddingBenchmarkError("Benchmark vector dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    dot = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return dot / (left_norm * right_norm)


def _expected_path_covering(path: str, expected_paths: Sequence[str]) -> str | None:
    # A hit on a provision inside the expected one (e.g. s.8(2) for s.8) is the
    # expected provision answering the query.
    for expected in expected_paths:
        if path == expected or path.startswith(f"{expected}."):
            return expected
    return None


def _ndcg_at_k(*, top_paths: Sequence[str], expected_paths: Sequence[str]) -> float:
    expected = set(expected_paths)
    dcg = 0.0
    credited: set[str] = set()
    for rank, path in enumerate(top_paths, start=1):
        covering = _expected_path_covering(path, expected_paths)
        # Credit each expected provision once, at its best rank.
        if covering and covering not in credited:
            credited.add(covering)
            dcg += 1 / math.log2(rank + 1)
    ideal_relevant = min(len(expected), len(top_paths))
    ideal_dcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_relevant + 1))
    return dcg / ideal_dcg if ideal_dcg else 0.0
