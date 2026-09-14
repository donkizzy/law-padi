import hashlib
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.ingestion import CompletedMultipartUploadPart, R2BlobStore
from app.ingestion.blob_store import BlobStoreError


def test_r2_blob_store_satisfies_blob_store_contract() -> None:
    transport = _R2MemoryTransport()
    store = _store(transport)
    content = b"%PDF-1.7\nconstitution source"

    quarantine = store.put_quarantine(
        upload_id="upload-1",
        filename="constitution.pdf",
        content=content,
        content_type="application/pdf",
        metadata={"source-url": "https://example.test/constitution.pdf"},
    )

    assert quarantine.key == "quarantine/upload-1/constitution.pdf"
    assert quarantine.sha256 == hashlib.sha256(content).hexdigest()
    assert store.read_bytes(quarantine.key) == content
    assert store.head(quarantine.key).metadata["source-url"] == (
        "https://example.test/constitution.pdf"
    )

    original = store.promote_quarantine_to_original(
        quarantine_key=quarantine.key,
        expected_sha256=quarantine.sha256,
        content_type="application/pdf",
        extension=".pdf",
        metadata={"source-upload-id": "upload-1"},
    )

    assert original.key == f"sources/sha256/{quarantine.sha256}/original.pdf"
    assert store.read_bytes(original.key) == content
    assert store.head(original.key).metadata["source-upload-id"] == "upload-1"
    with pytest.raises(FileNotFoundError):
        store.head(quarantine.key)


def test_r2_presigned_put_url_binds_content_type_and_sha256_metadata() -> None:
    store = _store(_R2MemoryTransport())

    upload_url = store.create_presigned_put_url(
        key="quarantine/upload-1/constitution.pdf",
        content_type="application/pdf",
        metadata={"sha256": "a" * 64},
        expires_in_seconds=900,
    )

    parsed = urlsplit(upload_url)
    query = parse_qs(parsed.query)
    assert parsed.path == "/law-padi-ingestion/quarantine/upload-1/constitution.pdf"
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == ["900"]
    assert "AKIA_TEST/20260911/auto/s3/aws4_request" in query["X-Amz-Credential"][0]
    assert query["X-Amz-SignedHeaders"] == [
        "content-type;host;x-amz-meta-sha256"
    ]
    assert len(query["X-Amz-Signature"][0]) == 64
    assert "SECRET_TEST" not in upload_url


def test_r2_multipart_upload_signs_parts_and_completes_with_sorted_etags() -> None:
    transport = _R2MemoryTransport()
    store = _store(transport)

    multipart = store.create_multipart_upload(
        key="quarantine/upload-1/large-constitution.pdf",
        content_type="application/pdf",
        part_count=2,
        metadata={"sha256": "b" * 64},
        expires_in_seconds=900,
    )

    assert multipart.upload_id == "multipart-1"
    assert [part.part_number for part in multipart.parts] == [1, 2]
    first_part_query = parse_qs(urlsplit(multipart.parts[0].upload_url).query)
    assert first_part_query["partNumber"] == ["1"]
    assert first_part_query["uploadId"] == ["multipart-1"]
    assert first_part_query["X-Amz-SignedHeaders"] == ["host"]

    response_2 = transport.browser_put_part(
        multipart.parts[1].upload_url,
        b"second",
    )
    response_1 = transport.browser_put_part(
        multipart.parts[0].upload_url,
        b"first",
    )
    head = store.complete_multipart_upload(
        key="quarantine/upload-1/large-constitution.pdf",
        upload_id=multipart.upload_id,
        parts=[
            CompletedMultipartUploadPart(
                part_number=2, etag=response_2.headers["etag"]
            ),
            CompletedMultipartUploadPart(
                part_number=1, etag=response_1.headers["etag"]
            ),
        ],
    )

    assert head.size_bytes == len(b"firstsecond")
    assert head.sha256 == "b" * 64
    assert store.read_bytes("quarantine/upload-1/large-constitution.pdf") == (
        b"firstsecond"
    )
    completion_request = next(
        request
        for request in reversed(transport.requests)
        if request.method == "POST" and "uploadId=multipart-1" in str(request.url)
    )
    assert completion_request.method == "POST"
    assert b"<PartNumber>1</PartNumber>" in completion_request.content
    assert completion_request.content.index(b"<PartNumber>1</PartNumber>") < (
        completion_request.content.index(b"<PartNumber>2</PartNumber>")
    )


def test_r2_delete_quarantine_refuses_canonical_objects() -> None:
    store = _store(_R2MemoryTransport())

    with pytest.raises(BlobStoreError, match="Only quarantine"):
        store.delete_quarantine("sources/sha256/" + "a" * 64 + "/original.pdf")


def test_r2_put_artifact_verifies_existing_object_without_sha_metadata() -> None:
    transport = _R2MemoryTransport()
    store = _store(transport)
    transport.objects["runs/run-1/artifacts/raw/page-0001.json"] = (
        b'{"text":"old"}',
        {"content-type": "application/json"},
    )

    with pytest.raises(BlobStoreError, match="Immutable artifact"):
        store.put_artifact(
            run_id="run-1",
            artifact_type="raw",
            filename="page-0001.json",
            content=b'{"text":"new"}',
            content_type="application/json",
        )


def _store(transport: "_R2MemoryTransport") -> R2BlobStore:
    return R2BlobStore(
        endpoint_url="https://r2.example.test",
        bucket_name="law-padi-ingestion",
        access_key_id="AKIA_TEST",
        secret_access_key="SECRET_TEST",
        client=httpx.Client(transport=httpx.MockTransport(transport.handle)),
        clock=lambda: datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
    )


class _R2MemoryTransport:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, str]]] = {}
        self.multipart_uploads: dict[str, dict[int, bytes]] = {}
        self.multipart_metadata: dict[str, dict[str, str]] = {}
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = self._key(request)
        params = dict(request.url.params.multi_items())
        if request.method == "POST" and "uploads" in params:
            return self._create_multipart(request)
        if request.method == "PUT" and {"partNumber", "uploadId"} <= set(params):
            return self._put_multipart_part(request, params)
        if request.method == "POST" and "uploadId" in params:
            return self._complete_multipart(key, params)
        if request.method == "PUT":
            return self._put_object(request, key)
        if request.method == "HEAD":
            return self._head_object(key)
        if request.method == "GET":
            return self._get_object(key)
        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)
        return httpx.Response(400)

    def browser_put_part(self, upload_url: str, content: bytes) -> httpx.Response:
        request = httpx.Request("PUT", upload_url, content=content)
        return self.handle(request)

    def _create_multipart(self, request: httpx.Request) -> httpx.Response:
        upload_id = f"multipart-{len(self.multipart_uploads) + 1}"
        self.multipart_uploads[upload_id] = {}
        self.multipart_metadata[upload_id] = _metadata_from_request(request)
        return httpx.Response(
            200,
            content=(
                "<InitiateMultipartUploadResult>"
                f"<UploadId>{upload_id}</UploadId>"
                "</InitiateMultipartUploadResult>"
            ),
        )

    def _put_multipart_part(
        self, request: httpx.Request, params: dict[str, str]
    ) -> httpx.Response:
        upload_id = params["uploadId"]
        part_number = int(params["partNumber"])
        self.multipart_uploads[upload_id][part_number] = request.content
        return httpx.Response(200, headers={"etag": f'"etag-{part_number}"'})

    def _complete_multipart(
        self, key: str, params: dict[str, str]
    ) -> httpx.Response:
        upload_id = params["uploadId"]
        parts = self.multipart_uploads[upload_id]
        content = b"".join(parts[part_number] for part_number in sorted(parts))
        headers = {
            "content-type": "application/pdf",
            **self.multipart_metadata[upload_id],
        }
        self.objects[key] = (content, headers)
        return httpx.Response(200)

    def _put_object(self, request: httpx.Request, key: str) -> httpx.Response:
        copy_source = request.headers.get("x-amz-copy-source")
        headers = {
            "content-type": request.headers.get(
                "content-type", "application/octet-stream"
            ),
            **_metadata_from_request(request),
        }
        if copy_source:
            source_key = "/".join(copy_source.split("/")[2:])
            self.objects[key] = (self.objects[source_key][0], headers)
        else:
            self.objects[key] = (request.content, headers)
        return httpx.Response(200)

    def _head_object(self, key: str) -> httpx.Response:
        if key not in self.objects:
            return httpx.Response(404)
        content, headers = self.objects[key]
        return httpx.Response(
            200,
            headers={
                **headers,
                "content-length": str(len(content)),
                "last-modified": "Fri, 11 Sep 2026 12:00:00 GMT",
            },
        )

    def _get_object(self, key: str) -> httpx.Response:
        if key not in self.objects:
            return httpx.Response(404)
        content, headers = self.objects[key]
        return httpx.Response(200, content=content, headers=headers)

    def _key(self, request: httpx.Request) -> str:
        path_parts = request.url.path.lstrip("/").split("/")
        return "/".join(path_parts[1:])


def _metadata_from_request(request: httpx.Request) -> dict[str, str]:
    return {
        header.lower(): value
        for header, value in request.headers.items()
        if header.lower().startswith("x-amz-meta-")
    }
