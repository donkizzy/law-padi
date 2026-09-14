import json

import httpx
import pytest

from app.ingestion.qdrant import (
    QdrantHttpIndexAdapter,
    QdrantIndexError,
    QdrantPoint,
    QdrantSearchHit,
    alias_delete_actions,
    alias_switch_actions,
    collection_name_for_release,
    validate_qdrant_points,
)


def test_collection_name_is_deterministic_and_safe() -> None:
    first = collection_name_for_release(
        release_version="Draft 2026/09",
        embedding_profile_name="OpenAI Large",
        profile_hash="abc123",
    )
    second = collection_name_for_release(
        release_version="Draft 2026/09",
        embedding_profile_name="OpenAI Large",
        profile_hash="abc123",
    )

    assert first == second
    assert first.startswith("law_padi_draft_2026_09_openai_large_")
    assert "/" not in first


def test_validate_qdrant_points_reports_count_checksum_duplicates_and_dimensions() -> (
    None
):
    report = validate_qdrant_points(
        [
            QdrantPoint(
                point_id="p1",
                vector=[0.1, 0.2],
                payload={"canonical_path": "section37", "release": "draft"},
            ),
            QdrantPoint(
                point_id="p1",
                vector=[0.3],
                payload={"canonical_path": "section38", "release": "draft"},
            ),
        ],
        vector_dimensions=2,
    )

    assert report.point_count == 2
    assert report.vector_dimensions == 2
    assert report.duplicate_ids == ["p1"]
    assert report.dimension_errors == ["p1"]
    assert report.payload_errors == [
        "p1:missing:citation,corpus_release_entry_id,kind,legal_status,"
        "provision_id,provision_version_id,release_version,"
        "retrieval_text_sha256,segment_count,segment_id,segment_index,"
        "source_document_id,text_sha256",
        "p1:missing:citation,corpus_release_entry_id,kind,legal_status,"
        "provision_id,provision_version_id,release_version,"
        "retrieval_text_sha256,segment_count,segment_id,segment_index,"
        "source_document_id,text_sha256",
    ]
    assert not report.is_valid
    assert len(report.checksum) == 64
    assert len(report.payload_schema_hash) == 64


def test_validate_qdrant_points_accepts_complete_retrieval_payload() -> None:
    report = validate_qdrant_points(
        [
            QdrantPoint(
                point_id="p1",
                vector=[0.1, 0.2],
                payload={
                    "release_version": "2026.09.test",
                    "corpus_release_entry_id": "entry-1",
                    "provision_id": "provision-1",
                    "provision_version_id": "version-1",
                    "canonical_path": "constitution.1999.section37",
                    "kind": "section",
                    "source_document_id": "source-1",
                    "legal_status": "current",
                    "segment_index": 1,
                    "segment_count": 1,
                    "text_sha256": "a" * 64,
                    "retrieval_text_sha256": "b" * 64,
                    "segment_id": "constitution.1999.section37:v1:s1",
                    "citation": "Section 37",
                },
            )
        ],
        vector_dimensions=2,
    )

    assert report.is_valid
    assert report.payload_errors == []


def test_qdrant_http_adapter_sends_collection_points_count_and_alias_payloads() -> None:
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.url.path.endswith("/points/count"):
            return httpx.Response(200, json={"result": {"count": 1}})
        if request.url.path.endswith("/points/search"):
            return httpx.Response(
                200,
                json={
                    "result": [
                        {
                            "id": "point-1",
                            "score": 0.99,
                            "payload": {
                                "canonical_path": "constitution.1999.section37"
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"result": True})

    adapter = QdrantHttpIndexAdapter(
        base_url="https://qdrant.example.test",
        api_key="qdrant-key",
        transport=httpx.MockTransport(handler),
    )
    point = QdrantPoint(
        point_id="point-1",
        vector=[0.1, 0.2],
        payload={"canonical_path": "constitution.1999.section37"},
    )

    adapter.create_collection(collection_name="collection_a", vector_dimensions=2)
    adapter.upsert_points(collection_name="collection_a", points=[point])
    count = adapter.read_point_count(collection_name="collection_a")
    hits = adapter.search_points(
        collection_name="collection_a", vector=[0.1, 0.2], limit=3
    )
    adapter.switch_alias(
        alias_name="law_padi_production",
        old_collection_name="collection_old",
        new_collection_name="collection_a",
    )

    assert count == 1
    assert hits == [
        QdrantSearchHit(
            point_id="point-1",
            score=0.99,
            payload={"canonical_path": "constitution.1999.section37"},
        )
    ]
    assert requests == [
        (
            "PUT",
            "/collections/collection_a",
            {"vectors": {"size": 2, "distance": "Cosine"}},
        ),
        (
            "PUT",
            "/collections/collection_a/points",
            {
                "points": [
                    {
                        "id": "point-1",
                        "vector": [0.1, 0.2],
                        "payload": {"canonical_path": "constitution.1999.section37"},
                    }
                ]
            },
        ),
        ("POST", "/collections/collection_a/points/count", {"exact": True}),
        (
            "POST",
            "/collections/collection_a/points/search",
            {"vector": [0.1, 0.2], "limit": 3, "with_payload": True},
        ),
        (
            "POST",
            "/collections/aliases",
            {
                "actions": alias_switch_actions(
                    alias_name="law_padi_production",
                    old_collection_name="collection_old",
                    new_collection_name="collection_a",
                )
            },
        ),
    ]


def test_qdrant_http_adapter_can_delete_alias_for_first_publish_rollback() -> None:
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"result": True})

    adapter = QdrantHttpIndexAdapter(
        base_url="https://qdrant.example.test",
        transport=httpx.MockTransport(handler),
    )

    adapter.delete_alias(
        alias_name="law_padi_production",
        collection_name="collection_a",
    )

    assert requests == [
        (
            "POST",
            "/collections/aliases",
            {
                "actions": alias_delete_actions(
                    alias_name="law_padi_production",
                    collection_name="collection_a",
                )
            },
        )
    ]


def test_qdrant_http_adapter_raises_on_failed_alias_switch() -> None:
    adapter = QdrantHttpIndexAdapter(
        base_url="https://qdrant.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(500, text="alias failure")
        ),
    )

    with pytest.raises(QdrantIndexError, match="switch alias"):
        adapter.switch_alias(
            alias_name="law_padi_production",
            new_collection_name="collection_a",
        )
