import hashlib
import hmac
import re
import tempfile
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import BinaryIO
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import httpx

from app.ingestion.blob_store import (
    BlobStoreError,
    original_key,
    quarantine_key,
    verify_blob_contents,
)
from app.ingestion.contracts import (
    BlobHead,
    BlobObject,
    CompletedMultipartUploadPart,
    MultipartUpload,
    MultipartUploadPartUrl,
)
from app.ingestion.runtime.retry import request_with_retries

_ALGORITHM = "AWS4-HMAC-SHA256"
_REGION = "auto"
_SERVICE = "s3"
_TERMINATOR = "aws4_request"
_UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"
_SAFE_METADATA_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


_MIN_UPLOAD_BYTES_PER_SECOND = 256 * 1024


class R2BlobStore:
    """Cloudflare R2 BlobStore using the S3-compatible API."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not endpoint_url:
            raise BlobStoreError("R2 endpoint URL is required")
        if not bucket_name:
            raise BlobStoreError("R2 bucket name is required")
        if not access_key_id or not secret_access_key:
            raise BlobStoreError("R2 access key ID and secret access key are required")

        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket_name = bucket_name
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self._client = client or httpx.Client(timeout=30)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._host = urlsplit(self.endpoint_url).netloc

    def quarantine_key(self, *, upload_id: str, filename: str) -> str:
        return quarantine_key(upload_id=upload_id, filename=filename)

    def original_key(self, *, sha256: str, extension: str) -> str:
        return original_key(sha256=sha256, extension=extension)

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
        return self._put_object(
            key=key,
            content=content,
            content_type=content_type,
            metadata=metadata,
        )

    def put_verified_original(
        self,
        *,
        stream: BinaryIO,
        expected_sha256: str,
        size_bytes: int,
        content_type: str,
        extension: str,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobObject:
        canonical_key = self.original_key(sha256=expected_sha256, extension=extension)
        merged_metadata = {**dict(metadata or {}), "sha256": expected_sha256}
        position = stream.tell()

        def content_factory() -> Iterator[bytes]:
            stream.seek(position)
            return iter(lambda: stream.read(1024 * 1024), b"")

        response = self._request(
            "PUT",
            canonical_key,
            headers={
                "content-length": str(size_bytes),
                "content-type": content_type,
                "if-none-match": "*",
                **_metadata_headers(merged_metadata),
            },
            content_factory=content_factory,
            payload_sha256=expected_sha256,
            expected_statuses={200, 412},
        )
        if response.status_code == 412:
            verify_blob_contents(
                self,
                canonical_key,
                expected_sha256=expected_sha256,
                size_bytes=size_bytes,
            )
        return BlobObject(
            key=canonical_key,
            size_bytes=size_bytes,
            sha256=expected_sha256,
            content_type=content_type,
            metadata=merged_metadata,
        )

    def head(self, key: str) -> BlobHead:
        response = self._request("HEAD", key)
        metadata = {}
        for header, value in response.headers.items():
            normalized_header = header.lower()
            if normalized_header.startswith("x-amz-meta-"):
                metadata[normalized_header.removeprefix("x-amz-meta-")] = value
        content_length = response.headers.get("content-length", "0")
        content_type = response.headers.get("content-type", "application/octet-stream")
        return BlobHead(
            key=key,
            size_bytes=int(content_length),
            sha256=metadata.get("sha256") or _sha256_from_etag(response),
            content_type=content_type,
            metadata=metadata,
            last_modified_at=_parse_http_datetime(
                response.headers.get("last-modified")
            ),
        )

    @contextmanager
    def open_read(self, key: str) -> Iterator[BinaryIO]:
        with tempfile.TemporaryFile(mode="w+b") as temporary:
            with closing(self.iter_read(key)) as chunks:
                for chunk in chunks:
                    temporary.write(chunk)
            temporary.seek(0)
            yield temporary

    def read_bytes(self, key: str) -> bytes:
        response = self._request("GET", key)
        return response.content

    def iter_read(self, key: str) -> Generator[bytes]:
        """Read an object incrementally for checksum verification."""
        headers = self._signed_headers(
            "GET",
            key,
            query={},
            headers={},
            payload_hash=hashlib.sha256(b"").hexdigest(),
        )
        response = request_with_retries(
            lambda remaining: self._client.send(
                self._client.build_request(
                    "GET",
                    self._object_url(key),
                    headers=headers,
                    timeout=min(30, remaining),
                ),
                stream=True,
            )
        )
        try:
            if response.status_code == 404:
                raise FileNotFoundError(key)
            if response.status_code != 200:
                raise BlobStoreError(
                    f"R2 GET failed for {key}: HTTP {response.status_code}"
                ) from httpx.HTTPStatusError(
                    "R2 request failed", request=response.request, response=response
                )
            yield from response.iter_bytes(chunk_size=1024 * 1024)
        finally:
            response.close()

    def put_if_absent(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, str],
    ) -> bool:
        """Create an exact key, leaving any existing object intact."""
        response = self._request(
            "PUT",
            key,
            headers={
                **_metadata_headers(metadata),
                "content-type": content_type,
                "if-none-match": "*",
            },
            content=content,
            expected_statuses={200, 412},
        )
        return response.status_code == 200

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
        key = (
            f"runs/{_safe_segment(run_id, fallback='run')}/artifacts/"
            f"{_safe_segment(artifact_type, fallback='artifact')}/"
            f"{_safe_segment(filename, fallback='artifact')}"
        )
        try:
            existing_head = self.head(key)
        except FileNotFoundError:
            return self._put_object(
                key=key,
                content=content,
                content_type=content_type,
                metadata=metadata,
            )
        if existing_head.sha256:
            actual_sha256 = hashlib.sha256(content).hexdigest()
            if existing_head.sha256 != actual_sha256:
                raise BlobStoreError(
                    "Immutable artifact already exists with different bytes"
                )
        elif self.read_bytes(key) != content:
            raise BlobStoreError(
                "Immutable artifact already exists with different bytes"
            )
        return BlobObject(
            key=key,
            size_bytes=existing_head.size_bytes,
            sha256=existing_head.sha256,
            content_type=existing_head.content_type,
            metadata=existing_head.metadata,
        )

    def delete_quarantine(self, key: str) -> None:
        if not key.startswith("quarantine/"):
            raise BlobStoreError("Only quarantine objects can be deleted")
        self._request("DELETE", key, expected_statuses={200, 204, 404})

    def create_presigned_put_url(
        self,
        *,
        key: str,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
        expires_in_seconds: int,
    ) -> str:
        return self._presign(
            "PUT",
            key,
            query={},
            headers={
                "content-type": content_type,
                **_metadata_headers(metadata or {}),
            },
            expires_in_seconds=expires_in_seconds,
        )

    def create_presigned_get_url(self, *, key: str, expires_in_seconds: int) -> str:
        """Return a short-lived private download URL for an artifact."""
        return self._presign(
            "GET",
            key,
            query={},
            headers={},
            expires_in_seconds=expires_in_seconds,
        )

    def create_multipart_upload(
        self,
        *,
        key: str,
        content_type: str,
        part_count: int,
        metadata: Mapping[str, str] | None = None,
        expires_in_seconds: int,
    ) -> MultipartUpload:
        if part_count < 1:
            raise BlobStoreError("Multipart upload requires at least one part")
        response = self._request(
            "POST",
            key,
            query={"uploads": ""},
            headers={
                "content-type": content_type,
                **_metadata_headers(metadata or {}),
            },
        )
        upload_id = _multipart_upload_id(response.content)
        parts = tuple(
            MultipartUploadPartUrl(
                part_number=part_number,
                upload_url=self._presign(
                    "PUT",
                    key,
                    query={"partNumber": str(part_number), "uploadId": upload_id},
                    headers={},
                    expires_in_seconds=expires_in_seconds,
                ),
            )
            for part_number in range(1, part_count + 1)
        )
        return MultipartUpload(upload_id=upload_id, parts=parts)

    def complete_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[CompletedMultipartUploadPart],
    ) -> BlobHead:
        self._complete_multipart_upload(key=key, upload_id=upload_id, parts=parts)
        return self.head(key)

    def complete_multipart_upload_if_absent(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[CompletedMultipartUploadPart],
    ) -> bool:
        return self._complete_multipart_upload(
            key=key, upload_id=upload_id, parts=parts, if_absent=True
        )

    def _complete_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[CompletedMultipartUploadPart],
        if_absent: bool = False,
    ) -> bool:
        if not parts:
            raise BlobStoreError("Multipart completion requires at least one part")
        root = ElementTree.Element("CompleteMultipartUpload")
        for part in sorted(parts, key=lambda item: item.part_number):
            part_element = ElementTree.SubElement(root, "Part")
            ElementTree.SubElement(part_element, "PartNumber").text = str(
                part.part_number
            )
            ElementTree.SubElement(part_element, "ETag").text = part.etag
        payload = ElementTree.tostring(root, encoding="utf-8")
        headers = {"content-type": "application/xml"}
        if if_absent:
            headers["if-none-match"] = "*"
        response = self._request(
            "POST",
            key,
            query={"uploadId": upload_id},
            headers=headers,
            content=payload,
            expected_statuses={200, 412} if if_absent else {200},
        )
        return response.status_code == 200

    def abort_multipart_upload(self, *, key: str, upload_id: str) -> None:
        self._request(
            "DELETE",
            key,
            query={"uploadId": upload_id},
            expected_statuses={200, 204},
        )

    def _put_object(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, str] | None,
    ) -> BlobObject:
        sha256 = hashlib.sha256(content).hexdigest()
        merged_metadata = {"sha256": sha256, **dict(metadata or {})}
        headers = {"content-type": content_type, **_metadata_headers(merged_metadata)}
        self._request("PUT", key, headers=headers, content=content)
        return BlobObject(
            key=key,
            size_bytes=len(content),
            sha256=sha256,
            content_type=content_type,
            metadata=merged_metadata,
        )

    def _request(
        self,
        method: str,
        key: str,
        *,
        query: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        content: bytes | Iterator[bytes] = b"",
        payload_sha256: str | None = None,
        content_factory: Callable[[], Iterator[bytes]] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> httpx.Response:
        url = self._object_url(key, query=query)
        if payload_sha256 is None:
            if not isinstance(content, bytes):
                raise BlobStoreError("Streaming R2 requests require a payload checksum")
            payload_sha256 = hashlib.sha256(content).hexdigest()
        signed_headers = self._signed_headers(
            method,
            key,
            query=query or {},
            headers=headers or {},
            payload_hash=payload_sha256,
        )

        timeout = self._timeout_for(content)
        write_timeout: float = timeout.as_dict()["write"] or 0.0
        if content_factory:
            size = int((headers or {}).get("content-length", "0"))
            timeout = httpx.Timeout(
                **{
                    **timeout.as_dict(),
                    "write": max(
                        write_timeout,
                        size / _MIN_UPLOAD_BYTES_PER_SECOND,
                    ),
                }
            )

        def send(remaining: float) -> httpx.Response:
            return self._client.request(
                method,
                url,
                headers=signed_headers,
                content=content_factory() if content_factory else content,
                timeout=httpx.Timeout(
                    **{
                        name: min(value, remaining) if value is not None else remaining
                        for name, value in timeout.as_dict().items()
                    }
                ),
            )

        response = request_with_retries(
            send,
            max_attempts=5 if isinstance(content, bytes) or content_factory else 1,
            deadline_seconds=max(120, (timeout.as_dict()["write"] or 0.0) + 30),
        )
        expected = expected_statuses or {200}
        if response.status_code == 404 and 404 not in expected:
            raise FileNotFoundError(key)
        if response.status_code not in expected:
            raise BlobStoreError(
                f"R2 {method} failed for {key}: HTTP {response.status_code}"
            ) from httpx.HTTPStatusError(
                "R2 request failed", request=response.request, response=response
            )
        return response

    def _timeout_for(self, content: bytes | Iterator[bytes]) -> httpx.Timeout:
        """Allow one write long enough to send the whole body at a slow uplink."""
        timeout = self._client.timeout
        if not isinstance(content, bytes):
            return timeout
        limits = timeout.as_dict()
        write = max(limits["write"] or 0, len(content) / _MIN_UPLOAD_BYTES_PER_SECOND)
        return httpx.Timeout(
            connect=limits["connect"],
            read=limits["read"],
            write=write,
            pool=limits["pool"],
        )

    def _signed_headers(
        self,
        method: str,
        key: str,
        *,
        query: Mapping[str, str],
        headers: Mapping[str, str],
        payload_hash: str,
    ) -> dict[str, str]:
        now = self._clock()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        request_headers = {
            _normalize_header_name(name): value.strip()
            for name, value in headers.items()
        }
        request_headers["host"] = self._host
        request_headers["x-amz-content-sha256"] = payload_hash
        request_headers["x-amz-date"] = amz_date
        signed_headers = _signed_header_names(request_headers)
        canonical_request = _canonical_request(
            method=method,
            key=key,
            bucket_name=self.bucket_name,
            query=query,
            headers=request_headers,
            signed_headers=signed_headers,
            payload_hash=payload_hash,
        )
        credential_scope = _credential_scope(now)
        string_to_sign = "\n".join(
            [
                _ALGORITHM,
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signature = _signature(
            secret_access_key=self.secret_access_key,
            date_stamp=now.strftime("%Y%m%d"),
            string_to_sign=string_to_sign,
        )
        request_headers["authorization"] = (
            f"{_ALGORITHM} Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return request_headers

    def _presign(
        self,
        method: str,
        key: str,
        *,
        query: Mapping[str, str],
        headers: Mapping[str, str],
        expires_in_seconds: int,
    ) -> str:
        if expires_in_seconds < 1 or expires_in_seconds > 604800:
            raise BlobStoreError("Presigned URL expiry must be between 1 and 604800")
        now = self._clock()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        credential_scope = _credential_scope(now)
        presign_headers = {
            _normalize_header_name(name): value.strip()
            for name, value in headers.items()
        }
        presign_headers["host"] = self._host
        signed_headers = _signed_header_names(presign_headers)
        presign_query = {
            **dict(query),
            "X-Amz-Algorithm": _ALGORITHM,
            "X-Amz-Credential": f"{self.access_key_id}/{credential_scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_in_seconds),
            "X-Amz-SignedHeaders": signed_headers,
        }
        canonical_request = _canonical_request(
            method=method,
            key=key,
            bucket_name=self.bucket_name,
            query=presign_query,
            headers=presign_headers,
            signed_headers=signed_headers,
            payload_hash=_UNSIGNED_PAYLOAD,
        )
        string_to_sign = "\n".join(
            [
                _ALGORITHM,
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        presign_query["X-Amz-Signature"] = _signature(
            secret_access_key=self.secret_access_key,
            date_stamp=now.strftime("%Y%m%d"),
            string_to_sign=string_to_sign,
        )
        return self._object_url(key, query=presign_query)

    def _object_url(self, key: str, *, query: Mapping[str, str] | None = None) -> str:
        url = (
            f"{self.endpoint_url}/{quote(self.bucket_name, safe='')}/{_quote_key(key)}"
        )
        if query:
            return f"{url}?{_canonical_query(query)}"
        return url


def _canonical_request(
    *,
    method: str,
    key: str,
    bucket_name: str,
    query: Mapping[str, str],
    headers: Mapping[str, str],
    signed_headers: str,
    payload_hash: str,
) -> str:
    return "\n".join(
        [
            method.upper(),
            f"/{quote(bucket_name, safe='')}/{_quote_key(key)}",
            _canonical_query(query),
            _canonical_headers(headers),
            signed_headers,
            payload_hash,
        ]
    )


def _canonical_headers(headers: Mapping[str, str]) -> str:
    return "".join(
        f"{name}:{' '.join(value.split())}\n" for name, value in sorted(headers.items())
    )


def _canonical_query(query: Mapping[str, str]) -> str:
    encoded = [
        (quote(str(name), safe="-_.~"), quote(str(value), safe="-_.~"))
        for name, value in query.items()
    ]
    return "&".join(f"{name}={value}" for name, value in sorted(encoded))


def _credential_scope(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d')}/{_REGION}/{_SERVICE}/{_TERMINATOR}"


def _metadata_headers(metadata: Mapping[str, str]) -> dict[str, str]:
    return {
        f"x-amz-meta-{_safe_metadata_name(name)}": value
        for name, value in metadata.items()
    }


def _multipart_upload_id(content: bytes) -> str:
    root = ElementTree.fromstring(content)
    upload_id = root.findtext(".//{*}UploadId") or root.findtext("UploadId")
    if not upload_id:
        raise BlobStoreError("R2 multipart upload response did not include UploadId")
    return upload_id


def _normalize_header_name(name: str) -> str:
    return name.strip().lower()


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _quote_key(key: str) -> str:
    if key.startswith("/") or not key or "/../" in f"/{key}/":
        raise BlobStoreError("Blob key must be a relative object key")
    return "/".join(quote(part, safe="-_.~") for part in key.split("/"))


def _safe_metadata_name(name: str) -> str:
    safe = _SAFE_METADATA_PATTERN.sub("-", name.strip()).strip(".-").lower()
    if not safe:
        raise BlobStoreError("Metadata keys must not be empty")
    return safe


def _safe_segment(value: str, *, fallback: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return sanitized or fallback


def _sha256_from_etag(response: httpx.Response) -> str:
    etag = str(response.headers.get("etag", "")).strip('"')
    if re.fullmatch(r"[a-fA-F0-9]{64}", etag):
        return etag.lower()
    return ""


def _signature(*, secret_access_key: str, date_stamp: str, string_to_sign: str) -> str:
    key = _signing_key(secret_access_key, date_stamp)
    return hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()


def _signing_key(secret_access_key: str, date_stamp: str) -> bytes:
    date_key = hmac.new(
        f"AWS4{secret_access_key}".encode(),
        date_stamp.encode(),
        hashlib.sha256,
    ).digest()
    region_key = hmac.new(date_key, _REGION.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, _SERVICE.encode(), hashlib.sha256).digest()
    return hmac.new(service_key, _TERMINATOR.encode(), hashlib.sha256).digest()


def _signed_header_names(headers: Mapping[str, str]) -> str:
    return ";".join(sorted(headers))
