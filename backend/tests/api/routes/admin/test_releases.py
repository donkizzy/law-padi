import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.ingestion import LocalBlobStore
from app.legal.enums import (
    AuditSeverity,
    CorpusReleaseStatus,
    IngestionArtifactType,
    ReleasePromotionStatus,
    VectorIndexStatus,
)
from app.legal.models import (
    AuditEvent,
    CorpusReleaseEntry,
    EmbeddingRun,
    EvaluationDataset,
    IdempotencyRecord,
    IngestionArtifact,
    ReleasePromotionAttempt,
)
from tests.api.routes.admin.conftest import _release_bundle, _superuser


def test_release_validation_and_publish_require_selected_ready_index_and_two_people(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, build = _release_bundle(db, uploader=_superuser(db))

    release.validation_report = {
        **(release.validation_report or {}),
        "corpus_legal_status": "historical",
        "source_edition_review": {"known_exceptions": "Printed 189; missing 168"},
    }
    db.add(release)
    db.commit()
    validate_key = f"validate-{uuid.uuid4().hex}"
    validate_body = {
        "idempotency_key": validate_key,
        "expected_version": release.lock_version,
    }
    validate_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json=validate_body,
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["status"] == CorpusReleaseStatus.APPROVED
    assert validate_response.json()["validation_report"]["unresolved_gates"] == []
    assert (
        validate_response.json()["validation_report"]["corpus_legal_status"]
        == "historical"
    )
    assert validate_response.json()["validation_report"]["source_edition_review"] == {
        "known_exceptions": "Printed 189; missing 168"
    }
    db.refresh(release)
    validated_lock_version = release.lock_version

    repeated_validate = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json=validate_body,
    )
    assert repeated_validate.status_code == 200
    assert repeated_validate.json()["lock_version"] == validated_lock_version
    db.refresh(release)
    assert release.lock_version == validated_lock_version

    blocked_publish = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert blocked_publish.status_code == 409
    assert blocked_publish.json()["detail"] == (
        "Publisher must differ from the source uploader"
    )
    db.refresh(release)

    publish_key = f"publish-{uuid.uuid4().hex}"
    publish_body = {
        "idempotency_key": publish_key,
        "expected_version": release.lock_version,
        "superuser_override_reason": "Solo seeded superuser in route test",
    }
    publish_response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json=publish_body,
    )

    assert publish_response.status_code == 200
    payload = publish_response.json()
    assert payload["release"]["status"] == CorpusReleaseStatus.PRODUCTION
    assert payload["promotion_status"] == "succeeded"
    assert payload["vector_index_status"] == VectorIndexStatus.PROMOTED
    db.refresh(build)
    assert build.status == VectorIndexStatus.PROMOTED
    high_audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.action == "corpus_release.publish_override",
            AuditEvent.severity == AuditSeverity.HIGH,
        )
    ).first()
    assert high_audit
    promotion_count = db.exec(
        select(func.count())
        .select_from(ReleasePromotionAttempt)
        .where(ReleasePromotionAttempt.release_id == release.id)
    ).one()
    assert promotion_count == 1

    repeated_publish = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json=publish_body,
    )
    assert repeated_publish.status_code == 200
    assert repeated_publish.json()["promotion_status"] == "succeeded"
    assert (
        db.exec(
            select(func.count())
            .select_from(ReleasePromotionAttempt)
            .where(ReleasePromotionAttempt.release_id == release.id)
        ).one()
        == 1
    )
    assert (
        db.exec(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(
                col(IdempotencyRecord.idempotency_key).in_([validate_key, publish_key])
            )
        ).one()
        == 2
    )


def test_read_release_manifest_returns_retained_manifest_artifact(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    release, _build = _release_bundle(db, uploader=_superuser(db))
    release_entry = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).one()
    manifest = {
        "release_id": str(release.id),
        "release_version": release.version,
        "source_documents": [
            {
                "id": str(release_entry.source_document_id),
                "title": "Official 1999 Constitution PDF",
                "authority": "Official Gazette",
                "sha256": "a" * 64,
                "page_count": 3,
            }
        ],
        "entries": [
            {
                "provision_version_id": str(release_entry.provision_version_id),
                "source_document_id": str(release_entry.source_document_id),
                "canonical_path": "constitution.1999.section.37",
                "source_page_start": 2,
                "source_page_end": 2,
            }
        ],
    }
    blob = LocalBlobStore(tmp_path).put_artifact(
        run_id=str(release_entry.ingestion_run_id),
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST.value,
        filename="release-manifest.json",
        content=json.dumps(manifest).encode(),
        content_type="application/json",
        metadata={
            "release_id": str(release.id),
            "source_manifest_hash": release.source_manifest_hash or "",
        },
    )
    artifact = IngestionArtifact(
        run_id=release_entry.ingestion_run_id,
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        artifact_metadata=blob.metadata,
    )
    db.add(artifact)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/manifest",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["release_id"] == str(release.id)
    assert payload["release_version"] == release.version
    assert payload["source_manifest_hash"] == release.source_manifest_hash
    assert payload["artifact"]["id"] == str(artifact.id)
    assert payload["manifest"]["source_documents"][0]["title"] == (
        "Official 1999 Constitution PDF"
    )
    assert payload["manifest"]["entries"][0]["canonical_path"] == (
        "constitution.1999.section.37"
    )


def test_read_release_manifest_404s_when_artifact_is_missing(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _build = _release_bundle(db, uploader=_superuser(db))

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/manifest",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Release manifest artifact was not found"


def test_read_release_publication_evidence_returns_index_actor_and_promotion_history(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    uploader = _superuser(db)
    release, build = _release_bundle(db, uploader=uploader)
    release.approved_by = uploader.id
    promotion = ReleasePromotionAttempt(
        release_id=release.id,
        retrieval_index_build_id=build.id,
        requested_by=uploader.id,
        status=ReleasePromotionStatus.ROLLED_BACK,
        previous_release_id=None,
        rollback_completed=True,
        error_details={"phase": "database_promotion"},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    override = AuditEvent(
        actor_user_id=uploader.id,
        action="corpus_release.publish_override",
        entity_type="corpus_release",
        entity_id=release.id,
        severity=AuditSeverity.HIGH,
        reason="Solo superuser override for route test",
    )
    db.add_all([release, promotion, override])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publication-evidence",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["release_id"] == str(release.id)
    assert "vector_indexes" not in payload
    assert not {
        "vector_index_id",
        "previous_collection_name",
        "target_collection_name",
    } & set(payload["promotion_attempts"][0])
    assert payload["retrieval_index_builds"][0]["id"] == str(build.id)
    assert payload["promotion_attempts"][0]["id"] == str(promotion.id)
    assert payload["promotion_attempts"][0]["status"] == (
        ReleasePromotionStatus.ROLLED_BACK
    )
    assert payload["promotion_attempts"][0]["rollback_completed"] is True
    assert payload["actor_separation"] == {
        "current_actor_id": str(uploader.id),
        "source_uploader_ids": [str(uploader.id)],
        "current_actor_is_source_uploader": True,
        "approved_by": str(uploader.id),
        "approved_by_differs_from_uploaders": False,
        "superuser_override_recorded": True,
        "override_reasons": ["Solo superuser override for route test"],
    }


def test_release_validation_rejects_ready_index_without_validation_evidence(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, build = _release_bundle(db, uploader=_superuser(db))
    build.validation_report = {"is_valid": True}
    db.add(build)
    db.commit()
    db.refresh(release)

    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CorpusReleaseStatus.VALIDATING
    assert payload["validation_report"]["unresolved_gates"] == [
        "retrieval_index_report_dimensions_mismatch",
        "retrieval_index_lexical_validation_missing",
    ]


def test_release_validation_rejects_selected_embedding_below_recall_gate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _build = _release_bundle(db, uploader=_superuser(db))
    embedding_run = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    embedding_run.recall_at_10 = 0.94
    db.add(embedding_run)
    db.commit()
    db.refresh(release)

    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CorpusReleaseStatus.VALIDATING
    assert payload["validation_report"]["unresolved_gates"] == [
        "selected_embedding_run_below_recall_threshold"
    ]


def test_release_validation_requires_active_retrieval_benchmark_dataset(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    release, _build = _release_bundle(db, uploader=_superuser(db))
    embedding_run = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    assert embedding_run.benchmark_dataset_version
    dataset = db.exec(
        select(EvaluationDataset).where(
            EvaluationDataset.version == embedding_run.benchmark_dataset_version
        )
    ).one()
    dataset.is_active = False
    db.add(dataset)
    db.commit()
    db.refresh(release)

    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CorpusReleaseStatus.VALIDATING
    assert payload["validation_report"]["benchmark_query_count"] == 0
    assert payload["validation_report"]["unresolved_gates"] == [
        "benchmark_dataset_missing_or_empty"
    ]


def test_release_validation_blocks_instruments_without_citation_names(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    from app.legal.models import LegalInstrument, Provision, ProvisionVersion

    release, _build = _release_bundle(db, uploader=_superuser(db))
    instrument = db.exec(
        select(LegalInstrument)
        .join(Provision)
        .join(ProvisionVersion)
        .join(CorpusReleaseEntry)
        .where(CorpusReleaseEntry.release_id == release.id)
    ).one()
    instrument.slug = f"law-without-citation-names-{uuid.uuid4().hex}"
    db.add(instrument)
    db.commit()
    response = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/validate",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"validate-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == CorpusReleaseStatus.VALIDATING
    assert body["validation_report"]["unresolved_gates"] == [
        f"Instrument {instrument.slug} has no citation names; add an entry to legal/data/instrument-names.json"
    ]
    blocked = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": body["lock_version"],
        },
    )
    assert blocked.status_code == 409

    # A previously approved release must also fail the publication recheck.
    db.refresh(release)
    release.status = CorpusReleaseStatus.APPROVED
    db.add(release)
    db.commit()
    rechecked = client.post(
        f"{settings.API_V1_STR}/admin/corpus-releases/{release.id}/publish",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"publish-{uuid.uuid4().hex}",
            "expected_version": release.lock_version,
        },
    )
    assert rechecked.status_code == 409
    assert instrument.slug in rechecked.json()["detail"]["gates"][0]
    assert "instrument-names.json" in rechecked.json()["detail"]["gates"][0]
