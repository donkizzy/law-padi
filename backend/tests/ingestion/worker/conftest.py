import json
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlmodel import Session, delete, select

from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.runtime.queue import create_run_steps, enqueue_task
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EvaluationDatasetKind,
    EvaluationItemKind,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    SourceTier,
    VerificationStatus,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionRun,
    IngestionTask,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    SourceDocument,
    SourcePage,
)
from app.legal.parser import PARSER_VERSION, legal_text_sha256, normalize_legal_text
from tests.factories.pdf import pdf_with_pages as _pdf_with_pages


@pytest.fixture(autouse=True)
def isolate_ingestion_tasks(db: Session) -> Generator[None]:
    db.rollback()
    db.exec(delete(IngestionTask))
    db.commit()
    yield
    db.rollback()
    db.exec(delete(IngestionTask))
    db.commit()


def _stored_source_and_run(
    db: Session,
    *,
    tmp_path: Path,
    pdf: bytes,
    expected_sha256: str | None = None,
    max_attempts: int = 3,
    instrument: LegalInstrument | None = None,
) -> tuple[SourceDocument, IngestionRun]:
    store = LocalBlobStore(tmp_path)
    quarantine = store.put_quarantine(
        upload_id=f"worker-{uuid.uuid4()}",
        filename="constitution.pdf",
        content=pdf,
        content_type="application/pdf",
    )
    original = store.promote_quarantine_to_original(
        quarantine_key=quarantine.key,
        expected_sha256=quarantine.sha256,
        content_type="application/pdf",
        extension=".pdf",
    )
    if instrument is None:
        instrument = LegalInstrument(
            slug=f"constitution-worker-{uuid.uuid4().hex}",
            title="Constitution of the Federal Republic of Nigeria 1999",
            instrument_type=InstrumentType.CONSTITUTION,
            jurisdiction="NG",
            year=1999,
            status=InstrumentStatus.ENACTED,
        )
        db.add(instrument)
        db.commit()
        db.refresh(instrument)
    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Official Gazette",
        title="Stored worker source",
        source_url="https://example.test/constitution.pdf",
        mime_type="application/pdf",
        sha256=expected_sha256 or original.sha256,
        storage_backend="local",
        storage_key=original.key,
        original_filename="constitution.pdf",
        file_size=original.size_bytes,
        page_count=None,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
        source_tier=SourceTier.OFFICIAL,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    run = IngestionRun(
        source_document_id=source.id,
        status=IngestionRunStatus.QUEUED,
        current_stage=IngestionStage.VERIFYING_UPLOAD,
        pipeline_config={"instrument_parser": "constitution"},
        expected_page_count=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    steps = create_run_steps(db, run)
    verify_step = next(
        step for step in steps if step.stage == IngestionStage.VERIFYING_UPLOAD
    )
    enqueue_task(
        db,
        run=run,
        step=verify_step,
        task_type=IngestionStage.VERIFYING_UPLOAD.value,
        idempotency_key=f"{run.id}:verify",
        payload={"source_document_id": str(source.id)},
        priority=10,
    )
    task = db.exec(select(IngestionTask).where(IngestionTask.run_id == run.id)).one()
    task.max_attempts = max_attempts
    db.add(task)
    db.commit()
    return source, run


def _release_with_retrieval_documents(
    db: Session, *, tmp_path: Path, create_benchmark_dataset: bool = True
) -> tuple[SourceDocument, IngestionRun, CorpusRelease, EmbeddingProfile]:
    pdf = _pdf_with_pages([f"37. Right to privacy {uuid.uuid4().hex}"])
    source, run = _stored_source_and_run(db, tmp_path=tmp_path, pdf=pdf)
    _clear_run_tasks(db, run)
    source.verification_status = VerificationStatus.VERIFIED
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
    text = "Right to private and family life"
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=normalize_legal_text(text),
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        source_page_start=1,
        source_page_end=1,
        text_sha256=legal_text_sha256(text),
    )
    release = CorpusRelease(
        version=f"draft-embed-{uuid.uuid4().hex}",
        status=CorpusReleaseStatus.BUILDING,
        source_manifest_hash=legal_text_sha256(text),
        parser_version=PARSER_VERSION,
    )
    benchmark_dataset_version = f"golden-{uuid.uuid4().hex}"
    for existing_profile in db.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active == True)  # noqa: E712
    ).all():
        existing_profile.is_active = False
        db.add(existing_profile)
    profile = EmbeddingProfile(
        name=f"fake-profile-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="fake-large",
        model_revision="pinned-test",
        vector_dimensions=1024,
        configuration={
            "benchmark_dataset_version": benchmark_dataset_version,
            "estimated_cost_usd": 0.01,
            "p95_latency_ms": 120,
        },
    )
    db.add_all([source, version, release, profile])
    db.commit()
    db.refresh(version)
    db.refresh(release)
    db.refresh(profile)
    entry = CorpusReleaseEntry(
        release_id=release.id,
        provision_version_id=version.id,
        source_document_id=source.id,
        ingestion_run_id=run.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    if create_benchmark_dataset:
        _create_retrieval_benchmark_dataset(
            db,
            version=benchmark_dataset_version,
            canonical_path=provision.canonical_path,
        )
    retrieval_payload = {
        "release_id": str(release.id),
        "release_version": release.version,
        "document_count": 1,
        "documents": [
            {
                "id": "retrieval-doc-1",
                "segment_id": f"{provision.canonical_path}:v1:s1",
                "citation": "Section 37",
                "retrieval_text": "Section 37\nRight to private and family life",
                "payload": {
                    "release_version": release.version,
                    "corpus_release_entry_id": str(entry.id),
                    "canonical_path": provision.canonical_path,
                    "kind": ProvisionKind.SECTION.value,
                    "provision_id": str(provision.id),
                    "provision_version_id": str(version.id),
                    "source_document_id": str(source.id),
                    "source_page_start": 1,
                    "source_page_end": 1,
                    "legal_status": LegalStatus.CURRENT.value,
                    "segment_index": 1,
                    "segment_count": 1,
                    "text_sha256": version.text_sha256,
                    "retrieval_text_sha256": legal_text_sha256(
                        "Section 37\nRight to private and family life"
                    ),
                },
            }
        ],
    }
    blob = LocalBlobStore(tmp_path).put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS.value,
        filename="retrieval-documents.json",
        content=json.dumps(retrieval_payload, sort_keys=True).encode(),
        content_type="application/json",
        metadata={"release_id": str(release.id)},
    )
    db.add(
        IngestionArtifact(
            run_id=run.id,
            artifact_type=IngestionArtifactType.RETRIEVAL_DOCUMENTS,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            artifact_metadata={"release_id": str(release.id), "document_count": 1},
        )
    )
    db.commit()
    db.refresh(run)
    return source, run, release, profile


def _create_legal_grade_dataset(
    db: Session,
    *,
    version: str,
    canonical_path: str,
    section_number: str,
    text: str,
    source_page_start: int,
    source_page_end: int,
    source_spans: list[dict[str, object]],
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        version=version,
        name="Nigerian Constitution legal-grade gold provisions",
        dataset_kind=EvaluationDatasetKind.LEGAL_GRADE_EXTRACTION,
        language="en",
        jurisdiction="NG",
        content_sha256=legal_text_sha256(text),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key=section_number,
            item_kind=EvaluationItemKind.GOLD_PROVISION,
            canonical_path=canonical_path,
            provision_kind=ProvisionKind.SECTION,
            section_number=section_number,
            expected_text=text,
            source_page_start=source_page_start,
            source_page_end=source_page_end,
            source_spans=source_spans,
        )
    )
    db.commit()
    return dataset


def _create_retrieval_benchmark_dataset(
    db: Session,
    *,
    version: str,
    canonical_path: str,
    instrument_slug: str | None = None,
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        version=version,
        name="Nigerian Constitution retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        language="en",
        jurisdiction="NG",
        instrument_slug=instrument_slug,
        content_sha256=legal_text_sha256(version + canonical_path),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        EvaluationItem(
            dataset_id=dataset.id,
            item_key="privacy-exact-reference",
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            query_text="Which section protects privacy?",
            expected_canonical_paths=[canonical_path],
        )
    )
    db.commit()
    return dataset


def _approved_candidate(
    db: Session,
    *,
    run: IngestionRun,
    source: SourceDocument,
    text: str,
    number: str = "37",
    canonical_path: str | None = None,
    heading: str = "Right to private and family life",
    sort_key: str = "037",
) -> ExtractionCandidate:
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number=number,
        heading=heading,
        canonical_path=canonical_path or f"{instrument.slug}.section37",
        sort_key=sort_key,
        raw_text=text,
        normalized_text=normalize_legal_text(text),
        text_sha256=legal_text_sha256(text),
        source_page_start=1,
        source_page_end=1,
        source_spans=[
            {"page": 1, "bbox": {"x0": 36.0, "y0": 440.0, "x1": 220.0, "y1": 460.0}}
        ],
        parser_confidence=0.96,
        extractor_confidence=0.96,
        status=ExtractionCandidateStatus.APPROVED,
        blocking_issue_count=0,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def _store_raw_extraction(
    db: Session,
    *,
    tmp_path: Path,
    run: IngestionRun,
    source: SourceDocument,
    page_number: int,
    text: str,
    spans: list[dict[str, object]] | None = None,
    quality_flags: dict[str, object] | None = None,
) -> None:
    page = SourcePage(
        run_id=run.id,
        source_document_id=source.id,
        page_number=page_number,
        role=PageRole.LEGAL_BODY,
        inclusion_status=PageInclusionStatus.INCLUDED,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    span_payload = spans
    if span_payload is None:
        span_payload = [
            {
                "text": line,
                "bbox": {
                    "x0": 36.0,
                    "y0": 450.0 - (index * 14),
                    "x1": 240.0,
                    "y1": 462.0 - (index * 14),
                },
                "reading_order": index + 1,
            }
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]
    payload = {
        "page_number": page_number,
        "method": "native_pdf",
        "provider_version": "pypdf-native-layout-v1",
        "confidence": 0.96,
        "text": text,
        "spans": span_payload,
        "quality_flags": quality_flags
        or {"span_count": len(span_payload), "needs_ocr": False},
    }
    store = LocalBlobStore(tmp_path)
    blob = store.put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.RAW_EXTRACTION.value,
        filename=f"page-{page_number:04d}.json",
        content=json.dumps(payload, sort_keys=True).encode(),
        content_type="application/json",
        metadata={
            "source_document_id": str(source.id),
            "page_number": str(page_number),
        },
    )
    db.add(
        IngestionArtifact(
            run_id=run.id,
            source_page_id=page.id,
            artifact_type=IngestionArtifactType.RAW_EXTRACTION,
            storage_key=blob.key,
            sha256=blob.sha256,
            mime_type=blob.content_type,
            artifact_metadata={"page_number": page_number},
        )
    )
    db.commit()


def _clear_run_tasks(db: Session, run: IngestionRun) -> None:
    db.exec(delete(IngestionTask).where(IngestionTask.run_id == run.id))
    db.commit()


def _instrument_slug(db: Session, source: SourceDocument) -> str:
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    return instrument.slug
