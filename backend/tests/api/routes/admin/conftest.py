import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion import LocalBlobStore, MultipartUpload, MultipartUploadPartUrl
from app.ingestion.pgvector_repository import (
    validate_index_build,
    write_embeddings,
    write_segments,
)
from app.ingestion.retrieval import build_retrieval_documents
from app.ingestion.runtime.queue import create_run_steps
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
    IngestionRunStatus,
    IngestionStage,
    InstrumentStatus,
    InstrumentType,
    ProvisionKind,
    SourceTier,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    IngestionRun,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    SourceDocument,
    SourceUpload,
)
from app.models import User
from tests.factories.pdf import sha256 as _sha256
from tests.factories.pdf import sha256_text as _sha256_text
from tests.utils.legal import register_fixture_citation_names


def _complete_pdf_upload(
    client: TestClient,
    headers: dict[str, str],
    db: Session,
    pdf: bytes,
) -> dict[str, object]:
    upload_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads",
        headers=headers,
        json=_source_upload_payload(pdf),
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert (
        client.put(
            upload["upload_url"],
            headers={**headers, "content-type": "application/pdf"},
            content=pdf,
        ).status_code
        == 204
    )
    stored_upload = db.get(SourceUpload, uuid.UUID(upload["id"]))
    assert stored_upload
    db.refresh(stored_upload)
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/source-uploads/{upload['id']}/complete",
        headers=headers,
        json={
            "idempotency_key": f"complete-{uuid.uuid4().hex}",
            "expected_version": stored_upload.lock_version,
            "actual_sha256": _sha256(pdf),
        },
    )
    assert complete_response.status_code == 200
    return complete_response.json()


def _source_upload_payload(
    content: bytes,
    *,
    idempotency_key: str | None = None,
    slug: str | None = None,
    mime_type: str = "application/pdf",
    expected_size: int | None = None,
) -> dict[str, object]:
    source_slug = slug or f"constitution-1999-{uuid.uuid4().hex}"
    return {
        "idempotency_key": idempotency_key or f"upload-{uuid.uuid4().hex}",
        "expected_size": expected_size or len(content),
        "expected_sha256": _sha256(content),
        "original_filename": "constitution.pdf",
        "mime_type": mime_type,
        "instrument_slug": source_slug,
        "instrument_title": "Constitution of the Federal Republic of Nigeria 1999",
        "instrument_short_title": "CFRN 1999",
        "instrument_year": 1999,
        "instrument_status": InstrumentStatus.ENACTED,
        "enacted_at": date(1999, 5, 29).isoformat(),
        "effective_at": date(1999, 5, 29).isoformat(),
        "source_title": f"{source_slug} official PDF",
        "authority": "Official Gazette",
        "source_url": f"https://example.test/{source_slug}.pdf",
        "source_tier": SourceTier.OFFICIAL,
        "published_at": date(1999, 5, 29).isoformat(),
        "retrieved_at": date.today().isoformat(),
    }


class _ManagedLocalBlobStore(LocalBlobStore):
    def __init__(self, root: object) -> None:
        super().__init__(root)
        self.presigned_put_calls: list[dict[str, object]] = []
        self.multipart_calls: list[dict[str, object]] = []

    def create_presigned_put_url(
        self,
        *,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
        expires_in_seconds: int,
    ) -> str:
        self.presigned_put_calls.append(
            {
                "key": key,
                "content_type": content_type,
                "metadata": metadata,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return f"https://r2.example.test/{key}?signed=put"

    def create_multipart_upload(
        self,
        *,
        key: str,
        content_type: str,
        part_count: int,
        metadata: dict[str, str] | None = None,
        expires_in_seconds: int,
    ) -> MultipartUpload:
        self.multipart_calls.append(
            {
                "key": key,
                "content_type": content_type,
                "part_count": part_count,
                "metadata": metadata,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return MultipartUpload(
            upload_id="managed-multipart-1",
            parts=tuple(
                MultipartUploadPartUrl(
                    part_number=part_number,
                    upload_url=f"https://r2.example.test/{key}?partNumber={part_number}",
                )
                for part_number in range(1, part_count + 1)
            ),
        )

    def complete_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[object],
    ) -> object:
        return self.head(key)

    def abort_multipart_upload(self, *, key: str, upload_id: str) -> None:
        return None


def _superuser(db: Session) -> User:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    return user


def _source_and_run(
    db: Session, *, created_by: uuid.UUID | None = None
) -> tuple[SourceDocument, IngestionRun]:
    instrument = LegalInstrument(
        slug=f"constitution-direct-{uuid.uuid4().hex}",
        title="Constitution of the Federal Republic of Nigeria 1999",
        short_title="CFRN 1999",
        instrument_type=InstrumentType.CONSTITUTION,
        jurisdiction="NG",
        year=1999,
        status=InstrumentStatus.ENACTED,
        enacted_at=date(1999, 5, 29),
        effective_at=date(1999, 5, 29),
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Official Gazette",
        title=f"Source {uuid.uuid4().hex}",
        source_url=f"https://example.test/source-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        sha256=_sha256(uuid.uuid4().bytes),
        storage_backend="local",
        storage_key=f"originals/sha256/{uuid.uuid4().hex}.pdf",
        original_filename="constitution.pdf",
        file_size=128,
        page_count=3,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
        source_tier=SourceTier.OFFICIAL,
        created_by=created_by,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    run = IngestionRun(
        source_document_id=source.id,
        created_by=created_by,
        status=IngestionRunStatus.WAITING_FOR_INPUT,
        current_stage=IngestionStage.AWAITING_PAGE_CONFIRMATION,
        pipeline_config={"instrument_parser": "constitution"},
        expected_page_count=source.page_count,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    create_run_steps(db, run)
    return source, run


def _retire_existing_production_release(db: Session) -> None:
    releases = db.exec(
        select(CorpusRelease).where(
            CorpusRelease.status == CorpusReleaseStatus.PRODUCTION
        )
    ).all()
    for release in releases:
        release.status = CorpusReleaseStatus.RETIRED
        release.lock_version += 1
        db.add(release)
    db.commit()


def _release_bundle(
    db: Session, *, uploader: User
) -> tuple[CorpusRelease, RetrievalIndexBuild]:
    source, run = _source_and_run(db, created_by=uploader.id)
    source.verification_status = VerificationStatus.VERIFIED
    db.add(source)
    db.commit()
    instrument = db.get(LegalInstrument, source.legal_instrument_id)
    assert instrument
    register_fixture_citation_names(instrument.slug)
    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"constitution.1999.section.37.{uuid.uuid4().hex}",
        sort_key="037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)
    text = "The privacy of citizens, their homes and correspondence is guaranteed."
    version = ProvisionVersion(
        provision_id=provision.id,
        text=text,
        normalized_text=text,
        valid_from=date(1999, 5, 29),
        source_document_id=source.id,
        source_page_start=2,
        source_page_end=2,
        text_sha256=_sha256_text(text),
    )
    release = CorpusRelease(
        version=f"test-release-{uuid.uuid4().hex}",
        status=CorpusReleaseStatus.BUILDING,
        source_manifest_hash=_sha256_text(str(uuid.uuid4())),
        parser_version="constitution-parser-v1",
    )
    benchmark_dataset_version = f"golden-{uuid.uuid4().hex}"
    benchmark_dataset = EvaluationDataset(
        version=benchmark_dataset_version,
        name="Nigerian Constitution retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        language="en",
        jurisdiction="NG",
        source_document_id=source.id,
        content_sha256=_sha256_text(benchmark_dataset_version),
    )
    profile = EmbeddingProfile(
        name=f"openai-small-{uuid.uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="text-embedding-3-small",
        model_revision="pinned-test-revision",
        vector_dimensions=1024,
        configuration={
            "chunking": "provision",
            "benchmark_dataset_version": benchmark_dataset_version,
        },
    )
    db.add_all([version, release, benchmark_dataset, profile])
    db.commit()
    db.refresh(version)
    db.refresh(release)
    db.refresh(benchmark_dataset)
    db.refresh(profile)
    db.add(
        EvaluationItem(
            dataset_id=benchmark_dataset.id,
            item_key="privacy-exact-reference",
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
            query_text="Which section protects privacy?",
            expected_canonical_paths=[provision.canonical_path],
        )
    )
    entry = CorpusReleaseEntry(
        release_id=release.id,
        provision_version_id=version.id,
        source_document_id=source.id,
        ingestion_run_id=run.id,
    )
    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        status=EmbeddingRunStatus.SUCCEEDED,
        benchmark_dataset_version=benchmark_dataset_version,
        recall_at_10=0.96,
        ndcg_at_10=0.94,
        selected_for_release=True,
    )
    db.add_all([entry, embedding_run])
    db.commit()
    db.refresh(embedding_run)
    documents = build_retrieval_documents(
        release_version=release.version,
        entries=[entry],
        versions_by_id={version.id: version},
        provisions_by_id={provision.id: provision},
        instruments_by_id={instrument.id: instrument},
    )
    segments = write_segments(
        db, release_id=release.id, documents=documents, index_kind="enacted"
    )
    embeddings = write_embeddings(
        db,
        release_id=release.id,
        embedding_run=embedding_run,
        profile=profile,
        segments=segments,
        vectors=[[1.0] + [0.0] * 1023 for _ in segments],
    )
    build = RetrievalIndexBuild(
        release_id=release.id,
        embedding_run_id=embedding_run.id,
        profile_id=profile.id,
        profile_hash=_sha256_text("profile-config-v1"),
        status=VectorIndexStatus.READY,
        expected_segment_count=len(documents),
        stored_segment_count=len(segments),
        stored_embedding_count=len(embeddings),
        vector_dimensions=1024,
        checksum=_sha256_text("vector-checksum"),
    )
    build.validation_report = validate_index_build(
        db, build=build, expected_segment_count=len(documents)
    )
    assert build.validation_report["is_valid"]
    db.add(build)
    db.commit()
    db.refresh(release)
    db.refresh(build)
    return release, build
