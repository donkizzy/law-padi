from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class BlobObject:
    key: str
    size_bytes: int
    sha256: str
    content_type: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class BlobHead:
    key: str
    size_bytes: int
    sha256: str
    content_type: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    last_modified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MultipartUploadPartUrl:
    part_number: int
    upload_url: str


@dataclass(frozen=True, slots=True)
class MultipartUpload:
    upload_id: str
    parts: tuple[MultipartUploadPartUrl, ...]


@dataclass(frozen=True, slots=True)
class CompletedMultipartUploadPart:
    part_number: int
    etag: str


class BlobStore(Protocol):
    """Provider-neutral object storage boundary for ingestion artifacts."""

    def quarantine_key(self, *, upload_id: str, filename: str) -> str:
        """Return the private quarantine object key for an upload."""

    def original_key(self, *, sha256: str, extension: str) -> str:
        """Return the immutable content-addressed key for a verified source."""

    def put_quarantine(
        self,
        *,
        upload_id: str,
        filename: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobObject:
        """Persist an untrusted upload under a private quarantine key."""

    def promote_quarantine_to_original(
        self,
        *,
        quarantine_key: str,
        expected_sha256: str,
        content_type: str,
        extension: str,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobObject:
        """Move a verified quarantine object into immutable content-addressed storage."""

    def head(self, key: str) -> BlobHead:
        """Return object metadata without reading the object body."""

    def open_read(self, key: str) -> AbstractContextManager[BinaryIO]:
        """Open an object for streaming reads."""

    def read_bytes(self, key: str) -> bytes:
        """Read a small object body into memory for tests and control-plane checks."""

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
        """Persist an immutable worker artifact under a run-scoped key."""

    def delete_quarantine(self, key: str) -> None:
        """Delete an untrusted quarantine object."""


class ManagedUploadBlobStore(BlobStore, Protocol):
    """Optional extension implemented by remote stores that support browser uploads."""

    def create_presigned_put_url(
        self,
        *,
        key: str,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
        expires_in_seconds: int,
    ) -> str:
        """Return a short-lived upload URL for a private object key."""

    def create_multipart_upload(
        self,
        *,
        key: str,
        content_type: str,
        part_count: int,
        metadata: Mapping[str, str] | None = None,
        expires_in_seconds: int,
    ) -> MultipartUpload:
        """Create a multipart upload and return short-lived URLs for its parts."""

    def complete_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[CompletedMultipartUploadPart],
    ) -> BlobHead:
        """Complete a browser multipart upload and return the final object head."""

    def abort_multipart_upload(self, *, key: str, upload_id: str) -> None:
        """Abort a multipart upload that cannot be completed safely."""
