import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx


class QdrantIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class QdrantPoint:
    point_id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class QdrantSearchHit:
    point_id: str
    score: float | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class QdrantValidationReport:
    point_count: int
    vector_dimensions: int
    checksum: str
    payload_schema_hash: str
    duplicate_ids: list[str]
    dimension_errors: list[str]
    payload_errors: list[str]

    @property
    def is_valid(self) -> bool:
        return (
            not self.duplicate_ids
            and not self.dimension_errors
            and not self.payload_errors
        )


REQUIRED_QDRANT_PAYLOAD_KEYS = (
    "release_version",
    "corpus_release_entry_id",
    "provision_id",
    "provision_version_id",
    "canonical_path",
    "kind",
    "source_document_id",
    "legal_status",
    "segment_index",
    "segment_count",
    "text_sha256",
    "retrieval_text_sha256",
    "segment_id",
    "citation",
)


def collection_name_for_release(
    *, release_version: str, embedding_profile_name: str, profile_hash: str
) -> str:
    digest = hashlib.sha256(
        f"{release_version}:{embedding_profile_name}:{profile_hash}".encode()
    ).hexdigest()[:16]
    safe_version = _safe_token(release_version)
    safe_profile = _safe_token(embedding_profile_name)
    return f"law_padi_{safe_version}_{safe_profile}_{digest}"


def validate_qdrant_points(
    points: list[QdrantPoint],
    *,
    vector_dimensions: int,
    required_payload_keys: tuple[str, ...] = REQUIRED_QDRANT_PAYLOAD_KEYS,
) -> QdrantValidationReport:
    id_counts = Counter(point.point_id for point in points)
    duplicate_ids = sorted(
        point_id for point_id, count in id_counts.items() if count > 1
    )
    dimension_errors = [
        point.point_id for point in points if len(point.vector) != vector_dimensions
    ]
    payload_errors = _payload_errors(
        points, required_payload_keys=required_payload_keys
    )
    payload_keys = sorted({key for point in points for key in point.payload})
    payload_schema_hash = _sha256_json(payload_keys)
    checksum = _sha256_json(
        [
            {
                "id": point.point_id,
                "vector": point.vector,
                "payload": point.payload,
            }
            for point in sorted(points, key=lambda item: item.point_id)
        ]
    )
    return QdrantValidationReport(
        point_count=len(points),
        vector_dimensions=vector_dimensions,
        checksum=checksum,
        payload_schema_hash=payload_schema_hash,
        duplicate_ids=duplicate_ids,
        dimension_errors=dimension_errors,
        payload_errors=payload_errors,
    )


def alias_switch_actions(
    *,
    alias_name: str,
    new_collection_name: str,
    old_collection_name: str | None = None,
) -> list[dict[str, dict[str, str]]]:
    actions: list[dict[str, dict[str, str]]] = []
    if old_collection_name:
        actions.append(
            {
                "delete_alias": {
                    "collection_name": old_collection_name,
                    "alias_name": alias_name,
                }
            }
        )
    actions.append(
        {
            "create_alias": {
                "collection_name": new_collection_name,
                "alias_name": alias_name,
            }
        }
    )
    return actions


def alias_delete_actions(
    *, alias_name: str, collection_name: str
) -> list[dict[str, dict[str, str]]]:
    return [
        {
            "delete_alias": {
                "collection_name": collection_name,
                "alias_name": alias_name,
            }
        }
    ]


class QdrantHttpIndexAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"api-key": api_key} if api_key else None
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
        )

    def create_collection(
        self, *, collection_name: str, vector_dimensions: int
    ) -> None:
        response = self.client.put(
            f"/collections/{collection_name}",
            json={
                "vectors": {
                    "size": vector_dimensions,
                    "distance": "Cosine",
                }
            },
        )
        _raise_for_qdrant(response, "create collection")

    def upsert_points(self, *, collection_name: str, points: list[QdrantPoint]) -> None:
        response = self.client.put(
            f"/collections/{collection_name}/points",
            json={
                "points": [
                    {
                        "id": point.point_id,
                        "vector": point.vector,
                        "payload": point.payload,
                    }
                    for point in points
                ]
            },
        )
        _raise_for_qdrant(response, "upsert points")

    def read_point_count(self, *, collection_name: str) -> int:
        response = self.client.post(
            f"/collections/{collection_name}/points/count",
            json={"exact": True},
        )
        _raise_for_qdrant(response, "count points")
        payload = response.json()
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("count"), int):
            raise QdrantIndexError("Qdrant count response was malformed")
        return int(result["count"])

    def search_points(
        self, *, collection_name: str, vector: list[float], limit: int = 5
    ) -> list[QdrantSearchHit]:
        response = self.client.post(
            f"/collections/{collection_name}/points/search",
            json={"vector": vector, "limit": limit, "with_payload": True},
        )
        _raise_for_qdrant(response, "search points")
        payload = response.json()
        result = payload.get("result")
        if not isinstance(result, list):
            raise QdrantIndexError("Qdrant search response was malformed")
        hits: list[QdrantSearchHit] = []
        for item in result:
            if not isinstance(item, dict) or "id" not in item:
                raise QdrantIndexError("Qdrant search hit was malformed")
            hit_payload = item.get("payload")
            if hit_payload is None:
                hit_payload = {}
            if not isinstance(hit_payload, dict):
                raise QdrantIndexError("Qdrant search hit payload was malformed")
            score = item.get("score")
            hits.append(
                QdrantSearchHit(
                    point_id=str(item["id"]),
                    score=float(score) if isinstance(score, int | float) else None,
                    payload=hit_payload,
                )
            )
        return hits

    def switch_alias(
        self,
        *,
        alias_name: str,
        new_collection_name: str,
        old_collection_name: str | None = None,
    ) -> None:
        response = self.client.post(
            "/collections/aliases",
            json={
                "actions": alias_switch_actions(
                    alias_name=alias_name,
                    new_collection_name=new_collection_name,
                    old_collection_name=old_collection_name,
                )
            },
        )
        _raise_for_qdrant(response, "switch alias")

    def delete_alias(self, *, alias_name: str, collection_name: str) -> None:
        response = self.client.post(
            "/collections/aliases",
            json={
                "actions": alias_delete_actions(
                    alias_name=alias_name,
                    collection_name=collection_name,
                )
            },
        )
        _raise_for_qdrant(response, "delete alias")


def _safe_token(value: str) -> str:
    lowered = value.lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in lowered)
    return "_".join(part for part in cleaned.split("_") if part)[:48]


def _payload_errors(
    points: list[QdrantPoint], *, required_payload_keys: tuple[str, ...]
) -> list[str]:
    errors: list[str] = []
    for point in points:
        if not point.point_id.strip():
            errors.append("<empty>:point_id_empty")
        missing = sorted(
            key for key in required_payload_keys if key not in point.payload
        )
        if missing:
            errors.append(f"{point.point_id}:missing:{','.join(missing)}")
        for key in (
            "release_version",
            "corpus_release_entry_id",
            "provision_id",
            "provision_version_id",
            "canonical_path",
            "kind",
            "source_document_id",
            "legal_status",
            "text_sha256",
            "retrieval_text_sha256",
            "segment_id",
            "citation",
        ):
            value = point.payload.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{point.point_id}:invalid:{key}")
        for key in ("segment_index", "segment_count"):
            value = point.payload.get(key)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                errors.append(f"{point.point_id}:invalid:{key}")
    return errors


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _raise_for_qdrant(response: httpx.Response, operation: str) -> None:
    if response.status_code >= 400:
        raise QdrantIndexError(
            f"Qdrant {operation} failed: {response.status_code} {response.text}"
        )
