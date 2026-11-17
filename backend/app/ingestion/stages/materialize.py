import hashlib
import json
import uuid

from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.common import get_datetime_utc
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.inputs import retain_pipeline_inputs
from app.ingestion.runtime.types import StageOutcome
from app.ingestion.stages.artifacts import ensure_artifact, sha256_json
from app.ingestion.stages.candidates import (
    candidate_text_for_materialization,
    run_parser_version,
)
from app.ingestion.stages.manifests import release_manifest
from app.ingestion.stages.materialize_versions import (
    block_unclassified_current_law_changes,
    parent_provision_id_for_candidate,
    resolve_corpus_legal_status,
    sync_release_entries,
    upsert_current_version_from_candidate,
    upsert_historical_version_from_candidate,
    upsert_provision_from_candidate,
)
from app.ingestion.stages.sources import get_source_for_run
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    CorpusReleaseStatus,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    InstrumentType,
    LegalStatus,
    ReviewIssueStatus,
    VerificationStatus,
)
from app.legal.models import (
    CorpusRelease,
    ExtractionCandidate,
    IngestionRun,
    IngestionTask,
    LegalInstrument,
    ReviewIssue,
)


def handle_materializing(
    session: Session, run: IngestionRun, task: IngestionTask
) -> StageOutcome:
    source = get_source_for_run(session, run, task)
    if source.verification_status != VerificationStatus.VERIFIED:
        raise IngestionWorkerError(
            "Source document must be verified before materialization"
        )
    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    if not instrument:
        raise IngestionWorkerError(
            "Source document is not linked to a legal instrument"
        )
    candidates = approved_candidates_for_run(session, run)
    if not candidates:
        raise IngestionWorkerError(
            "Run does not have reviewed candidates to materialize"
        )
    ensure_no_open_blocking_issues(session, candidates)

    if (
        str(instrument.instrument_type)
        not in settings.INGESTION_ALLOWED_INSTRUMENT_TYPES
    ):
        raise IngestionWorkerError(
            f"Ingestion is disabled for instrument type: {instrument.instrument_type}"
        )
    corpus_legal_status = resolve_corpus_legal_status(run, instrument=instrument)
    if instrument.instrument_type == InstrumentType.ACT:
        run.pipeline_config = {
            **(run.pipeline_config or {}),
            "corpus_legal_status": "historical",
            "source_edition_review": {
                "edition": f"As enacted, {instrument.year}",
                "notice": "As enacted, may have been amended.",
                "instrument_slug": instrument.slug,
            },
        }
    provision_ids_by_candidate_id: dict[uuid.UUID, uuid.UUID] = {}
    materialized_version_ids: set[uuid.UUID] = set()
    created_provisions = 0
    created_versions = 0
    reused_versions = 0
    superseded_versions = 0
    changed_current_law_text_count = (
        block_unclassified_current_law_changes(
            session, source=source, candidates=candidates
        )
        if corpus_legal_status == LegalStatus.CURRENT
        else 0
    )
    if changed_current_law_text_count:
        session.commit()
        return StageOutcome(
            metrics={
                "candidate_count": len(candidates),
                "changed_current_law_text_count": changed_current_law_text_count,
                "blocking_issue_count": changed_current_law_text_count,
            },
            next_stage=IngestionStage.REVIEW,
            next_status=IngestionRunStatus.WAITING_FOR_REVIEW,
            block_next_stage=True,
        )

    for candidate in candidates:
        parent_id = parent_provision_id_for_candidate(
            session,
            candidate,
            provision_ids_by_candidate_id=provision_ids_by_candidate_id,
        )
        provision, provision_created = upsert_provision_from_candidate(
            session, instrument=instrument, candidate=candidate, parent_id=parent_id
        )
        provision_ids_by_candidate_id[candidate.id] = provision.id
        if provision_created:
            created_provisions += 1

        candidate.materialized_provision_id = provision.id
        text = candidate_text_for_materialization(session, candidate)
        if text:
            upsert_version = (
                upsert_historical_version_from_candidate
                if corpus_legal_status == LegalStatus.HISTORICAL
                else upsert_current_version_from_candidate
            )
            version, version_action = upsert_version(
                session,
                source=source,
                instrument=instrument,
                provision=provision,
                candidate=candidate,
                text=text,
            )
            candidate.materialized_version_id = version.id
            materialized_version_ids.add(version.id)
            if version_action == "created":
                created_versions += 1
            elif version_action == "reused":
                reused_versions += 1
            else:
                superseded_versions += 1
        candidate.status = ExtractionCandidateStatus.MATERIALIZED
        candidate.lock_version += 1
        candidate.updated_at = get_datetime_utc()
        session.add(candidate)

    release = run_release(session, run=run, instrument=instrument)
    entries = sync_release_entries(
        session,
        release=release,
        run=run,
        instrument=instrument,
        materialized_version_ids=materialized_version_ids,
    )
    manifest = release_manifest(
        session,
        release=release,
        run=run,
        source=source,
        entries=entries,
    )
    release.source_manifest_hash = sha256_json(manifest["entries"])
    release.parser_version = run_parser_version(run)
    release.validation_report = {
        "entry_count": len(entries),
        "instrument_slug": instrument.slug,
        "corpus_legal_status": corpus_legal_status.value,
        "source_edition_review": (run.pipeline_config or {}).get(
            "source_edition_review"
        ),
        "materialized_run_id": str(run.id),
        "ingestion_run_ids": manifest["ingestion_run_ids"],
        "source_document_ids": manifest["source_document_ids"],
        "source_document_count": len(manifest["source_document_ids"]),
        "unresolved_gates": [
            "retrieval_documents_pending",
            "selected_embedding_run_missing",
            "ready_retrieval_index_build_missing",
        ],
    }
    session.add(release)
    manifest_content = json.dumps(manifest, sort_keys=True).encode()
    # Artifacts are immutable: a manifest rebuilt after a review correction is
    # stored beside the earlier one, and readers take the newest for the release.
    manifest_hash = hashlib.sha256(manifest_content).hexdigest()[:16]
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST.value,
        filename=f"release-{release.version}-{manifest_hash}.json",
        content=manifest_content,
        content_type="application/json",
        metadata={
            "release_id": str(release.id),
            "source_manifest_hash": release.source_manifest_hash,
        },
    )
    ensure_artifact(
        session,
        run_id=run.id,
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST,
        storage_key=blob.key,
        sha256=blob.sha256,
        mime_type=blob.content_type,
        metadata={
            "release_id": str(release.id),
            "source_manifest_hash": release.source_manifest_hash,
            "entry_count": len(entries),
        },
    )
    retain_pipeline_inputs(session, run, {"release_id": str(release.id)})
    session.commit()
    return StageOutcome(
        metrics={
            "release_id": str(release.id),
            "release_version": release.version,
            "candidate_count": len(candidates),
            "created_provisions": created_provisions,
            "created_versions": created_versions,
            "reused_versions": reused_versions,
            "superseded_versions": superseded_versions,
            "release_entry_count": len(entries),
            "source_manifest_hash": release.source_manifest_hash,
        },
        next_stage=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
        next_task_payload={
            "source_document_id": str(source.id),
            "release_id": str(release.id),
        },
    )


def approved_candidates_for_run(
    session: Session, run: IngestionRun
) -> list[ExtractionCandidate]:
    # Rejected candidates are a final review decision and are never materialized.
    candidates = list(
        session.exec(
            select(ExtractionCandidate)
            .where(
                ExtractionCandidate.run_id == run.id,
                ExtractionCandidate.status != ExtractionCandidateStatus.REJECTED,
            )
            .order_by(col(ExtractionCandidate.sort_key), col(ExtractionCandidate.id))
        ).all()
    )
    unapproved = [
        candidate
        for candidate in candidates
        if candidate.status
        not in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.AUTO_APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }
    ]
    if unapproved:
        raise IngestionWorkerError(
            "All extraction candidates must be approved before materialization"
        )
    return candidates


def ensure_no_open_blocking_issues(
    session: Session, candidates: list[ExtractionCandidate]
) -> None:
    candidate_ids = [candidate.id for candidate in candidates]
    if not candidate_ids:
        return
    issue = session.exec(
        select(ReviewIssue).where(
            col(ReviewIssue.candidate_id).in_(candidate_ids),
            ReviewIssue.blocking == True,  # noqa: E712
            ReviewIssue.status == ReviewIssueStatus.OPEN,
        )
    ).first()
    if issue:
        raise IngestionWorkerError(
            "Blocking review issues must be resolved before materialization"
        )


def run_release(
    session: Session, *, run: IngestionRun, instrument: LegalInstrument
) -> CorpusRelease:
    version = f"draft-{run.id.hex[:12]}"
    release = session.exec(
        select(CorpusRelease).where(CorpusRelease.version == version)
    ).first()
    if release:
        return release
    release = CorpusRelease(
        version=version,
        status=CorpusReleaseStatus.BUILDING,
        parser_version=run_parser_version(run),
        validation_report={
            "instrument_slug": instrument.slug,
            "materialized_run_id": str(run.id),
        },
    )
    session.add(release)
    session.flush()
    return release
