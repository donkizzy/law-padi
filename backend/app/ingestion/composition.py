"""Frozen membership and provenance checks for composite corpus releases."""

import hashlib
import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, col, select

from app.legal.enums import CorpusReleaseStatus, InstrumentType, LegalStatus
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
from app.legal.parser import legal_text_sha256


def manifest_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def release_entries(
    session: Session, release_id: uuid.UUID
) -> list[CorpusReleaseEntry]:
    return list(
        session.exec(
            select(CorpusReleaseEntry).where(
                CorpusReleaseEntry.release_id == release_id
            )
        ).all()
    )


def entry_snapshot(
    session: Session, entries: Sequence[CorpusReleaseEntry]
) -> list[dict[str, Any]]:
    versions = {
        version.id: version
        for version in session.exec(
            select(ProvisionVersion).where(
                col(ProvisionVersion.id).in_(
                    {entry.provision_version_id for entry in entries}
                )
            )
        ).all()
    }
    provisions = {
        provision.id: provision
        for provision in session.exec(
            select(Provision).where(
                col(Provision.id).in_(
                    {version.provision_id for version in versions.values()}
                )
            )
        ).all()
    }
    sources = {
        source.id: source
        for source in session.exec(
            select(SourceDocument).where(
                col(SourceDocument.id).in_(
                    {
                        entry.source_document_id
                        for entry in entries
                        if entry.source_document_id
                    }
                )
            )
        ).all()
    }
    rows: list[dict[str, Any]] = []
    for entry in entries:
        version = versions.get(entry.provision_version_id)
        provision = provisions.get(version.provision_id) if version else None
        source = (
            sources.get(entry.source_document_id) if entry.source_document_id else None
        )
        if not version or not provision or not source:
            raise ValueError(
                "Every member entry requires a canonical version, provision and source"
            )
        if (
            version.source_document_id != source.id
            or source.legal_instrument_id != provision.instrument_id
        ):
            raise ValueError(
                "Member source identity differs from its canonical provision"
            )
        if legal_text_sha256(version.text) != version.text_sha256:
            raise ValueError("Member canonical text differs from its recorded hash")
        rows.append(
            {
                "provision_version_id": str(version.id),
                "provision_id": str(provision.id),
                "instrument_id": str(provision.instrument_id),
                "canonical_path": provision.canonical_path,
                "text_sha256": version.text_sha256,
                "legal_status": str(version.legal_status),
                "source_document_id": str(source.id),
                "source_sha256": source.sha256,
                "source_page_start": version.source_page_start,
                "source_page_end": version.source_page_end,
                "ingestion_run_id": str(entry.ingestion_run_id)
                if entry.ingestion_run_id
                else None,
            }
        )
    return sorted(rows, key=lambda row: row["provision_version_id"])


def member_snapshot(session: Session, release: CorpusRelease) -> dict[str, Any]:
    entries = entry_snapshot(session, release_entries(session, release.id))
    if not entries:
        raise ValueError("Member release has no canonical entries")
    instruments = [
        session.get(LegalInstrument, uuid.UUID(key))
        for key in sorted({row["instrument_id"] for row in entries})
    ]
    if any(instrument is None for instrument in instruments):
        raise ValueError("Member instrument is missing")
    return {
        "release_id": str(release.id),
        "version": release.version,
        "source_manifest_hash": release.source_manifest_hash,
        "entry_snapshot_hash": manifest_hash(entries),
        "entry_count": len(entries),
        "instruments": [
            {"id": str(item.id), "slug": item.slug, "type": str(item.instrument_type)}
            for item in instruments
            if item
        ],
        "source_hashes": {
            row["source_document_id"]: row["source_sha256"] for row in entries
        },
        "source_edition_review": (release.validation_report or {}).get(
            "source_edition_review"
        ),
        "parser_version": release.parser_version,
    }


def act_review_gates(
    session: Session, entries: Sequence[CorpusReleaseEntry]
) -> list[str]:
    """Act membership requires materialised reviewed text, including its ancestry."""
    gates: set[str] = set()
    run_ids = {entry.ingestion_run_id for entry in entries if entry.ingestion_run_id}
    candidates = (
        session.exec(
            select(ExtractionCandidate).where(
                col(ExtractionCandidate.run_id).in_(run_ids)
            )
        ).all()
        if run_ids
        else []
    )
    reviewed_versions = {
        (
            row.run_id,
            row.materialized_version_id,
            row.source_document_id,
            row.materialized_provision_id,
        )
        for row in candidates
        if row.status in {"approved", "auto_approved", "materialized"}
    }
    canonical = entry_snapshot(session, entries)
    instruments = {
        str(item.id): item
        for item in session.exec(
            select(LegalInstrument).where(
                col(LegalInstrument.id).in_(
                    {uuid.UUID(row["instrument_id"]) for row in canonical}
                )
            )
        ).all()
    }
    runs = (
        {
            str(item.id): item
            for item in session.exec(
                select(IngestionRun).where(col(IngestionRun.id).in_(run_ids))
            ).all()
        }
        if run_ids
        else {}
    )
    for row in canonical:
        instrument = instruments.get(row["instrument_id"])
        if instrument and instrument.instrument_type == InstrumentType.ACT:
            if row["legal_status"] != str(LegalStatus.HISTORICAL):
                gates.add("composite_act_edition_not_historical")
            origin = runs.get(row["ingestion_run_id"])
            if (
                not origin
                or str(origin.source_document_id) != row["source_document_id"]
                or origin.status
                in {"cancelled", "failed", "waiting_for_input", "waiting_for_review"}
            ):
                gates.add("composite_act_ingestion_not_materialized")
            if (
                uuid.UUID(row["ingestion_run_id"]) if row["ingestion_run_id"] else None,
                uuid.UUID(row["provision_version_id"]),
                uuid.UUID(row["source_document_id"]),
                uuid.UUID(row["provision_id"]),
            ) not in reviewed_versions:
                gates.add("composite_act_review_provenance_missing")
    return sorted(gates)


def composition_gates(
    session: Session, release: CorpusRelease, entries: Sequence[CorpusReleaseEntry]
) -> list[str]:
    composition = (release.validation_report or {}).get("composition")
    if composition is None:
        return []
    if not isinstance(composition, dict) or not isinstance(
        composition.get("members"), list
    ):
        return ["composite_membership_invalid"]
    gates: set[str] = set()
    expected: dict[str, dict[str, Any]] = {}
    for frozen in composition["members"]:
        try:
            member = session.get(CorpusRelease, uuid.UUID(frozen["release_id"]))
            if not member or member.status not in {
                CorpusReleaseStatus.APPROVED,
                CorpusReleaseStatus.PRODUCTION,
                CorpusReleaseStatus.RETIRED,
            }:
                gates.add("composite_member_not_approved")
                continue
            current = member_snapshot(session, member)
            if current != frozen:
                gates.add("composite_member_manifest_changed")
            for row in entry_snapshot(session, release_entries(session, member.id)):
                previous = expected.setdefault(row["provision_version_id"], row)
                if previous != row:
                    gates.add("composite_member_provenance_conflict")
        except ValueError, TypeError, KeyError:
            gates.add("composite_membership_invalid")
    try:
        actual = entry_snapshot(session, entries)
        if actual != sorted(
            expected.values(), key=lambda row: row["provision_version_id"]
        ):
            gates.add("composite_entry_union_changed")
        if manifest_hash(actual) != release.source_manifest_hash:
            gates.add("composite_manifest_hash_mismatch")
    except ValueError:
        gates.add("composite_canonical_provenance_invalid")
    if release.status not in {
        CorpusReleaseStatus.PRODUCTION,
        CorpusReleaseStatus.RETIRED,
    }:
        try:
            base = session.get(CorpusRelease, uuid.UUID(composition["base_release_id"]))
        except ValueError, TypeError, KeyError:
            return sorted(gates | {"composite_membership_invalid"})
        if not base or base.status != CorpusReleaseStatus.PRODUCTION:
            gates.add("composite_base_no_longer_production")
    try:
        gates.update(act_review_gates(session, entries))
    except ValueError:
        gates.add("composite_canonical_provenance_invalid")
    return sorted(gates)
