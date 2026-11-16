"""Composite publication uses approved synthetic laws in the dedicated test DB."""

import hashlib
import json
import uuid
from collections.abc import Generator, Sequence
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete, select

from app.core.config import settings
from app.ingestion.composition import (
    composition_gates,
    entry_snapshot,
    manifest_hash,
    release_entries,
)
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.embedding_reuse import member_document_vectors, profile_fingerprint
from app.ingestion.pgvector_repository import (
    validate_index_build,
    write_embeddings,
    write_segments,
)
from app.ingestion.retrieval import build_retrieval_documents
from app.ingestion.service import (
    _release_id_for_run,
    compose_corpus_release,
    correct_source_document_title,
    get_blob_store,
    publish_corpus_release,
    read_corpus_release_manifest,
    start_embedding,
    validate_corpus_release,
)
from app.ingestion.worker import _retrieval_documents_payload, run_once
from app.ingestion.workflow import append_run_event
from app.legal.enums import (
    CorpusReleaseStatus,
    ExtractionCandidateStatus,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    InstrumentType,
    LegalStatus,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    AuditEvent,
    Conversation,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256
from app.legal.schemas import CompositeReleaseCreate, CompositeReleaseMember
from app.models import User
from tests.api.routes.test_admin_ingestion import (
    _retire_existing_production_release,
    _source_and_run,
)
from tests.ingestion.test_worker import _create_retrieval_benchmark_dataset


@pytest.fixture(autouse=True)
def isolate_tasks(db: Session) -> Generator[None]:
    db.rollback()
    db.exec(delete(IngestionTask))
    db.commit()
    yield
    db.rollback()
    db.exec(delete(IngestionTask))
    db.commit()


@pytest.fixture
def members(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[CorpusRelease, list[CorpusRelease], EmbeddingProfile]:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "INGESTION_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "RETRIEVAL_INDEX_BACKEND", "pgvector")
    _retire_existing_production_release(db)
    for profile in db.exec(select(EmbeddingProfile)).all():
        profile.is_active = False
        db.add(profile)
    benchmark = f"composite-gold-{uuid.uuid4().hex}"
    profile = EmbeddingProfile(
        name=f"composite-profile-{uuid.uuid4().hex}",
        provider="openai",
        model_name="synthetic-test",
        model_revision="pinned",
        vector_dimensions=1024,
        configuration={"benchmark_dataset_version": benchmark},
    )
    db.add(profile)
    db.commit()
    releases: list[CorpusRelease] = []
    for index, kind in enumerate(
        (InstrumentType.CONSTITUTION, InstrumentType.ACT, InstrumentType.ACT)
    ):
        source, run = _source_and_run(db)
        instrument = db.get(LegalInstrument, source.legal_instrument_id)
        assert instrument
        instrument.instrument_type = kind
        instrument.short_title = (
            "Fixture Constitution" if index == 0 else f"Fixture Act {index}"
        )
        if index:
            instrument.slug = f"fixture-act-{uuid.uuid4().hex}"
        source.verification_status = "verified"
        run.status = "ready_to_embed"
        run.current_stage = "embedding"
        provision = Provision(
            instrument_id=instrument.id,
            kind="section",
            number="9",
            heading="Synthetic heading",
            canonical_path=f"{instrument.slug}.section9",
            sort_key="009",
        )
        db.add_all([source, instrument, provision, run])
        db.commit()
        text = f"Synthetic reviewed wording {instrument.slug}."
        version = ProvisionVersion(
            provision_id=provision.id,
            text=text,
            normalized_text=text.lower(),
            legal_status=LegalStatus.HISTORICAL,
            valid_from=date(2015, 1, 1),
            source_document_id=source.id,
            source_page_start=1,
            source_page_end=1,
            text_sha256=legal_text_sha256(text),
        )
        release = CorpusRelease(
            version=f"fixture-member-{uuid.uuid4().hex}",
            status=CorpusReleaseStatus.BUILDING,
            parser_version="fixture-v1",
        )
        db.add_all([version, release])
        db.commit()
        db.add(
            CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=source.id,
                ingestion_run_id=run.id,
            )
        )
        db.add(
            ExtractionCandidate(
                run_id=run.id,
                source_document_id=source.id,
                kind="section",
                number="9",
                canonical_path=provision.canonical_path,
                sort_key="009",
                raw_text=text,
                text_sha256=version.text_sha256,
                materialized_provision_id=provision.id,
                materialized_version_id=version.id,
                status=ExtractionCandidateStatus.MATERIALIZED,
            )
        )
        db.commit()
        release.source_manifest_hash = manifest_hash(
            entry_snapshot(db, release_entries(db, release.id))
        )
        entries = release_entries(db, release.id)
        documents = build_retrieval_documents(
            release_version=release.version,
            entries=entries,
            versions_by_id={version.id: version},
            provisions_by_id={provision.id: provision},
            instruments_by_id={instrument.id: instrument},
        )
        embedding = EmbeddingRun(
            release_id=release.id,
            profile_id=profile.id,
            status="succeeded",
            selected_for_release=True,
            metrics={"profile_fingerprint": profile_fingerprint(profile)},
        )
        db.add(embedding)
        db.flush()
        # Non-exact binary fractions exercise pgvector's float32 storage.
        vectors = [[0.123456789] + [0.0] * 1023]
        segments = write_segments(db, release_id=release.id, documents=documents)
        write_embeddings(
            db,
            release_id=release.id,
            embedding_run=embedding,
            profile=profile,
            segments=segments,
            vectors=vectors,
        )
        build = RetrievalIndexBuild(
            release_id=release.id,
            embedding_run_id=embedding.id,
            profile_id=profile.id,
            status="ready",
            expected_segment_count=1,
            stored_segment_count=1,
            stored_embedding_count=1,
            vector_dimensions=1024,
            validation_report={"is_valid": True},
        )
        db.add(build)
        content = json.dumps(
            {
                "documents": [doc.to_json() for doc in documents],
                "dense_vectors": vectors,
            }
        ).encode()
        blob = get_blob_store().put_artifact(
            run_id=str(run.id),
            artifact_type="embeddings",
            filename="fixture-embeddings.json",
            content=content,
            content_type="application/json",
        )
        db.add(
            IngestionArtifact(
                run_id=run.id,
                artifact_type="embeddings",
                storage_key=blob.key,
                sha256=hashlib.sha256(content).hexdigest(),
                artifact_metadata={"embedding_run_id": str(embedding.id)},
            )
        )
        if index == 0:
            _create_retrieval_benchmark_dataset(
                db, version=benchmark, canonical_path=provision.canonical_path
            )
            release.status = CorpusReleaseStatus.PRODUCTION
        else:
            release.status = CorpusReleaseStatus.APPROVED
        db.add(release)
        db.commit()
        releases.append(release)
    return releases[0], releases[1:], profile


def _body(
    members: tuple[CorpusRelease, list[CorpusRelease], EmbeddingProfile],
) -> CompositeReleaseCreate:
    base, acts, _profile = members
    return CompositeReleaseCreate(
        idempotency_key=f"compose-{uuid.uuid4()}",
        version=f"composite-{uuid.uuid4().hex}",
        base_release_id=base.id,
        expected_base_version=base.lock_version,
        members=[
            CompositeReleaseMember(release_id=act.id, expected_version=act.lock_version)
            for act in acts
        ],
    )


def _actor(db: Session) -> User:
    return db.exec(select(User).where(col(User.is_superuser).is_(True))).first()


def test_composition_preserves_union_provenance_manifest_and_idempotency(
    db: Session, members
) -> None:
    body = _body(members)
    release = compose_corpus_release(db, body, _actor(db))
    assert compose_corpus_release(db, body, _actor(db)).id == release.id
    entries = release_entries(db, release.id)
    assert len(entries) == 3
    assert not composition_gates(db, release, entries)
    _release, _artifact, manifest = read_corpus_release_manifest(db, release.id)
    assert manifest["entries"] == entry_snapshot(db, entries)
    assert len(manifest["composition"]["members"]) == 3
    assert len(manifest["source_documents"]) == 3
    assert {
        source["source_document_id"]: source["sha256"]
        for source in manifest["source_documents"]
    } == {
        row["source_document_id"]: row["source_sha256"] for row in manifest["entries"]
    }
    assert all(entry.ingestion_run_id for entry in entries)
    run = db.get(
        IngestionRun, uuid.UUID(release.validation_report["composition"]["run_id"])
    )
    assert _release_id_for_run(db, run) == release.id
    for member in [members[0], *members[1]]:
        origin = db.get(
            IngestionRun, release_entries(db, member.id)[0].ingestion_run_id
        )
        # A composite must not hijack an original run's release lookup.
        assert _release_id_for_run(db, origin) == member.id


@pytest.mark.parametrize(
    "defect",
    ["unapproved", "unverified", "review", "current", "source_identity", "text_hash"],
)
def test_unapproved_or_mismatched_act_cannot_be_composed(
    db: Session, members, defect: str
) -> None:
    act = members[1][0]
    entry = release_entries(db, act.id)[0]
    source = db.get(SourceDocument, entry.source_document_id)
    candidate = db.exec(
        select(ExtractionCandidate).where(
            ExtractionCandidate.run_id == entry.ingestion_run_id
        )
    ).one()
    if defect == "unapproved":
        act.status = CorpusReleaseStatus.BUILDING
    elif defect == "unverified":
        source.verification_status = "needs_review"
    elif defect == "review":
        candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
    elif defect == "text_hash":
        db.get(
            ProvisionVersion, entry.provision_version_id
        ).text += " unreviewed change"
    elif defect == "current":
        db.get(
            ProvisionVersion, entry.provision_version_id
        ).legal_status = LegalStatus.CURRENT
    else:
        entry.source_document_id = release_entries(db, members[1][1].id)[
            0
        ].source_document_id
    db.add_all([act, source, candidate, entry])
    db.commit()
    with pytest.raises(HTTPException) as error:
        compose_corpus_release(db, _body(members), _actor(db))
    assert error.value.status_code == 409


def test_changed_member_is_blocked_before_build_and_publication(
    db: Session, members
) -> None:
    release = compose_corpus_release(db, _body(members), _actor(db))
    act = members[1][0]
    source = db.get(SourceDocument, release_entries(db, act.id)[0].source_document_id)
    source.sha256 = "f" * 64
    db.add(source)
    db.commit()
    assert "composite_member_manifest_changed" in composition_gates(
        db, release, release_entries(db, release.id)
    )
    result = run_once(
        db, worker_id="composite-test", task_type="building_retrieval_documents"
    )
    assert result.task_status != "succeeded"
    release.status = CorpusReleaseStatus.APPROVED
    db.add(release)
    db.commit()
    with pytest.raises(HTTPException) as error:
        publish_corpus_release(
            db,
            release.id,
            expected_version=release.lock_version,
            idempotency_key=f"publish-{uuid.uuid4()}",
            current_user=_actor(db),
            superuser_override_reason=None,
        )
    assert "composite_member_manifest_changed" in error.value.detail["gates"]


def test_correcting_a_source_title_is_audited_and_keeps_composition_gates_clear(
    db: Session, members
) -> None:
    release = compose_corpus_release(db, _body(members), _actor(db))
    source = db.get(
        SourceDocument, release_entries(db, members[1][0].id)[0].source_document_id
    )
    previous_title = source.title
    version = source.lock_version
    key = f"correct-title-{uuid.uuid4()}"

    def correct() -> SourceDocument:
        return correct_source_document_title(
            db,
            source.id,
            title="Corrected source title",
            expected_version=version,
            idempotency_key=key,
            reason="Source is verified.",
            current_user=_actor(db),
        )

    corrected = correct()
    assert corrected.title == "Corrected source title"
    assert corrected.lock_version == version + 1
    assert correct().lock_version == version + 1
    assert not composition_gates(db, release, release_entries(db, release.id))
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.action == "source_document.title_corrected",
            AuditEvent.entity_id == source.id,
        )
    ).one()
    assert audit.reason == "Source is verified."
    assert audit.payload == {
        "previous_title": previous_title,
        "title": "Corrected source title",
    }
    with pytest.raises(HTTPException) as error:
        correct_source_document_title(
            db,
            source.id,
            title="Stale change",
            expected_version=version,
            idempotency_key=f"correct-title-{uuid.uuid4()}",
            reason="Source is verified.",
            current_user=_actor(db),
        )
    assert error.value.status_code == 409


def test_composite_build_reuses_vectors_promotes_and_preserves_conversation_pins(
    db: Session, members, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    base, acts, profile = members
    actor = _actor(db)
    base_build = db.exec(
        select(RetrievalIndexBuild).where(RetrievalIndexBuild.release_id == base.id)
    ).one()
    old = Conversation(
        user_id=actor.id, pinned_release_id=base.id, pinned_index_build_id=base_build.id
    )
    base_run_id = release_entries(db, base.id)[0].ingestion_run_id
    assert base_run_id is not None
    base_run = db.get(IngestionRun, base_run_id)
    assert base_run is not None
    base_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == base_run_id,
            IngestionStep.stage == IngestionStage.PUBLISHING,
        )
    ).one()
    base_run.status = IngestionRunStatus.PUBLISHED
    base_run.current_stage = IngestionStage.PUBLISHING
    base_step.status = IngestionStepStatus.SUCCEEDED
    db.add_all([old, base_run, base_step])
    db.commit()
    base_event = append_run_event(
        db,
        base_run,
        event_type="release_published",
        message="Base fixture published",
        step=base_step,
        stage=IngestionStage.PUBLISHING,
    )
    db.refresh(base_run)
    db.refresh(base_step)
    base_run_snapshot = base_run.model_dump()
    base_step_snapshot = base_step.model_dump()
    calls: list[list[str]] = []

    class Provider:
        def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
            calls.append(list(texts))
            return EmbeddingBatch(
                provider="openai",
                model_name=profile.model_name,
                model_revision=profile.model_revision,
                vectors=[[0.123456789] + [0.0] * 1023 for _text in texts],
                cost_usd=0,
            )

    monkeypatch.setattr(
        "app.ingestion.worker._embedding_provider_for_profile",
        lambda _profile: Provider(),
    )
    release = compose_corpus_release(db, _body(members), actor)
    assert (
        run_once(
            db, worker_id="composite-test", task_type="building_retrieval_documents"
        ).task_status
        == "succeeded"
    )
    run = db.get(
        IngestionRun, uuid.UUID(release.validation_report["composition"]["run_id"])
    )
    db.refresh(run)
    assert run.status == "ready_to_embed"
    start_embedding(
        db,
        run.id,
        expected_version=run.lock_version,
        idempotency_key=f"start-{uuid.uuid4()}",
        current_user=actor,
    )
    for stage in ("embedding", "indexing", "validating_index"):
        result = run_once(db, worker_id="composite-test", task_type=stage)
        assert result.task_status == "succeeded", db.get(
            IngestionTask, result.task_id
        ).error_details
    embedding = db.exec(
        select(EmbeddingRun).where(EmbeddingRun.release_id == release.id)
    ).one()
    assert embedding.metrics["document_embedding_metrics"]["reused_document_count"] == 3
    assert len(calls) == 1  # Only benchmark queries reach the provider.
    build = db.exec(
        select(RetrievalIndexBuild).where(RetrievalIndexBuild.release_id == release.id)
    ).one()
    assert validate_index_build(db, build=build, expected_segment_count=3)["is_valid"]
    db.refresh(release)
    validate_corpus_release(
        db,
        release.id,
        expected_version=release.lock_version,
        idempotency_key=f"validate-{uuid.uuid4()}",
        current_user=actor,
    )
    assert release.status == CorpusReleaseStatus.APPROVED
    publish_corpus_release(
        db,
        release.id,
        expected_version=release.lock_version,
        idempotency_key=f"publish-{uuid.uuid4()}",
        current_user=actor,
        superuser_override_reason=None,
    )
    db.refresh(old)
    db.refresh(run)
    db.refresh(base_run)
    db.refresh(base_step)
    assert base_run.model_dump() == base_run_snapshot
    assert base_step.model_dump() == base_step_snapshot
    assert db.exec(
        select(IngestionEvent.id).where(IngestionEvent.run_id == base_run_id)
    ).all() == [base_event.id]
    assert run.status == "published"
    for act in acts:
        added_run_id = release_entries(db, act.id)[0].ingestion_run_id
        assert added_run_id is not None
        added_run = db.get(IngestionRun, added_run_id)
        assert added_run is not None and added_run.status == "published"
        added_step = db.exec(
            select(IngestionStep).where(
                IngestionStep.run_id == added_run_id,
                IngestionStep.stage == IngestionStage.PUBLISHING,
            )
        ).one()
        assert added_step.status == IngestionStepStatus.SUCCEEDED
        assert db.exec(
            select(IngestionEvent.id).where(
                IngestionEvent.run_id == added_run_id,
                IngestionEvent.event_type == "release_published",
            )
        ).one()
    assert old.pinned_release_id == base.id
    assert old.pinned_index_build_id == base_build.id
    assert db.get(CorpusRelease, base.id).status == CorpusReleaseStatus.RETIRED
    assert (
        db.exec(
            select(ActiveRetrievalTarget).where(
                ActiveRetrievalTarget.index_kind == "enacted"
            )
        )
        .one()
        .release_id
        == release.id
    )
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    response = client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    new = db.get(Conversation, uuid.UUID(response.json()["id"]))
    assert new.pinned_release_id == release.id


def test_compose_api_requires_publisher_and_returns_instrument_slugs(
    client: TestClient,
    members,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    body = _body(members).model_dump(mode="json")
    path = "/api/v1/admin/corpus-releases/compose"
    assert (
        client.post(path, json=body, headers=normal_user_token_headers).status_code
        == 403
    )
    result = client.post(path, json=body, headers=superuser_token_headers)
    assert result.status_code == 201
    assert len(result.json()["instrument_slugs"]) == 3


@pytest.mark.parametrize(
    "defect", ["stale_member", "stale_base", "changed_request", "duplicate_version"]
)
def test_composition_rejects_stale_versions_and_conflicting_retries(
    db: Session, members, defect: str
) -> None:
    body = _body(members)
    actor = _actor(db)
    if defect == "stale_member":
        body.members[0].expected_version += 1
    elif defect == "stale_base":
        body.expected_base_version += 1
    else:
        compose_corpus_release(db, body, actor)
        if defect == "changed_request":
            body.version += "-changed"
        else:
            body.idempotency_key = f"another-{uuid.uuid4()}"
    with pytest.raises(HTTPException) as error:
        compose_corpus_release(db, body, actor)
    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "defect", ["text", "profile", "missing_artifact", "corrupt_artifact"]
)
def test_vector_reuse_requires_exact_inputs_and_retained_evidence(
    db: Session, members, defect: str
) -> None:
    release = compose_corpus_release(db, _body(members), _actor(db))
    assert (
        run_once(
            db, worker_id="composite-test", task_type="building_retrieval_documents"
        ).task_status
        == "succeeded"
    )
    run = db.get(
        IngestionRun, uuid.UUID(release.validation_report["composition"]["run_id"])
    )
    documents = _retrieval_documents_payload(db, run, release.id)["documents"]
    profile = members[2]
    assert len(member_document_vectors(db, release, profile, documents)) == 3
    if defect == "text":
        documents[0]["retrieval_text"] += " changed"
        assert len(member_document_vectors(db, release, profile, documents)) == 2
    elif defect == "profile":
        profile.configuration = {**profile.configuration, "prefix": "different inputs"}
        assert not member_document_vectors(db, release, profile, documents)
    else:
        origin_run_id = release_entries(db, members[0].id)[0].ingestion_run_id
        artifact = db.exec(
            select(IngestionArtifact).where(
                IngestionArtifact.run_id == origin_run_id,
                IngestionArtifact.artifact_type == "embeddings",
            )
        ).one()
        if defect == "missing_artifact":
            db.delete(artifact)
            db.commit()
            assert len(member_document_vectors(db, release, profile, documents)) == 2
        else:
            get_blob_store().read_bytes(artifact.storage_key)
            path = Path(settings.INGESTION_STORAGE_DIR) / artifact.storage_key
            path.write_bytes(b"corrupted review fixture")
            with pytest.raises(ValueError, match="artifact checksum mismatch"):
                member_document_vectors(db, release, profile, documents)
