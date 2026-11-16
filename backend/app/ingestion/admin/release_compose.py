import json
import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.ingestion.admin.idempotency import (
    add_idempotency_record,
    idempotency_record_for_request,
    idempotency_request_hash,
)
from app.ingestion.admin.queries import check_expected_version, get_release
from app.ingestion.admin.release_gates import release_source_and_review_gates
from app.ingestion.composition import (
    act_review_gates,
    entry_snapshot,
    manifest_hash,
    member_snapshot,
    release_entries,
)
from app.ingestion.runtime.queue import (
    append_run_event,
    create_run_steps,
    enqueue_task,
)
from app.ingestion.storage import get_blob_store
from app.legal.enums import (
    CorpusReleaseStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    InstrumentType,
)
from app.legal.models import (
    AuditEvent,
    CorpusRelease,
    CorpusReleaseEntry,
    IngestionArtifact,
    IngestionRun,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.schemas import (
    CompositeReleaseCreate,
)
from app.models import User


def compose_corpus_release(
    session: Session, body: CompositeReleaseCreate, current_user: User
) -> CorpusRelease:
    scope = "corpus_release.compose"
    request_hash = idempotency_request_hash(body)
    record = idempotency_record_for_request(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if record and record.result_id:
        return get_release(session, record.result_id)
    requested = [
        (body.base_release_id, body.expected_base_version),
        *[(item.release_id, item.expected_version) for item in body.members],
    ]
    members: list[CorpusRelease] = []
    snapshots: list[dict[str, object]] = []
    union: dict[uuid.UUID, CorpusReleaseEntry] = {}
    versions_by_provision: dict[uuid.UUID, uuid.UUID] = {}
    for index, (release_id, expected_version) in enumerate(requested):
        member = session.exec(
            select(CorpusRelease)
            .where(CorpusRelease.id == release_id)
            .with_for_update()
        ).one_or_none()
        if member is None:
            raise HTTPException(
                status_code=404, detail="Member corpus release was not found"
            )
        if index == 0:
            # Concurrent identical requests serialize on the production base.
            record = idempotency_record_for_request(
                session,
                scope=scope,
                idempotency_key=body.idempotency_key,
                request_hash=request_hash,
            )
            if record and record.result_id:
                return get_release(session, record.result_id)
        check_expected_version(member.lock_version, expected_version)
        if (index == 0 and member.status != CorpusReleaseStatus.PRODUCTION) or (
            index > 0 and member.status != CorpusReleaseStatus.APPROVED
        ):
            raise HTTPException(
                status_code=409,
                detail="Composition requires the current production base and approved Act releases",
            )
        entries = release_entries(session, member.id)
        try:
            snapshot = member_snapshot(session, member)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        types = {item["type"] for item in snapshot["instruments"]}
        if (index == 0 and str(InstrumentType.CONSTITUTION) not in types) or (
            index > 0
            and (
                types != {str(InstrumentType.ACT)} or len(snapshot["instruments"]) != 1
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="The base must contain the Constitution; each added member must contain one Act",
            )
        if not member.source_manifest_hash:
            raise HTTPException(
                status_code=409,
                detail="Each member requires a retained source manifest hash",
            )
        gates = release_source_and_review_gates(session, entries, release=member)
        gates.extend(act_review_gates(session, entries))
        if gates:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Member source/review gates must pass before composition",
                    "release_id": str(member.id),
                    "gates": sorted(set(gates)),
                },
            )
        for entry in entries:
            version = session.get(ProvisionVersion, entry.provision_version_id)
            assert version is not None  # Checked by member_snapshot.
            previous = versions_by_provision.setdefault(
                version.provision_id, version.id
            )
            if previous != version.id:
                raise HTTPException(
                    status_code=409,
                    detail="Members contain conflicting versions of the same provision",
                )
            existing = union.setdefault(version.id, entry)
            if (existing.source_document_id, existing.ingestion_run_id) != (
                entry.source_document_id,
                entry.ingestion_run_id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Members disagree about an entry's review provenance",
                )
        members.append(member)
        snapshots.append(snapshot)
    if session.exec(
        select(CorpusRelease).where(CorpusRelease.version == body.version)
    ).first():
        raise HTTPException(status_code=409, detail="Release version already exists")
    release = CorpusRelease(version=body.version, parser_version="composite-v1")
    run = IngestionRun(
        created_by=current_user.id,
        status=IngestionRunStatus.QUEUED,
        current_stage=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
        pipeline_config={
            "composition_release_id": str(release.id),
            "auto_start_embedding": False,
        },
    )
    snapshot_entries = entry_snapshot(session, list(union.values()))
    release.source_manifest_hash = manifest_hash(snapshot_entries)
    composition = {
        "version": 1,
        "base_release_id": str(body.base_release_id),
        "run_id": str(run.id),
        "members": snapshots,
    }
    release.validation_report = {
        "composition": composition,
        "entry_count": len(union),
        "ingestion_run_ids": sorted(
            {
                str(entry.ingestion_run_id)
                for entry in union.values()
                if entry.ingestion_run_id
            }
        ),
        "source_document_ids": sorted(
            {str(entry.source_document_id) for entry in union.values()}
        ),
        "unresolved_gates": [
            "retrieval_documents_pending",
            "selected_embedding_run_missing",
            "ready_retrieval_index_build_missing",
        ],
    }
    session.add_all([release, run])
    session.flush()
    for entry in union.values():
        session.add(
            CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=entry.provision_version_id,
                source_document_id=entry.source_document_id,
                ingestion_run_id=entry.ingestion_run_id,
            )
        )
    steps = create_run_steps(session, run, commit=False)
    for step in steps:
        if step.stage == IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS:
            break
        step.status = IngestionStepStatus.SKIPPED
        step.metrics = {
            "reason": "Reusing approved member releases; original ingestion provenance retained"
        }
        session.add(step)
    enqueue_task(
        session,
        run=run,
        step=step,
        task_type=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS.value,
        idempotency_key=f"{run.id}:building_retrieval_documents",
        payload={"release_id": str(release.id)},
        commit=False,
    )
    manifest = {
        "manifest_version": 2,
        "release_id": str(release.id),
        "release_version": release.version,
        "composition": composition,
        "entries": snapshot_entries,
        "source_document_ids": release.validation_report["source_document_ids"],
        "ingestion_run_ids": release.validation_report["ingestion_run_ids"],
        "source_documents": [
            {
                "id": str(source.id),
                "source_document_id": str(source.id),
                "title": source.title,
                "authority": source.authority,
                "source_url": source.source_url,
                "sha256": source.sha256,
                "page_count": source.page_count,
                "verification_status": str(source.verification_status),
            }
            for source in session.exec(
                select(SourceDocument)
                .where(
                    col(SourceDocument.id).in_(
                        {entry.source_document_id for entry in union.values()}
                    )
                )
                .order_by(col(SourceDocument.id))
            ).all()
        ],
    }
    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RELEASE_MANIFEST.value,
        filename=f"release-{release.version}.json",
        content=json.dumps(manifest, sort_keys=True).encode(),
        content_type="application/json",
    )
    session.add(
        IngestionArtifact(
            run_id=run.id,
            artifact_type=IngestionArtifactType.RELEASE_MANIFEST,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            artifact_metadata={
                "release_id": str(release.id),
                "source_manifest_hash": release.source_manifest_hash,
            },
        )
    )
    session.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="corpus_release.compose",
            entity_type="corpus_release",
            entity_id=release.id,
            payload={
                "member_release_ids": [str(member.id) for member in members],
                "source_manifest_hash": release.source_manifest_hash,
            },
        )
    )
    append_run_event(
        session,
        run,
        event_type="release_composed",
        message="Composite retrieval build queued from approved member releases",
        payload={"release_id": str(release.id)},
        commit=False,
    )
    add_idempotency_record(
        session,
        scope=scope,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        result_type="corpus_release",
        result_id=release.id,
        created_by=current_user.id,
    )
    session.commit()
    session.refresh(release)
    return release
