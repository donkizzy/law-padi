from pathlib import Path

import pytest

from app.ingestion import BlobStore, LocalBlobStore
from app.ingestion.blob_store import BlobStoreError


def test_local_blob_store_satisfies_blob_store_contract(tmp_path: Path) -> None:
    store: BlobStore = LocalBlobStore(tmp_path)
    content = b"%PDF-1.7\nconstitution source"

    quarantine = store.put_quarantine(
        upload_id="upload-1",
        filename="constitution.pdf",
        content=content,
        content_type="application/pdf",
        metadata={"source_url": "https://example.test/constitution.pdf"},
    )

    assert quarantine.key == "quarantine/upload-1/constitution.pdf"
    assert quarantine.size_bytes == len(content)
    assert quarantine.sha256
    assert store.read_bytes(quarantine.key) == content

    quarantine_head = store.head(quarantine.key)
    assert quarantine_head.content_type == "application/pdf"
    assert quarantine_head.metadata["source_url"] == (
        "https://example.test/constitution.pdf"
    )

    original = store.promote_quarantine_to_original(
        quarantine_key=quarantine.key,
        expected_sha256=quarantine.sha256,
        content_type="application/pdf",
        extension=".pdf",
        metadata={"source_upload_id": "upload-1"},
    )

    assert original.key == f"sources/sha256/{quarantine.sha256}/original.pdf"
    assert store.read_bytes(original.key) == content
    assert store.head(original.key).metadata["source_upload_id"] == "upload-1"
    with pytest.raises(FileNotFoundError):
        store.head(quarantine.key)


def test_put_artifact_stores_immutable_run_artifacts(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    content = b'{"page": 1, "text": "Section 37"}'

    artifact = store.put_artifact(
        run_id="run-1",
        artifact_type="raw_extraction",
        filename="page-0001.json",
        content=content,
        content_type="application/json",
        metadata={"page_number": "1"},
    )
    duplicate = store.put_artifact(
        run_id="run-1",
        artifact_type="raw_extraction",
        filename="page-0001.json",
        content=content,
        content_type="application/json",
    )

    assert artifact.key == "runs/run-1/artifacts/raw_extraction/page-0001.json"
    assert duplicate.key == artifact.key
    assert store.read_bytes(artifact.key) == content
    assert store.head(artifact.key).metadata["page_number"] == "1"
    with pytest.raises(BlobStoreError, match="Immutable artifact"):
        store.put_artifact(
            run_id="run-1",
            artifact_type="raw_extraction",
            filename="page-0001.json",
            content=b"different",
            content_type="application/json",
        )


def test_promote_reuses_existing_content_addressed_original(
    tmp_path: Path,
) -> None:
    store = LocalBlobStore(tmp_path)
    content = b"CHAPTER I\n1. Supremacy of the Constitution"
    first = store.put_quarantine(
        upload_id="first",
        filename="constitution.txt",
        content=content,
        content_type="text/plain",
    )
    original = store.promote_quarantine_to_original(
        quarantine_key=first.key,
        expected_sha256=first.sha256,
        content_type="text/plain",
        extension="txt",
    )
    second = store.put_quarantine(
        upload_id="second",
        filename="constitution-copy.txt",
        content=content,
        content_type="text/plain",
    )

    duplicate = store.promote_quarantine_to_original(
        quarantine_key=second.key,
        expected_sha256=second.sha256,
        content_type="text/plain",
        extension=".txt",
    )

    assert duplicate.key == original.key
    assert store.read_bytes(original.key) == content
    with pytest.raises(FileNotFoundError):
        store.head(second.key)


def test_promote_rejects_hash_mismatch(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    quarantine = store.put_quarantine(
        upload_id="upload",
        filename="constitution.pdf",
        content=b"%PDF-1.7\nreal bytes",
        content_type="application/pdf",
    )

    with pytest.raises(BlobStoreError, match="SHA-256"):
        store.promote_quarantine_to_original(
            quarantine_key=quarantine.key,
            expected_sha256="0" * 64,
            content_type="application/pdf",
            extension=".pdf",
        )

    assert store.read_bytes(quarantine.key) == b"%PDF-1.7\nreal bytes"


def test_local_blob_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)

    with pytest.raises(BlobStoreError):
        store.head("../outside.pdf")
    with pytest.raises(BlobStoreError):
        store.read_bytes("/absolute.pdf")
    with pytest.raises(BlobStoreError):
        store.delete_quarantine("sources/sha256/not-quarantine/original.pdf")


def test_original_key_requires_sha256_and_safe_extension(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)

    with pytest.raises(BlobStoreError):
        store.original_key(sha256="not-a-digest", extension=".pdf")
    with pytest.raises(BlobStoreError):
        store.original_key(sha256="a" * 64, extension="../pdf")
