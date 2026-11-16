import uuid
from datetime import date

from sqlmodel import Session, col, select

from app.ingestion.common import get_datetime_utc
from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.stages.candidates import (
    candidate_text_for_materialization,
    ensure_review_issue,
)
from app.ingestion.stages.manifests import materialized_run_ids_by_version
from app.legal.enums import (
    ExtractionCandidateStatus,
    InstrumentType,
    LegalStatus,
    ReviewIssueSeverity,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    ExtractionCandidate,
    IngestionRun,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.parser import (
    legal_text_sha256,
    normalize_legal_text,
)


def parent_provision_id_for_candidate(
    session: Session,
    candidate: ExtractionCandidate,
    *,
    provision_ids_by_candidate_id: dict[uuid.UUID, uuid.UUID],
) -> uuid.UUID | None:
    if not candidate.parent_candidate_id:
        return None
    parent_id = provision_ids_by_candidate_id.get(candidate.parent_candidate_id)
    if parent_id:
        return parent_id
    parent_candidate = session.get(ExtractionCandidate, candidate.parent_candidate_id)
    if parent_candidate and parent_candidate.materialized_provision_id:
        return parent_candidate.materialized_provision_id
    raise IngestionWorkerError(
        f"Parent candidate for {candidate.canonical_path} is not materialized"
    )


def upsert_provision_from_candidate(
    session: Session,
    *,
    instrument: LegalInstrument,
    candidate: ExtractionCandidate,
    parent_id: uuid.UUID | None,
) -> tuple[Provision, bool]:
    provision = session.exec(
        select(Provision).where(Provision.canonical_path == candidate.canonical_path)
    ).first()
    created = False
    if not provision:
        provision = Provision(
            instrument_id=instrument.id,
            parent_id=parent_id,
            kind=candidate.kind,
            number=candidate.number,
            heading=candidate.heading,
            canonical_path=candidate.canonical_path,
            sort_key=candidate.sort_key,
        )
        created = True
    else:
        provision.instrument_id = instrument.id
        provision.parent_id = parent_id
        provision.kind = candidate.kind
        provision.number = candidate.number
        provision.heading = candidate.heading
        provision.sort_key = candidate.sort_key
    session.add(provision)
    session.flush()
    return provision, created


def resolve_corpus_legal_status(
    run: IngestionRun, *, instrument: LegalInstrument | None = None
) -> LegalStatus:
    if (instrument and instrument.instrument_type == InstrumentType.ACT) or (
        run.pipeline_config or {}
    ).get("instrument_parser") == "act":
        return LegalStatus.HISTORICAL
    value = (run.pipeline_config or {}).get("corpus_legal_status", "current")
    if value not in {LegalStatus.CURRENT.value, LegalStatus.HISTORICAL.value}:
        raise IngestionWorkerError("Corpus legal status must be current or historical")
    return LegalStatus(value)


def upsert_historical_version_from_candidate(
    session: Session,
    *,
    source: SourceDocument,
    instrument: LegalInstrument,
    provision: Provision,
    candidate: ExtractionCandidate,
    text: str,
) -> tuple[ProvisionVersion, str]:
    """Store a source edition without changing or reusing current-law versions."""
    text_sha256 = legal_text_sha256(text)
    versions = session.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == provision.id)
    ).all()
    for version in versions:
        if (
            version.legal_status == LegalStatus.HISTORICAL
            and version.source_document_id == source.id
            and version.text_sha256 == text_sha256
        ):
            return version, "reused"
    if versions:
        raise IngestionWorkerError(
            "Historical source editions need a separate provision identity or "
            "reviewed validity dates when versions already exist"
        )
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalize_legal_text(text),
        valid_from=version_valid_from(instrument, source),
        legal_status=LegalStatus.HISTORICAL,
        source_document_id=source.id,
        source_page_start=candidate.source_page_start,
        source_page_end=candidate.source_page_end,
        text_sha256=text_sha256,
    )
    session.add(version)
    session.flush()
    return version, "created"


def upsert_current_version_from_candidate(
    session: Session,
    *,
    source: SourceDocument,
    instrument: LegalInstrument,
    provision: Provision,
    candidate: ExtractionCandidate,
    text: str,
) -> tuple[ProvisionVersion, str]:
    normalized_text = normalize_legal_text(text)
    text_sha256 = legal_text_sha256(text)
    current_version = current_version_for_provision(session, provision.id)
    if current_version and current_version.text_sha256 == text_sha256:
        return current_version, "reused"
    if current_version:
        if not source.is_legal_revision or not source.legal_revision_effective_at:
            raise IngestionWorkerError(
                "Changed current-law text requires legal revision metadata"
            )
        if source.legal_revision_effective_at <= current_version.valid_from:
            raise IngestionWorkerError(
                "Legal revision effective date must be after the current version start"
            )
        current_version.legal_status = LegalStatus.SUPERSEDED
        current_version.valid_until = source.legal_revision_effective_at
        session.add(current_version)
        version = ProvisionVersion(
            provision_id=provision.id,
            text=text,
            normalized_text=normalized_text,
            valid_from=source.legal_revision_effective_at,
            legal_status=LegalStatus.CURRENT,
            revision_number=next_version_number(session, provision.id),
            source_document_id=source.id,
            source_page_start=candidate.source_page_start,
            source_page_end=candidate.source_page_end,
            text_sha256=text_sha256,
            supersedes_id=current_version.id,
        )
        session.add(version)
        session.flush()
        candidate.normalized_text = normalized_text
        candidate.text_sha256 = text_sha256
        return version, "superseded"

    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalized_text,
        valid_from=version_valid_from(instrument, source),
        legal_status=LegalStatus.CURRENT,
        revision_number=next_version_number(session, provision.id),
        source_document_id=source.id,
        source_page_start=candidate.source_page_start,
        source_page_end=candidate.source_page_end,
        text_sha256=text_sha256,
    )
    session.add(version)
    session.flush()
    candidate.normalized_text = normalized_text
    candidate.text_sha256 = text_sha256
    return version, "created"


def block_unclassified_current_law_changes(
    session: Session,
    *,
    source: SourceDocument,
    candidates: list[ExtractionCandidate],
) -> int:
    if source.is_legal_revision and source.legal_revision_effective_at:
        return 0
    blocked = 0
    for candidate in candidates:
        text = candidate_text_for_materialization(session, candidate)
        if not text:
            continue
        provision = session.exec(
            select(Provision).where(
                Provision.canonical_path == candidate.canonical_path
            )
        ).first()
        if not provision:
            continue
        current_version = current_version_for_provision(session, provision.id)
        if not current_version:
            continue
        candidate_text_sha256 = legal_text_sha256(text)
        if current_version.text_sha256 == candidate_text_sha256:
            continue
        ensure_review_issue(
            session,
            candidate=candidate,
            issue_type="changed_current_law_text",
            severity=ReviewIssueSeverity.BLOCKING,
            blocking=True,
            message=(
                "Candidate text differs from the current law. Mark the source as a "
                "legal revision and provide its effective date before materializing."
            ),
            evidence={
                "canonical_path": candidate.canonical_path,
                "current_version_id": str(current_version.id),
                "current_text_sha256": current_version.text_sha256,
                "candidate_text_sha256": candidate_text_sha256,
            },
        )
        candidate.status = ExtractionCandidateStatus.NEEDS_REVIEW
        candidate.blocking_issue_count = max(candidate.blocking_issue_count, 1)
        candidate.updated_at = get_datetime_utc()
        session.add(candidate)
        blocked += 1
    return blocked


def current_version_for_provision(
    session: Session, provision_id: uuid.UUID
) -> ProvisionVersion | None:
    return session.exec(
        select(ProvisionVersion)
        .where(
            ProvisionVersion.provision_id == provision_id,
            ProvisionVersion.legal_status == LegalStatus.CURRENT,
            col(ProvisionVersion.valid_until).is_(None),
        )
        .order_by(col(ProvisionVersion.revision_number).desc())
    ).first()


def next_version_number(session: Session, provision_id: uuid.UUID) -> int:
    latest = session.exec(
        select(ProvisionVersion)
        .where(ProvisionVersion.provision_id == provision_id)
        .order_by(col(ProvisionVersion.revision_number).desc())
    ).first()
    return (latest.revision_number if latest else 0) + 1


def version_valid_from(instrument: LegalInstrument, source: SourceDocument) -> date:
    return (
        instrument.effective_at
        or instrument.enacted_at
        or source.published_at
        or get_datetime_utc().date()
    )


def sync_release_entries(
    session: Session,
    *,
    release: CorpusRelease,
    run: IngestionRun,
    instrument: LegalInstrument,
    materialized_version_ids: set[uuid.UUID],
) -> list[CorpusReleaseEntry]:
    versions = (
        list(
            session.exec(
                select(ProvisionVersion)
                .where(col(ProvisionVersion.id).in_(materialized_version_ids))
                .order_by(col(ProvisionVersion.id))
            ).all()
        )
        if resolve_corpus_legal_status(run, instrument=instrument)
        == LegalStatus.HISTORICAL
        else current_versions_for_instrument(session, instrument.id)
    )
    run_ids_by_version = materialized_run_ids_by_version(
        session, [version.id for version in versions]
    )
    existing = {
        entry.provision_version_id: entry
        for entry in session.exec(
            select(CorpusReleaseEntry).where(
                CorpusReleaseEntry.release_id == release.id
            )
        ).all()
    }
    entries: list[CorpusReleaseEntry] = []
    for version in versions:
        ingestion_run_id = (
            run.id
            if version.id in materialized_version_ids
            else run_ids_by_version.get(version.id)
        )
        entry = existing.get(version.id)
        if not entry:
            entry = CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=version.source_document_id,
                ingestion_run_id=ingestion_run_id,
            )
        else:
            entry.source_document_id = version.source_document_id
            if ingestion_run_id:
                entry.ingestion_run_id = ingestion_run_id
        session.add(entry)
        entries.append(entry)
    session.flush()
    return entries


def current_versions_for_instrument(
    session: Session, instrument_id: uuid.UUID
) -> list[ProvisionVersion]:
    return list(
        session.exec(
            select(ProvisionVersion)
            .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
            .where(
                Provision.instrument_id == instrument_id,
                ProvisionVersion.legal_status == LegalStatus.CURRENT,
                col(ProvisionVersion.valid_until).is_(None),
            )
            .order_by(col(Provision.sort_key), col(Provision.canonical_path))
        ).all()
    )
