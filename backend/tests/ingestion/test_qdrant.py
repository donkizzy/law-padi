import json

import httpx
import pytest

from app.ingestion.qdrant import (
    CONSTITUTION_ENACTED_ALIAS,
    CONSTITUTION_PROPOSALS_ALIAS,
    QdrantHttpIndexAdapter,
    QdrantIndexError,
    QdrantPoint,
    QdrantSearchHit,
    QdrantSparseVector,
    alias_delete_actions,
    alias_for_index_kind,
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
    assert first.startswith("ng_constitution_enacted_draft_2026_09_openai_large_")
    assert "/" not in first


def test_collection_name_splits_enacted_and_proposals() -> None:
    enacted = collection_name_for_release(
        release_version="draft-abc",
        embedding_profile_name="profile",
        profile_hash="hash",
        index_kind="enacted",
    )
    proposals = collection_name_for_release(
        release_version="draft-abc",
        embedding_profile_name="profile",
        profile_hash="hash",
        index_kind="proposals",
    )

    assert enacted != proposals
    assert enacted.startswith("ng_constitution_enacted_")
    assert proposals.startswith("ng_constitution_proposals_")
    assert alias_for_index_kind("enacted") == CONSTITUTION_ENACTED_ALIAS
    assert alias_for_index_kind("proposals") == CONSTITUTION_PROPOSALS_ALIAS


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
    assert report.sparse_errors == [
        "p1:missing:sparse_legal",
        "p1:missing:sparse_legal",
    ]

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
                sparse=QdrantSparseVector(indices=[1, 7], values=[0.7, 0.7]),
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
    assert report.sparse_errors == []


def test_validate_qdrant_points_rejects_missing_sparse() -> None:
    report = validate_qdrant_points(
        [
            QdrantPoint(
                point_id="p1",
                vector=[0.1, 0.2],
                payload={"canonical_path": "section37"},
            )
        ],
        vector_dimensions=2,
    )

    assert not report.is_valid
    assert report.sparse_errors == ["p1:missing:sparse_legal"]


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
        sparse=QdrantSparseVector(indices=[3], values=[1.0]),
        payload={"canonical_path": "constitution.1999.section37"},
    )

    adapter.create_collection(collection_name="collection_a", vector_dimensions=2)
    adapter.upsert_points(collection_name="collection_a", points=[point])
    count = adapter.read_point_count(collection_name="collection_a")
    hits = adapter.search_points(
        collection_name="collection_a", vector=[0.1, 0.2], limit=3
    )
    adapter.switch_alias(
        alias_name="constitution_enacted",
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
            {
                "vectors": {"dense": {"size": 2, "distance": "Cosine"}},
                "sparse_vectors": {"sparse_legal": {}},
            },
        ),
        (
            "PUT",
            "/collections/collection_a/points",
            {
                "points": [
                    {
                        "id": "point-1",
                        "vector": {
                            "dense": [0.1, 0.2],
                            "sparse_legal": {"indices": [3], "values": [1.0]},
                        },
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
                    alias_name="constitution_enacted",
                    old_collection_name="collection_old",
                    new_collection_name="collection_a",
                )
            },
        ),
    ]


def test_qdrant_upsert_chunks_large_batches() -> None:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        assert isinstance(body, dict)
        points = body["points"]
        assert isinstance(points, list)
        seen.append(len(points))
        return httpx.Response(200, json={"result": True})

    adapter = QdrantHttpIndexAdapter(
        base_url="https://qdrant.example.test",
        transport=httpx.MockTransport(handler),
    )
    points = [
        QdrantPoint(
            point_id=f"p{i}",
            vector=[0.1, 0.2],
            payload={"canonical_path": f"path-{i}"},
        )
        for i in range(5)
    ]
    adapter.upsert_points(collection_name="collection_a", points=points, batch_size=2)

    assert seen == [2, 2, 1]


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
        alias_name="constitution_enacted",
        collection_name="collection_a",
    )

    assert requests == [
        (
            "POST",
            "/collections/aliases",
            {
                "actions": alias_delete_actions(
                    alias_name="constitution_enacted",
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
            alias_name="constitution_enacted",
            new_collection_name="collection_a",
        )


def test_collection_naming_and_alias_reject_unknown_kind() -> None:
    with pytest.raises(QdrantIndexError, match="Unknown index kind"):
        collection_name_for_release(
            release_version="draft",
            embedding_profile_name="profile",
            profile_hash="hash",
            index_kind="drafts",
        )
    with pytest.raises(QdrantIndexError, match="Unknown index kind"):
        alias_for_index_kind("drafts")


def test_sparse_errors_catch_length_mismatch_and_unordered_indices() -> None:
    report = validate_qdrant_points(
        [
            QdrantPoint(
                point_id="bad-length",
                vector=[0.1, 0.2],
                sparse=QdrantSparseVector(indices=[1, 2], values=[0.5]),
                payload={"canonical_path": "x"},
            ),
            QdrantPoint(
                point_id="bad-order",
                vector=[0.1, 0.2],
                sparse=QdrantSparseVector(indices=[9, 3], values=[0.5, 0.5]),
                payload={"canonical_path": "y"},
            ),
        ],
        vector_dimensions=2,
    )

    assert not report.is_valid
    assert "bad-length:invalid:sparse_legal_length" in report.sparse_errors
    assert "bad-order:invalid:sparse_legal_order" in report.sparse_errors


def test_point_payload_falls_back_to_dense_only_without_sparse() -> None:
    adapter_requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        assert isinstance(body, dict)
        adapter_requests.append(body)
        return httpx.Response(200, json={"result": True})

    adapter = QdrantHttpIndexAdapter(
        base_url="https://qdrant.example.test",
        transport=httpx.MockTransport(handler),
    )
    adapter.upsert_points(
        collection_name="collection_legacy",
        points=[
            QdrantPoint(
                point_id="legacy-1",
                vector=[0.1, 0.2],
                payload={"canonical_path": "legacy"},
            )
        ],
    )

    assert adapter_requests == [
        {
            "points": [
                {
                    "id": "legacy-1",
                    "vector": [0.1, 0.2],
                    "payload": {"canonical_path": "legacy"},
                }
            ]
        }
    ]
