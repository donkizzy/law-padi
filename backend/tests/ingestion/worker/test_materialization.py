import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.queue import enqueue_task
from app.ingestion.runtime.runner import run_once, run_until_idle
from app.ingestion.worker import _upsert_historical_version_from_candidate
from app.legal.enums import (
    CorpusReleaseStatus,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    LegalStatus,
    ProvisionKind,
    VerificationStatus,
)
from app.legal.models import (
    CandidateRevision,
    CorpusRelease,
    CorpusReleaseEntry,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionStep,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    ReviewIssue,
)
from app.legal.parser import legal_text_sha256, normalize_legal_text
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages
from tests.ingestion.worker.conftest import (
    _approved_candidate,
    _clear_run_tasks,
    _store_raw_extraction,
    _stored_source_and_run,
)


@pytest.mark.parametrize("corpus_status", [LegalStatus.CURRENT, LegalStatus.HISTORICAL])
def test_worker_materializes_approved_candidates_and_builds_retrieval_artifact(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus_status: LegalStatus,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"CHAPTER IV Fundamental Rights {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    run.pipeline_config = {"corpus_legal_status": corpus_status.value}
    db.add(run)
    db.commit()
    _clear_run_tasks(db, run)
    _store_raw_extraction(
        db,
        tmp_path=tmp_path,
        run=run,
        source=source,
        page_number=1,
        text=(
            "CHAPTER IV - Fundamental Rights\n"
            "PART I Rights\n"
            "37. Right to private and family life\n"
            "(1) The privacy of citizens is hereby guaranteed and protected."
        ),
    )
    normalizing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.NORMALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=normalizing_step,
        task_type=IngestionStage.NORMALIZING.value,
        idempotency_key=f"{run.id}:normalize",
        payload={"source_document_id": str(source.id)},
    )
    run_until_idle(db, worker_id="worker-test", max_tasks=3)
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    candidates = db.exec(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.run_id == run.id)
        .order_by(ExtractionCandidate.sort_key)
    ).all()
    for candidate in candidates:
        candidate.status = ExtractionCandidateStatus.APPROVED
        candidate.blocking_issue_count = 0
        db.add(candidate)
    db.add(source)
    db.commit()
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize",
        payload={"source_document_id": str(source.id)},
    )

    results = run_until_idle(db, worker_id="worker-test", max_tasks=2)

    assert [result.stage for result in results] == [
        IngestionStage.MATERIALIZING,
        IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
    ]
    assert [result.task_status for result in results] == [
        IngestionTaskStatus.SUCCEEDED,
        IngestionTaskStatus.SUCCEEDED,
    ]
    db.refresh(run)
    assert run.status == IngestionRunStatus.READY_TO_EMBED
    assert run.current_stage == IngestionStage.EMBEDDING

    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provisions = db.exec(
        select(Provision)
        .where(Provision.instrument_id == instrument.id)
        .order_by(Provision.sort_key)
    ).all()
    assert [str(provision.kind) for provision in provisions] == [
        ProvisionKind.CHAPTER.value,
        ProvisionKind.PART.value,
        ProvisionKind.SECTION.value,
        ProvisionKind.SUBSECTION.value,
    ]
    assert provisions[1].parent_id == provisions[0].id
    assert provisions[2].parent_id == provisions[1].id
    assert provisions[3].parent_id == provisions[2].id

    section_version = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == provisions[2].id
        )
    ).one()
    assert section_version.provision_id == provisions[2].id
    assert section_version.text == (
        "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert section_version.valid_from == date(1999, 5, 29)
    assert section_version.legal_status == corpus_status
    subsection_version = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == provisions[3].id
        )
    ).one()
    assert subsection_version.text == (
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )

    release = db.exec(
        select(CorpusRelease).where(CorpusRelease.version == f"draft-{run.id.hex[:12]}")
    ).one()
    assert release.status == CorpusReleaseStatus.BUILDING
    assert release.source_manifest_hash
    entries = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    assert {entry.provision_version_id for entry in entries} == {
        section_version.id,
        subsection_version.id,
    }
    assert {entry.ingestion_run_id for entry in entries} == {run.id}

    artifacts = db.exec(
        select(IngestionArtifact).where(IngestionArtifact.run_id == run.id)
    ).all()
    artifact_types = {artifact.artifact_type for artifact in artifacts}
    assert IngestionArtifactType.RELEASE_MANIFEST in artifact_types
    assert IngestionArtifactType.RETRIEVAL_DOCUMENTS in artifact_types
    retrieval_artifact = next(
        artifact
        for artifact in artifacts
        if artifact.artifact_type == IngestionArtifactType.RETRIEVAL_DOCUMENTS
    )
    retrieval_payload = json.loads(
        LocalBlobStore(tmp_path).read_bytes(retrieval_artifact.storage_key)
    )
    assert retrieval_payload["document_count"] == 2
    document = next(
        item
        for item in retrieval_payload["documents"]
        if item["citation"] == "Section 37"
    )
    assert document["citation"] == "Section 37"
    assert document["ancestor_headings"] == ["Fundamental Rights", "Rights"]
    assert (
        document["authoritative_text"] == "Right to private and family life\n"
        "(1) The privacy of citizens is hereby guaranteed and protected."
    )
    assert "Section 37" in document["retrieval_text"]
    assert document["payload"]["legal_status"] == corpus_status.value

    embedding_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.EMBEDDING,
        )
    ).one()
    assert embedding_step.status == IngestionStepStatus.BLOCKED


def test_historical_materialization_does_not_reuse_current_law(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    source, run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=_pdf_with_pages([uuid.uuid4().hex])
    )
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    candidate = _approved_candidate(db, run=run, source=source, text="Source wording")
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        canonical_path=candidate.canonical_path,
        sort_key="037",
    )
    db.add(provision)
    db.flush()
    current = ProvisionVersion(
        provision_id=provision.id,
        text="Source wording",
        normalized_text="source wording",
        valid_from=date(1999, 5, 29),
        source_document_id=source.id,
        text_sha256=legal_text_sha256("Source wording"),
    )
    db.add(current)
    db.commit()
    with pytest.raises(IngestionWorkerError, match="separate provision identity"):
        _upsert_historical_version_from_candidate(
            db,
            source=source,
            instrument=instrument,
            provision=provision,
            candidate=candidate,
            text="Source wording",
        )
    assert current.legal_status == LegalStatus.CURRENT
    assert current.valid_until is None


def test_materialization_release_snapshot_is_cumulative_across_sources_and_runs(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    first_pdf = _pdf_with_pages([f"37. First source {uuid.uuid4().hex}"])
    first_source, first_run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=first_pdf
    )
    _clear_run_tasks(db, first_run)
    first_source.verification_status = VerificationStatus.VERIFIED
    instrument = db.get(LegalInstrument, first_source.legal_instrument_id)
    assert instrument
    first_provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="037",
    )
    db.add(first_provision)
    db.commit()
    db.refresh(first_provision)
    first_version = ProvisionVersion(
        provision_id=first_provision.id,
        text="Existing current Section 37 text.",
        normalized_text=normalize_legal_text("Existing current Section 37 text."),
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=first_source.id,
        source_page_start=1,
        source_page_end=1,
        text_sha256=legal_text_sha256("Existing current Section 37 text."),
    )
    db.add(first_version)
    db.commit()
    db.refresh(first_version)
    first_candidate = _approved_candidate(
        db,
        run=first_run,
        source=first_source,
        number="37",
        canonical_path=first_provision.canonical_path,
        heading=first_provision.heading or "",
        sort_key=first_provision.sort_key,
        text=first_version.text,
    )
    first_candidate.status = ExtractionCandidateStatus.MATERIALIZED
    first_candidate.materialized_provision_id = first_provision.id
    first_candidate.materialized_version_id = first_version.id
    db.add(first_source)
    db.add(first_candidate)
    db.commit()

    second_pdf = _pdf_with_pages([f"38. Second source {uuid.uuid4().hex}"])
    second_source, second_run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=second_pdf, instrument=instrument
    )
    _clear_run_tasks(db, second_run)
    second_source.verification_status = VerificationStatus.VERIFIED
    second_candidate = _approved_candidate(
        db,
        run=second_run,
        source=second_source,
        number="38",
        canonical_path=f"{instrument.slug}.section38",
        heading="Right to freedom of thought",
        sort_key="038",
        text="New current Section 38 text.",
    )
    db.add(second_source)
    db.commit()
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == second_run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=second_run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{second_run.id}:materialize-cumulative",
        payload={"source_document_id": str(second_source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.stage == IngestionStage.MATERIALIZING
    db.refresh(second_candidate)
    assert second_candidate.materialized_version_id
    release = db.exec(
        select(CorpusRelease).where(
            CorpusRelease.version == f"draft-{second_run.id.hex[:12]}"
        )
    ).one()
    entries = db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    entries_by_version = {entry.provision_version_id: entry for entry in entries}
    assert set(entries_by_version) == {
        first_version.id,
        second_candidate.materialized_version_id,
    }
    assert entries_by_version[first_version.id].source_document_id == first_source.id
    assert entries_by_version[first_version.id].ingestion_run_id == first_run.id
    assert (
        entries_by_version[second_candidate.materialized_version_id].source_document_id
        == second_source.id
    )
    assert (
        entries_by_version[second_candidate.materialized_version_id].ingestion_run_id
        == second_run.id
    )
    assert release.validation_report
    assert release.validation_report["source_document_count"] == 2
    assert set(release.validation_report["ingestion_run_ids"]) == {
        str(first_run.id),
        str(second_run.id),
    }
    manifest_artifact = db.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == second_run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.RELEASE_MANIFEST,
        )
    ).one()
    manifest = json.loads(
        LocalBlobStore(tmp_path).read_bytes(manifest_artifact.storage_key)
    )
    assert set(manifest["source_document_ids"]) == {
        str(first_source.id),
        str(second_source.id),
    }
    assert set(manifest["ingestion_run_ids"]) == {
        str(first_run.id),
        str(second_run.id),
    }
    assert {
        source_doc["source_document_id"] for source_doc in manifest["source_documents"]
    } == {str(first_source.id), str(second_source.id)}


def test_materialization_requires_document_source_verification(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf, max_attempts=1)
    _clear_run_tasks(db, run)
    candidate = _approved_candidate(db, run=run, source=source, text="Verified text")
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    materializing_task = enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-unverified",
        payload={"source_document_id": str(source.id)},
    )
    materializing_task.max_attempts = 1
    db.add(materializing_task)
    db.commit()

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.task_status == IngestionTaskStatus.FAILED
    db.refresh(candidate)
    assert candidate.materialized_version_id is None
    db.refresh(run)
    assert run.status == IngestionRunStatus.FAILED
    assert run.error_details
    assert "verified" in run.error_details["message"]


def test_materialization_skips_rejected_candidates_and_their_findings(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf, max_attempts=1)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    db.add(source)
    approved = _approved_candidate(db, run=run, source=source, text="Verified text")
    rejected = _approved_candidate(
        db,
        run=run,
        source=source,
        text="Duplicate scan (of section 37",
        canonical_path=f"{approved.canonical_path}.rejected-duplicate",
        sort_key="999",
    )
    rejected.status = ExtractionCandidateStatus.REJECTED
    rejected.blocking_issue_count = 1
    db.add(rejected)
    db.add(
        ReviewIssue(
            candidate_id=rejected.id,
            issue_type="unbalanced_punctuation",
            blocking=True,
            message="Unbalanced brackets in a rejected duplicate.",
        )
    )
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    db.commit()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-with-rejected",
        payload={"source_document_id": str(source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.task_status == IngestionTaskStatus.SUCCEEDED
    db.refresh(approved)
    db.refresh(rejected)
    assert approved.status == ExtractionCandidateStatus.MATERIALIZED
    assert approved.materialized_version_id is not None
    assert rejected.status == ExtractionCandidateStatus.REJECTED
    assert rejected.materialized_provision_id is None


def test_rematerialization_after_review_correction_stores_a_new_manifest(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"65. Interpretation {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf, max_attempts=1)
    _clear_run_tasks(db, run)
    # As-enacted Act text: the release holds exactly what this run materialized.
    run.pipeline_config = {**(run.pipeline_config or {}), "instrument_parser": "act"}
    db.add(run)
    source.verification_status = VerificationStatus.VERIFIED
    source.verified_at = datetime.now(UTC)
    db.add(source)
    section = _approved_candidate(db, run=run, source=source, text="Section text")
    fake = _approved_candidate(
        db,
        run=run,
        source=source,
        text="(a) part of a definition",
        canonical_path=f"{section.canonical_path}.paragrapha",
        sort_key="999",
    )
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    db.commit()

    for attempt in ("first", "corrected"):
        if attempt == "corrected":
            # A reviewer rejects an item after the first materialization.
            fake.status = ExtractionCandidateStatus.REJECTED
            db.add(fake)
            release = db.exec(
                select(CorpusRelease).where(
                    CorpusRelease.version == f"draft-{run.id.hex[:12]}"
                )
            ).one()
            for entry in db.exec(
                select(CorpusReleaseEntry).where(
                    CorpusReleaseEntry.release_id == release.id,
                    CorpusReleaseEntry.provision_version_id
                    == fake.materialized_version_id,
                )
            ).all():
                db.delete(entry)
            db.commit()
        enqueue_task(
            db,
            run=run,
            step=materializing_step,
            task_type=IngestionStage.MATERIALIZING.value,
            idempotency_key=f"{run.id}:materialize-{attempt}",
            payload={"source_document_id": str(source.id)},
        )
        result = run_once(db, worker_id="worker-test")
        assert result is not None
        assert result.task_status == IngestionTaskStatus.SUCCEEDED
        _clear_run_tasks(db, run)

    manifests = db.exec(
        select(IngestionArtifact)
        .where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.artifact_type == IngestionArtifactType.RELEASE_MANIFEST,
        )
        .order_by(col(IngestionArtifact.created_at))
    ).all()
    assert len(manifests) == 2
    latest = json.loads(LocalBlobStore(tmp_path).read_bytes(manifests[-1].storage_key))
    assert len(latest["entries"]) == 1


def test_materialization_blocks_changed_current_law_without_revision_metadata(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    db.add(source)
    db.commit()
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Bad old heading",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="999",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    bad_version = ProvisionVersion(
        provision_id=provision.id,
        text="Incorrect seeded text.",
        normalized_text="incorrect seeded text.",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        text_sha256=legal_text_sha256("Incorrect seeded text."),
    )
    db.add(bad_version)
    db.commit()
    db.refresh(bad_version)
    candidate = _approved_candidate(
        db,
        run=run,
        source=source,
        canonical_path=provision.canonical_path,
        heading="Right to private and family life",
        sort_key="037",
        text="Correct official text.",
    )
    db.add(
        CandidateRevision(
            candidate_id=candidate.id,
            revision_number=2,
            previous_text=candidate.raw_text,
            revised_text="Correct official text after review.",
            reason="Reviewer corrected seeded text.",
        )
    )
    candidate.revision_number = 2
    db.add(candidate)
    db.commit()
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-replace",
        payload={"source_document_id": str(source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.stage == IngestionStage.MATERIALIZING
    assert result.task_status == IngestionTaskStatus.SUCCEEDED
    db.refresh(provision)
    db.refresh(bad_version)
    db.refresh(candidate)
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_REVIEW
    assert run.current_stage == IngestionStage.REVIEW
    assert provision.heading == "Bad old heading"
    assert provision.sort_key == "999"
    assert bad_version.text == "Incorrect seeded text."
    assert bad_version.legal_status == LegalStatus.CURRENT
    assert bad_version.valid_until is None
    assert candidate.materialized_version_id is None
    assert candidate.status == ExtractionCandidateStatus.NEEDS_REVIEW
    assert db.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == provision.id)
    ).all() == [bad_version]
    issue = db.exec(
        select(ReviewIssue).where(
            ReviewIssue.candidate_id == candidate.id,
            ReviewIssue.issue_type == "changed_current_law_text",
        )
    ).one()
    assert issue.blocking
    assert issue.evidence
    assert issue.evidence["current_version_id"] == str(bad_version.id)


def test_materialization_supersedes_current_version_for_classified_legal_revision(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
    source.is_legal_revision = True
    source.legal_revision_effective_at = date(2024, 1, 1)
    db.add(source)
    db.commit()
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.section37",
        sort_key="037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    current_version = ProvisionVersion(
        provision_id=provision.id,
        text="Original current text.",
        normalized_text="original current text.",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        text_sha256=legal_text_sha256("Original current text."),
    )
    db.add(current_version)
    db.commit()
    db.refresh(current_version)
    candidate = _approved_candidate(
        db,
        run=run,
        source=source,
        canonical_path=provision.canonical_path,
        text="Revised current text.",
    )
    materializing_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.MATERIALIZING,
        )
    ).one()
    enqueue_task(
        db,
        run=run,
        step=materializing_step,
        task_type=IngestionStage.MATERIALIZING.value,
        idempotency_key=f"{run.id}:materialize-legal-revision",
        payload={"source_document_id": str(source.id)},
    )

    result = run_once(db, worker_id="worker-test")

    assert result is not None
    assert result.stage == IngestionStage.MATERIALIZING
    db.refresh(current_version)
    db.refresh(candidate)
    assert current_version.text == "Original current text."
    assert current_version.legal_status == LegalStatus.SUPERSEDED
    assert current_version.valid_until == date(2024, 1, 1)
    versions = db.exec(
        select(ProvisionVersion)
        .where(ProvisionVersion.provision_id == provision.id)
        .order_by(ProvisionVersion.revision_number)
    ).all()
    assert len(versions) == 2
    assert versions[1].text == "Revised current text."
    assert versions[1].legal_status == LegalStatus.CURRENT
    assert versions[1].valid_from == date(2024, 1, 1)
    assert versions[1].supersedes_id == current_version.id
    assert candidate.materialized_version_id == versions[1].id
