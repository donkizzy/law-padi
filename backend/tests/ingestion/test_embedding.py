import json
import uuid

import httpx

from app.ingestion.embedding import (
    EmbeddingBenchmarkError,
    EmbeddingBenchmarkQuery,
    HuggingFaceTeiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SparseLegalEncoder,
    evaluate_embedding_benchmark,
    select_best_embedding_run,
)
from app.legal.enums import EmbeddingRunStatus
from app.legal.models import EmbeddingRun


def test_openai_embedding_provider_batches_inputs_and_sorts_vectors_by_index() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
                "usage": {"total_tokens": 12},
            },
        )

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model_name="text-embedding-3-large",
        transport=httpx.MockTransport(handler),
    )

    batch = provider.embed(["Section 1", "Section 2"])

    assert requests == [
        {"model": "text-embedding-3-large", "input": ["Section 1", "Section 2"]}
    ]
    assert batch.provider == "openai"
    assert batch.dimensions == 2
    assert batch.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert batch.metrics == {"token_usage": {"total_tokens": 12}}


def test_huggingface_tei_provider_retries_cold_start_and_parses_vectors() -> None:
    statuses = [502, 200]
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        if status == 502:
            return httpx.Response(502, json={"error": "cold start"})
        return httpx.Response(200, json=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    provider = HuggingFaceTeiEmbeddingProvider(
        endpoint_url="https://tei.example.test/embed",
        api_token="hf-token",
        model_revision="pinned-revision",
        sleep=sleeps.append,
        transport=httpx.MockTransport(handler),
    )

    batch = provider.embed(["privacy", "citizenship"])

    assert sleeps == [1]
    assert batch.provider == "huggingface_tei"
    assert batch.model_name == "BAAI/bge-m3"
    assert batch.model_revision == "pinned-revision"
    assert batch.vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert batch.metrics == {"attempts": 2}


def test_sparse_legal_encoder_is_deterministic_and_normalized() -> None:
    encoder = SparseLegalEncoder(dimensions=128)

    first = encoder.encode(["Privacy privacy home"])[0]
    second = encoder.encode(["Privacy privacy home"])[0]

    assert first == second
    assert len(first.indices) == len(first.values)
    assert first.indices == sorted(first.indices)
    assert round(sum(value * value for value in first.values), 4) == 1


def test_evaluate_embedding_benchmark_computes_recall_and_ndcg_from_vectors() -> None:
    documents = [
        {
            "id": "doc-section-37",
            "payload": {"canonical_path": "constitution.1999.chapter4.section37"},
        },
        {
            "id": "doc-section-38",
            "payload": {"canonical_path": "constitution.1999.chapter4.section38"},
        },
    ]

    result = evaluate_embedding_benchmark(
        documents=documents,
        document_vectors=[[1.0, 0.0], [0.0, 1.0]],
        queries=[
            EmbeddingBenchmarkQuery(
                item_key="privacy",
                query_text="Which section protects privacy?",
                expected_canonical_paths=["constitution.1999.chapter4.section37"],
            ),
            EmbeddingBenchmarkQuery(
                item_key="religion",
                query_text="Which section protects religious freedom?",
                expected_canonical_paths=["constitution.1999.chapter4.section38"],
            ),
        ],
        query_vectors=[[0.9, 0.1], [0.8, 0.2]],
        top_k=1,
    )

    assert result.query_count == 2
    assert result.recall_at_10 == 0.5
    assert result.ndcg_at_10 == 0.5
    assert result.per_query[0]["matched_canonical_paths"] == [
        "constitution.1999.chapter4.section37"
    ]
    assert result.per_query[1]["matched_canonical_paths"] == []


def test_evaluate_embedding_benchmark_requires_canonical_paths() -> None:
    try:
        evaluate_embedding_benchmark(
            documents=[{"id": "missing-path", "payload": {}}],
            document_vectors=[[1.0, 0.0]],
            queries=[
                EmbeddingBenchmarkQuery(
                    item_key="privacy",
                    query_text="Which section protects privacy?",
                    expected_canonical_paths=["constitution.1999.chapter4.section37"],
                )
            ],
            query_vectors=[[1.0, 0.0]],
        )
    except EmbeddingBenchmarkError as exc:
        assert "canonical_path" in str(exc)
    else:
        raise AssertionError("Expected missing canonical_path to fail")


def test_select_best_embedding_run_applies_recall_threshold_and_tie_breakers() -> None:
    low_recall = EmbeddingRun(
        release_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status=EmbeddingRunStatus.SUCCEEDED,
        recall_at_10=0.93,
        ndcg_at_10=0.99,
        cost_usd=0.1,
        p95_latency_ms=100,
    )
    high_cost = EmbeddingRun(
        release_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status=EmbeddingRunStatus.SUCCEEDED,
        recall_at_10=0.96,
        ndcg_at_10=0.94,
        cost_usd=2,
        p95_latency_ms=150,
    )
    low_cost = EmbeddingRun(
        release_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status=EmbeddingRunStatus.SUCCEEDED,
        recall_at_10=0.96,
        ndcg_at_10=0.94,
        cost_usd=1,
        p95_latency_ms=200,
    )
    failed_with_stale_metrics = EmbeddingRun(
        release_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status=EmbeddingRunStatus.FAILED,
        recall_at_10=0.99,
        ndcg_at_10=0.99,
        cost_usd=0.01,
        p95_latency_ms=50,
    )

    selected = select_best_embedding_run(
        [low_recall, high_cost, low_cost, failed_with_stale_metrics]
    )

    assert selected == low_cost
