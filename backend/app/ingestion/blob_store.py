import hashlib
import json
import re
from collections.abc import Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.ingestion.contracts import BlobHead, BlobObject

_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_METADATA_SUFFIX = ".metadata.json"


class BlobStoreError(ValueError):
    """Raised when a blob-store operation violates the storage contract."""


class LocalBlobStore:
    """Filesystem-backed development BlobStore.

    The directory layout mirrors the production contract: untrusted uploads live
    below quarantine keys, while verified originals are content-addressed and
    never overwritten.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_quarantine(
        self,
        *,
        upload_id: str,
        filename: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobObject:
        if not content:
            raise BlobStoreError("Quarantine objects cannot be empty")
        key = self.quarantine_key(upload_id=upload_id, filename=filename)
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        sha256 = hashlib.sha256(content).hexdigest()
        blob = BlobObject(
            key=key,
            size_bytes=len(content),
            sha256=sha256,
            content_type=content_type,
            metadata=dict(metadata or {}),
        )
        self._write_metadata(blob)
        return blob

    def promote_quarantine_to_original(
        self,
        *,
        quarantine_key: str,
        expected_sha256: str,
        content_type: str,
        extension: str,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobObject:
        quarantine_path = self._path_for_key(quarantine_key)
        if not quarantine_path.exists():
            raise FileNotFoundError(quarantine_key)

        content = quarantine_path.read_bytes()
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != expected_sha256:
            raise BlobStoreError("Quarantine object SHA-256 does not match")

        original_key = self.original_key(sha256=actual_sha256, extension=extension)
        original_path = self._path_for_key(original_key)
        original_path.parent.mkdir(parents=True, exist_ok=True)
        if original_path.exists():
            if original_path.read_bytes() != content:
                raise BlobStoreError(
                    "Content-addressed original exists with different bytes"
                )
        else:
            quarantine_path.replace(original_path)

        quarantine_path.unlink(missing_ok=True)
        self._metadata_path(quarantine_key).unlink(missing_ok=True)
        blob = BlobObject(
            key=original_key,
            size_bytes=len(content),
            sha256=actual_sha256,
            content_type=content_type,
            metadata=dict(metadata or {}),
        )
        self._write_metadata(blob)
        return blob

    def head(self, key: str) -> BlobHead:
        path = self._path_for_key(key)
        if not path.exists():
            raise FileNotFoundError(key)
        metadata = self._read_metadata(key)
        return BlobHead(
            key=key,
            size_bytes=path.stat().st_size,
            sha256=metadata.get("sha256")
            or hashlib.sha256(path.read_bytes()).hexdigest(),
            content_type=metadata.get("content_type") or "application/octet-stream",
            metadata={
                item.removeprefix("metadata."): value
                for item, value in metadata.items()
                if item.startswith("metadata.")
            },
            last_modified_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
        )

    def open_read(self, key: str) -> AbstractContextManager[BinaryIO]:
        return self._path_for_key(key).open("rb")

    def read_bytes(self, key: str) -> bytes:
        return self._path_for_key(key).read_bytes()

    def put_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        filename: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobObject:
        if not content:
            raise BlobStoreError("Artifact objects cannot be empty")
        safe_run_id = _safe_segment(run_id, fallback="run")
        safe_artifact_type = _safe_segment(artifact_type, fallback="artifact")
        safe_filename = _safe_segment(filename, fallback="artifact")
        key = f"runs/{safe_run_id}/artifacts/{safe_artifact_type}/{safe_filename}"
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise BlobStoreError(
                    "Immutable artifact already exists with different bytes"
                )
            head = self.head(key)
            return BlobObject(
                key=key,
                size_bytes=head.size_bytes,
                sha256=head.sha256,
                content_type=head.content_type,
                metadata=head.metadata,
            )
        path.write_bytes(content)
        blob = BlobObject(
            key=key,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content_type=content_type,
            metadata=dict(metadata or {}),
        )
        self._write_metadata(blob)
        return blob

    def delete_quarantine(self, key: str) -> None:
        normalized_key = _normalize_key(key)
        if not normalized_key.startswith("quarantine/"):
            raise BlobStoreError("Only quarantine objects can be deleted")
        self._path_for_key(normalized_key).unlink(missing_ok=True)
        self._metadata_path(normalized_key).unlink(missing_ok=True)

    def quarantine_key(self, *, upload_id: str, filename: str) -> str:
        return quarantine_key(upload_id=upload_id, filename=filename)

    def original_key(self, *, sha256: str, extension: str) -> str:
        return original_key(sha256=sha256, extension=extension)

    def _path_for_key(self, key: str) -> Path:
        normalized_key = _normalize_key(key)
        path = (self.root / normalized_key).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise BlobStoreError("Blob key escapes the storage root")
        return path

    def _metadata_path(self, key: str) -> Path:
        return self._path_for_key(f"{_normalize_key(key)}{_METADATA_SUFFIX}")

    def _write_metadata(self, blob: BlobObject) -> None:
        payload = {
            "key": blob.key,
            "size_bytes": str(blob.size_bytes),
            "sha256": blob.sha256,
            "content_type": blob.content_type,
            "created_at": blob.created_at.isoformat(),
            **{f"metadata.{key}": value for key, value in blob.metadata.items()},
        }
        metadata_path = self._metadata_path(blob.key)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def _read_metadata(self, key: str) -> dict[str, str]:
        metadata_path = self._metadata_path(key)
        if not metadata_path.exists():
            return {}
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in payload.items()}


def _normalize_key(key: str) -> str:
    path = PurePosixPath(key)
    if key.startswith("/") or not key or ".." in path.parts:
        raise BlobStoreError("Blob key must be a relative object key")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise BlobStoreError("Blob key must not be empty")
    return normalized


def quarantine_key(*, upload_id: str, filename: str) -> str:
    safe_upload_id = _safe_segment(upload_id, fallback="upload")
    safe_filename = _safe_segment(filename, fallback="source")
    return f"quarantine/{safe_upload_id}/{safe_filename}"


def original_key(*, sha256: str, extension: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise BlobStoreError("Original keys require a lowercase SHA-256 digest")
    suffix = extension if extension.startswith(".") else f".{extension}"
    if not re.fullmatch(r"\.[A-Za-z0-9]+", suffix):
        raise BlobStoreError("Original file extension is invalid")
    return f"sources/sha256/{sha256}/original{suffix.lower()}"


def _safe_segment(value: str, *, fallback: str) -> str:
    sanitized = _SAFE_FILENAME_PATTERN.sub("-", value.strip()).strip(".-")
    return sanitized or fallback
