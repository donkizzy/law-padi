from typing import Any

import httpx
import pytest

from app.ingestion.embedding import (
    HuggingFaceTeiEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.ingestion.ocr import (
    AzureDocumentIntelligenceOcrProvider,
    GoogleDocumentAiOcrProvider,
    OcrPageInput,
)
from app.ingestion.r2_blob_store import R2BlobStore


@pytest.mark.parametrize("provider", ["r2", "openai", "tei", "google", "azure"])
@pytest.mark.parametrize("permanent", [False, True])
def test_clients_retry_transport_and_provider_outages_only(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    permanent: bool,
) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if provider == "azure" and request.method == "POST":
            return httpx.Response(
                202, headers={"Operation-Location": "https://test/operation"}
            )
        calls += 1
        if permanent:
            return httpx.Response(400, text="invalid input")
        if calls == 1:
            raise httpx.ConnectError("connection reset", request=request)
        if calls == 2:
            return httpx.Response(503)
        if calls == 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [1.0, 0.0]}],
                "document": {"text": "hello", "pages": []},
                "status": "succeeded",
                "analyzeResult": {"content": "hello", "pages": []},
            }
            if provider != "tei"
            else [[1.0, 0.0]],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    if provider == "r2":
        store = R2BlobStore(
            endpoint_url="https://test",
            bucket_name="test",
            access_key_id="test",
            secret_access_key="test",
            client=client,
        )

        def invoke() -> Any:
            return store.read_bytes("key")
    elif provider == "openai":
        embedder = OpenAIEmbeddingProvider(
            api_key="test", transport=httpx.MockTransport(handler)
        )

        def invoke() -> Any:
            return embedder.embed(["hello"])
    elif provider == "tei":
        tei = HuggingFaceTeiEmbeddingProvider(
            endpoint_url="https://test",
            api_token="test",
            transport=httpx.MockTransport(handler),
            sleep=lambda _: None,
        )

        def invoke() -> Any:
            return tei.embed(["hello"])
    elif provider == "google":
        google = GoogleDocumentAiOcrProvider(
            processor_name="test",
            access_token="test",
            endpoint_url="https://test",
            client=client,
        )

        def invoke() -> Any:
            return google.extract_page(OcrPageInput(1, b"png", "image/png"))
    else:
        azure = AzureDocumentIntelligenceOcrProvider(
            endpoint="https://test", api_key="test", client=client
        )

        def invoke() -> Any:
            return azure.extract_page(OcrPageInput(1, b"png", "image/png"))

    if permanent:
        with pytest.raises((ValueError, RuntimeError)):
            invoke()
        assert calls == 1
    else:
        invoke()
        assert calls == 4


def test_retry_budget_honors_retry_after_and_stops_before_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ingestion.runtime import retry

    elapsed = [0.0]
    timeouts: list[float] = []
    monkeypatch.setattr(retry.time, "monotonic", lambda: elapsed[0])

    def send(remaining: float) -> httpx.Response:
        timeouts.append(remaining)
        return httpx.Response(429, headers={"Retry-After": "3"})

    def sleep(seconds: float) -> None:
        elapsed[0] += seconds

    response = retry.request_with_retries(send, deadline_seconds=5, sleep=sleep)
    assert response.status_code == 429
    assert timeouts == [5, 2]
    assert elapsed[0] == 3


def test_streamed_r2_upload_rewinds_for_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib
    from io import BytesIO

    monkeypatch.setattr("time.sleep", lambda _: None)
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.read())
        return httpx.Response(503 if len(bodies) == 1 else 200)

    store = R2BlobStore(
        endpoint_url="https://test",
        bucket_name="test",
        access_key_id="test",
        secret_access_key="test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    content = b"large file body"
    store.put_verified_original(
        stream=BytesIO(content),
        size_bytes=len(content),
        expected_sha256=hashlib.sha256(content).hexdigest(),
        content_type="application/pdf",
        extension="pdf",
    )
    assert bodies == [content, content]


def test_azure_polling_honors_retry_after_and_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elapsed = [0.0]
    delays: list[float] = []
    monkeypatch.setattr("app.ingestion.ocr.perf_counter", lambda: elapsed[0])

    def sleep(seconds: float) -> None:
        delays.append(seconds)
        elapsed[0] += seconds

    monkeypatch.setattr("time.sleep", sleep)
    provider = AzureDocumentIntelligenceOcrProvider(
        endpoint="https://test",
        api_key="test",
        timeout_seconds=3,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"status": "running"}, headers={"Retry-After": "2"}
                )
            )
        ),
    )
    with pytest.raises(httpx.ReadTimeout, match="deadline"):
        provider._poll_operation("https://test/operation")
    assert delays == [2, 1]
