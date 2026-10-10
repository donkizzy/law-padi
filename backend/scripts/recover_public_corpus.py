"""Recover the published source edition from immutable ingestion artifacts.

This is intentionally narrow: it restores public canonical text and retrieval
records, not users, review decisions, or ingestion workflow history. It refuses
to merge into a database that already contains a legal corpus.
"""

import argparse
import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.ingestion.pgvector_repository import (
    aggregate_checksum,
    embedding_sha256,
    validate_index_build,
    validate_vector,
)
from app.ingestion.retrieval import deterministic_segment_id
from app.legal.enums import (
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
    SourceTier,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256, normalize_legal_text


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _batch_key(offset: int, inputs: list[str], config: dict[str, Any]) -> str:
    value = {
        "profile_id": "36bfcf19-ca90-4e7f-8130-d635d179c2a1",
        "model_name": "BAAI/bge-m3",
        "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "provider": "huggingface_tei",
        "vector_dimensions": 1024,
        "configuration": config,
        "kind": "documents",
        "offset": offset,
        "inputs": inputs,
    }
    return _hash(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _prepared(
    args: argparse.Namespace,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[list[float]],
    dict[str, Any],
    dict[str, Any],
]:
    manifest = json.loads(args.manifest.read_text())
    document_payload = json.loads(args.documents.read_text())
    evidence = json.loads(args.evidence.read_text())
    documents = document_payload["documents"]
    if not (
        manifest["release_id"]
        == document_payload["release_id"]
        == evidence["release_id"]
        and manifest["release_version"]
        == document_payload["release_version"]
        == evidence["release_version"]
        and len(manifest["entries"]) == 1811
        and len(documents) == 1829
    ):
        raise ValueError(
            "The recovery artifacts do not identify the same verified release"
        )
    source = manifest["source_documents"][0]
    if source["sha256"] != evidence["source_sha256"]:
        raise ValueError("Source document hash disagrees with the review evidence")
    by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        payload = document["payload"]
        if payload["release_version"] != manifest["release_version"]:
            raise ValueError("Retrieval document belongs to another release")
        if (
            _hash(document["authoritative_text"].encode())
            != payload["authoritative_text_sha256"]
        ):
            raise ValueError("Retrieval document authoritative text hash mismatch")
        if (
            _hash(document["retrieval_text"].encode())
            != payload["retrieval_text_sha256"]
        ):
            raise ValueError("Retrieval document text hash mismatch")
        by_version[payload["provision_version_id"]].append(document)
    for entry in manifest["entries"]:
        rows = sorted(
            by_version.pop(entry["provision_version_id"]),
            key=lambda row: row["payload"]["segment_index"],
        )
        if not rows or any(
            row["payload"]["canonical_path"] != entry["canonical_path"] for row in rows
        ):
            raise ValueError("Manifest identity does not match retrieval documents")
        text = " ".join(row["authoritative_text"] for row in rows)
        if legal_text_sha256(text) != entry["text_sha256"]:
            raise ValueError("Manifest legal text hash mismatch")
    if by_version:
        raise ValueError("Retrieval documents contain extra version identities")

    endpoint = settings.HUGGINGFACE_TEI_ENDPOINT_URL
    if not endpoint:
        raise ValueError(
            "HUGGINGFACE_TEI_ENDPOINT_URL is required to identify saved batches"
        )
    config = {
        "endpoint_url": endpoint.replace(
            "/pipeline/sentence-similarity", "/pipeline/feature-extraction"
        ),
        "batch_size": 16,
        "benchmark_dataset_version": "constitution-source-edition-retrieval-2026-10-05-v1",
        "provider_revision_pinned": False,
    }
    vectors: list[list[float]] = []
    for offset in range(0, len(documents), 16):
        inputs = [row["retrieval_text"] for row in documents[offset : offset + 16]]
        candidates = [
            path
            for path in args.embeddings.glob(
                f"batch-{_batch_key(offset, inputs, config)}-*.json"
            )
            if not path.name.endswith(".metadata.json")
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Cannot identify saved embedding batch at offset {offset}"
            )
        raw = candidates[0].read_bytes()
        if _hash(raw) != candidates[0].stem.rsplit("-", 1)[-1]:
            raise ValueError("Saved embedding batch checksum mismatch")
        batch = json.loads(raw)
        if len(batch["vectors"]) != len(inputs):
            raise ValueError("Saved embedding batch size mismatch")
        vectors.extend(validate_vector(vector) for vector in batch["vectors"])
    expected = evidence["index_validation"]
    if (
        aggregate_checksum(
            [row["payload"]["retrieval_text_sha256"] for row in documents]
        )
        != expected["segment_checksum"]
    ):
        raise ValueError("Segment aggregate checksum differs from the published record")
    if (
        aggregate_checksum([embedding_sha256(vector) for vector in vectors])
        != expected["embedding_checksum"]
    ):
        raise ValueError(
            "Embedding aggregate checksum differs from the published record"
        )
    return manifest, documents, vectors, evidence, config


def _restore(
    manifest: dict[str, Any],
    documents: list[dict[str, Any]],
    vectors: list[list[float]],
    evidence: dict[str, Any],
    config: dict[str, Any],
) -> None:
    release_id = uuid.UUID(manifest["release_id"])
    profile_id = uuid.UUID(
        evidence["release_validation_report"]["embedding_profile_id"]
    )
    embedding_run_id = uuid.UUID(evidence["embedding_run_id"])
    source_data = manifest["source_documents"][0]
    source_id = uuid.UUID(source_data["source_document_id"])
    instrument_id = uuid.uuid5(
        uuid.NAMESPACE_URL, "law-padi:constitution-1999:recovery"
    )
    by_path: dict[str, dict[str, Any]] = {}
    first_position: dict[str, int] = {}
    by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for position, row in enumerate(documents):
        path = row["payload"]["canonical_path"]
        by_path.setdefault(path, row)
        by_version[row["payload"]["provision_version_id"]].append(row)
        parts = path.split(".")
        for depth in range(2, len(parts) + 1):
            ancestor = ".".join(parts[:depth])
            first_position.setdefault(ancestor, position)
    all_paths = sorted(
        first_position, key=lambda path: (path.count("."), first_position[path], path)
    )
    path_id: dict[str, uuid.UUID] = {}
    for path in all_paths:
        doc_row = by_path.get(path)
        path_id[path] = (
            uuid.UUID(doc_row["payload"]["provision_id"])
            if doc_row
            else uuid.uuid5(uuid.NAMESPACE_URL, f"law-padi:provision:{path}")
        )

    with Session(engine) as session:
        if (
            session.exec(select(CorpusRelease.id)).first()
            or session.exec(select(Provision.id)).first()
        ):
            raise RuntimeError(
                "Refusing to merge recovery data into an existing legal corpus"
            )
        try:
            session.add(
                LegalInstrument(
                    id=instrument_id,
                    slug="constitution-1999",
                    title="Constitution of the Federal Republic of Nigeria 1999",
                    short_title="1999 Constitution",
                    instrument_type=InstrumentType.CONSTITUTION,
                    jurisdiction="NG",
                    year=1999,
                    status=InstrumentStatus.ENACTED,
                    enacted_at=date(1999, 5, 29),
                    effective_at=date(1999, 5, 29),
                )
            )
            session.flush()
            session.add(
                SourceDocument(
                    id=source_id,
                    legal_instrument_id=instrument_id,
                    authority=source_data["authority"],
                    title=source_data["title"],
                    source_url=source_data["source_url"],
                    mime_type="application/pdf",
                    sha256=source_data["sha256"],
                    storage_backend="local",
                    storage_key=source_data["storage_key"],
                    original_filename="1999 CONSTITUTION OF THE FRN.pdf",
                    file_size=895394,
                    published_at=date.fromisoformat(source_data["published_at"]),
                    retrieved_at=datetime.fromisoformat(source_data["retrieved_at"]),
                    source_tier=SourceTier.OFFICIAL,
                    verification_status=VerificationStatus.VERIFIED,
                )
            )
            report = dict(evidence["release_validation_report"])
            report["recovery"] = {
                "method": "verified_release_manifest_retrieval_documents_embedding_checkpoints",
                "limits": "Review and ingestion history are not restored; multi-segment whitespace may differ.",
            }
            session.add(
                CorpusRelease(
                    id=release_id,
                    version=manifest["release_version"],
                    status=CorpusReleaseStatus.BUILDING,
                    source_manifest_hash=evidence["source_manifest_hash"],
                    embedding_model="BAAI/bge-m3",
                    embedding_model_version="5617a9f61b028005a4858fdac845db406aefb181",
                    validation_report=report,
                )
            )
            session.flush()
            provisions: list[Provision] = []
            for path in all_paths:
                doc_row = by_path.get(path)
                part = path.rsplit(".", 1)[-1]
                if doc_row:
                    kind = ProvisionKind(doc_row["payload"]["kind"])
                    number = doc_row["payload"]["number"]
                    heading = doc_row["heading"]
                else:
                    kind = (
                        ProvisionKind.CHAPTER
                        if part.startswith("chapter")
                        else ProvisionKind.PART
                        if part.startswith("part")
                        else ProvisionKind.SCHEDULE
                    )
                    number = part.removeprefix(str(kind))
                    heading = None
                parent = path.rsplit(".", 1)[0]
                provisions.append(
                    Provision(
                        id=path_id[path],
                        instrument_id=instrument_id,
                        parent_id=path_id.get(parent),
                        kind=kind,
                        number=number,
                        heading=heading,
                        canonical_path=path,
                        sort_key=f"{first_position[path]:06d}",
                    )
                )
            session.add_all(provisions)
            session.flush()
            versions: list[ProvisionVersion] = []
            entries: list[CorpusReleaseEntry] = []
            entry_id_by_version = {
                row["payload"]["provision_version_id"]: uuid.UUID(
                    row["payload"]["corpus_release_entry_id"]
                )
                for row in documents
            }
            for entry in manifest["entries"]:
                version_id = entry["provision_version_id"]
                rows = sorted(
                    by_version[version_id],
                    key=lambda row: row["payload"]["segment_index"],
                )
                content = " ".join(row["authoritative_text"] for row in rows)
                versions.append(
                    ProvisionVersion(
                        id=uuid.UUID(version_id),
                        provision_id=uuid.UUID(entry["provision_id"]),
                        text=content,
                        normalized_text=normalize_legal_text(content),
                        valid_from=date(1999, 5, 29),
                        legal_status=LegalStatus.HISTORICAL,
                        revision_number=1,
                        source_document_id=source_id,
                        source_page_start=entry["source_page_start"],
                        source_page_end=entry["source_page_end"],
                        text_sha256=entry["text_sha256"],
                    )
                )
                entries.append(
                    CorpusReleaseEntry(
                        id=entry_id_by_version[version_id],
                        release_id=release_id,
                        provision_version_id=uuid.UUID(version_id),
                        source_document_id=source_id,
                    )
                )
            session.add_all(versions)
            session.flush()
            session.add_all(entries)
            session.flush()
            profile = EmbeddingProfile(
                id=profile_id,
                name="bge-m3-constitution-source-edition-v1",
                provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
                model_name="BAAI/bge-m3",
                model_revision="5617a9f61b028005a4858fdac845db406aefb181",
                vector_dimensions=1024,
                configuration=config,
            )
            session.add(profile)
            session.add(
                EmbeddingRun(
                    id=embedding_run_id,
                    release_id=release_id,
                    profile_id=profile_id,
                    status=EmbeddingRunStatus.SUCCEEDED,
                    benchmark_dataset_version=config["benchmark_dataset_version"],
                    recall_at_10=evidence["recall_at_10"],
                    ndcg_at_10=evidence["ndcg_at_10"],
                    selected_for_release=True,
                )
            )
            session.flush()
            segments: list[RetrievalSegment] = []
            embeddings: list[RetrievalEmbedding] = []
            for row, vector in zip(documents, vectors, strict=True):
                payload = row["payload"]
                version_id = uuid.UUID(payload["provision_version_id"])
                segment_id = deterministic_segment_id(
                    release_id=release_id,
                    provision_version_id=version_id,
                    segment_index=payload["segment_index"],
                    retrieval_text_sha256=payload["retrieval_text_sha256"],
                )
                segments.append(
                    RetrievalSegment(
                        id=segment_id,
                        release_id=release_id,
                        release_entry_id=entry_id_by_version[str(version_id)],
                        provision_id=uuid.UUID(payload["provision_id"]),
                        provision_version_id=version_id,
                        source_document_id=source_id,
                        index_kind="enacted",
                        segment_index=payload["segment_index"],
                        segment_count=payload["segment_count"],
                        citation=row["citation"],
                        canonical_path=payload["canonical_path"],
                        ancestor_headings=row["ancestor_headings"],
                        ancestor_text="\n".join(row["ancestor_headings"]),
                        heading=row["heading"],
                        retrieval_text=row["retrieval_text"],
                        retrieval_text_sha256=payload["retrieval_text_sha256"],
                        authoritative_text_sha256=payload["authoritative_text_sha256"],
                    )
                )
                checksum = embedding_sha256(vector)
                embeddings.append(
                    RetrievalEmbedding(
                        id=uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{embedding_run_id}:{segment_id}:{checksum}",
                        ),
                        segment_id=segment_id,
                        release_id=release_id,
                        embedding_run_id=embedding_run_id,
                        profile_id=profile_id,
                        vector_dimensions=1024,
                        embedding=vector,
                        embedding_sha256=checksum,
                    )
                )
            session.add_all(segments)
            session.flush()
            session.add_all(embeddings)
            session.flush()
            build_id = uuid.UUID(evidence["index_build_id"])
            build = RetrievalIndexBuild(
                id=build_id,
                release_id=release_id,
                embedding_run_id=embedding_run_id,
                profile_id=profile_id,
                status=VectorIndexStatus.READY,
                expected_segment_count=len(segments),
                stored_segment_count=len(segments),
                stored_embedding_count=len(embeddings),
                vector_dimensions=1024,
                checksum=evidence["index_checksum"],
            )
            session.add(build)
            session.flush()
            validated = validate_index_build(
                session, build=build, expected_segment_count=1829
            )
            expected = evidence["index_validation"]
            if not validated["is_valid"] or any(
                validated[key] != expected[key]
                for key in (
                    "segment_checksum",
                    "embedding_checksum",
                    "stored_segment_count",
                    "stored_embedding_count",
                )
            ):
                raise ValueError(
                    f"Rebuilt index failed validation: {validated['errors']}"
                )
            build.validation_report = validated
            session.add(build)
            release = session.get(CorpusRelease, release_id)
            assert release is not None
            release.status = CorpusReleaseStatus.PRODUCTION
            session.add(release)
            session.add(
                ActiveRetrievalTarget(
                    index_kind="enacted",
                    release_id=release_id,
                    embedding_run_id=embedding_run_id,
                    retrieval_index_build_id=build_id,
                    profile_id=profile_id,
                )
            )
            session.commit()
        except BaseException:
            session.rollback()
            raise
    print(  # noqa: T201
        "Restored 1 published release, 1,850 provision identities, 1,811 versions, and 1,829 verified vectors."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest, documents, vectors, evidence, config = _prepared(args)
    print(  # noqa: T201
        f"Verified {len(manifest['entries'])} manifest entries, {len(documents)} retrieval documents, and {len(vectors)} saved embeddings."
    )
    if args.apply:
        _restore(manifest, documents, vectors, evidence, config)


if __name__ == "__main__":
    main()
