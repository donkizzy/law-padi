import base64
import csv
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, cast

import httpx

from app.ingestion.runtime.retry import request_with_retries, retry_after

LOCAL_OCR_PROVIDER_VERSION = "tesseract-local-v1"
LOCAL_LAYOUT_OCR_PROVIDER_VERSION = "tesseract-local-lines-v2"
GOOGLE_DOCUMENT_AI_PROVIDER_VERSION = "google-document-ai-rest-v1"
AZURE_DOCUMENT_INTELLIGENCE_PROVIDER_VERSION = "azure-document-intelligence-rest-v1"


class OcrError(RuntimeError):
    retryable = False


class ManagedOcrUnavailable(OcrError):
    pass


@dataclass(frozen=True)
class OcrPageInput:
    page_number: int
    image: bytes
    content_type: str


@dataclass(frozen=True)
class OcrWord:
    text: str
    bbox: dict[str, float]
    confidence: float
    reading_order: int


@dataclass(frozen=True)
class OcrPageResult:
    page_number: int
    text: str
    words: list[OcrWord]
    method: str
    provider: str
    provider_version: str
    confidence: float
    timing_ms: float
    cost_usd: float | None
    quality_flags: dict[str, Any]


class LocalOcrProvider(Protocol):
    def extract_page(self, page: OcrPageInput) -> OcrPageResult:
        """Extract OCR text and word coordinates from a rendered page image."""


class ManagedOcrProvider(Protocol):
    def extract_page(self, page: OcrPageInput) -> OcrPageResult:
        """Extract OCR text through a managed OCR provider."""


class TesseractOcrProvider:
    def __init__(
        self,
        *,
        executable: str | None = None,
        language: str = "eng",
        preserve_lines: bool = False,
    ) -> None:
        self.executable = executable or shutil.which("tesseract")
        self.language = language
        self.preserve_lines = preserve_lines

    def extract_page(self, page: OcrPageInput) -> OcrPageResult:
        if not self.executable:
            raise OcrError("Tesseract executable was not found")
        if page.content_type != "image/png":
            raise OcrError("Local OCR currently expects rendered PNG page images")
        started_at = perf_counter()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / f"page-{page.page_number:04d}.png"
            image_path.write_bytes(page.image)
            command = [
                self.executable,
                str(image_path),
                "stdout",
                "-l",
                self.language,
                "--psm",
                "6",
                "tsv",
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired as exc:
                raise OcrError("Timed out while running local OCR") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise OcrError(f"Local OCR failed: {detail}")
        words = _parse_tesseract_tsv(completed.stdout)
        text = (
            _tesseract_line_text(completed.stdout)
            if self.preserve_lines
            else _join_words(words)
        )
        confidence = _average_confidence(words)
        timing_ms = (perf_counter() - started_at) * 1000
        return OcrPageResult(
            page_number=page.page_number,
            text=text,
            words=words,
            method="local_ocr",
            provider="tesseract",
            provider_version=LOCAL_LAYOUT_OCR_PROVIDER_VERSION
            if self.preserve_lines
            else LOCAL_OCR_PROVIDER_VERSION,
            confidence=confidence,
            timing_ms=round(timing_ms, 3),
            cost_usd=0,
            quality_flags={
                "empty_text": not bool(text.strip()),
                "word_count": len(words),
                "low_confidence": confidence < 0.75,
                "requires_managed_ocr": confidence < 0.75,
                "line_boundaries_preserved": self.preserve_lines,
            },
        )


class GoogleDocumentAiOcrProvider:
    def __init__(
        self,
        *,
        processor_name: str | None = None,
        access_token: str | None = None,
        endpoint_url: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = 120,
        cost_per_page_usd: float | None = None,
    ) -> None:
        self.cost_per_page_usd = cost_per_page_usd
        self.timeout_seconds = timeout_seconds
        self.processor_name = processor_name
        self.access_token = access_token
        self.endpoint_url = endpoint_url
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def extract_page(self, page: OcrPageInput) -> OcrPageResult:
        if not self.processor_name:
            raise ManagedOcrUnavailable(
                "Google Document AI processor is not configured"
            )
        if not self.access_token:
            raise ManagedOcrUnavailable(
                "Google Document AI access token is not configured"
            )
        if not page.content_type.startswith("image/"):
            raise OcrError("Google Document AI OCR expects a rendered page image")

        started_at = perf_counter()
        response = request_with_retries(
            lambda remaining: self.client.post(
                self._process_url(),
                timeout=min(self.timeout_seconds, remaining),
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "rawDocument": {
                        "content": base64.b64encode(page.image).decode(),
                        "mimeType": page.content_type,
                    }
                },
            )
        )
        _raise_ocr_http_error(response, "Google Document AI OCR failed")
        document = _document_from_google_response(response.json())
        words = _google_words(document)
        text = str(document.get("text") or _join_words(words)).strip()
        confidence = _average_confidence(words)
        return OcrPageResult(
            page_number=page.page_number,
            text=text,
            words=words,
            method="managed_ocr",
            provider="google_document_ai",
            provider_version=GOOGLE_DOCUMENT_AI_PROVIDER_VERSION,
            confidence=confidence,
            timing_ms=round((perf_counter() - started_at) * 1000, 3),
            cost_usd=self.cost_per_page_usd,
            quality_flags={
                "empty_text": not bool(text),
                "word_count": len(words),
                "low_confidence": confidence < 0.85,
            },
        )

    def _process_url(self) -> str:
        if self.endpoint_url:
            return self.endpoint_url
        location = _google_processor_location(self.processor_name or "")
        return (
            f"https://{location}-documentai.googleapis.com/v1/"
            f"{self.processor_name}:process"
        )


class AzureDocumentIntelligenceOcrProvider:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        model_id: str = "prebuilt-layout",
        api_version: str = "2024-11-30",
        client: httpx.Client | None = None,
        poll_interval_seconds: float = 1,
        timeout_seconds: float = 120,
        cost_per_page_usd: float | None = None,
    ) -> None:
        self.cost_per_page_usd = cost_per_page_usd
        self.timeout_seconds = timeout_seconds
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_id = model_id
        self.api_version = api_version
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.poll_interval_seconds = poll_interval_seconds

    def extract_page(self, page: OcrPageInput) -> OcrPageResult:
        if not self.endpoint:
            raise ManagedOcrUnavailable(
                "Azure Document Intelligence endpoint is not configured"
            )
        if not self.api_key:
            raise ManagedOcrUnavailable(
                "Azure Document Intelligence API key is not configured"
            )
        if not page.content_type.startswith("image/"):
            raise OcrError(
                "Azure Document Intelligence OCR expects a rendered page image"
            )

        started_at = perf_counter()
        response = request_with_retries(
            lambda remaining: self.client.post(
                self._analyze_url(),
                timeout=min(self.timeout_seconds, remaining),
                headers={
                    "Ocp-Apim-Subscription-Key": self.api_key or "",
                    "Content-Type": page.content_type,
                },
                content=page.image,
            )
        )
        _raise_ocr_http_error(response, "Azure Document Intelligence OCR failed")
        operation_url = response.headers.get("Operation-Location")
        if not operation_url:
            raise OcrError("Azure Document Intelligence did not return an operation")

        payload = self._poll_operation(operation_url)
        result = _azure_analyze_result(payload)
        words = _azure_words(result)
        text = str(result.get("content") or _join_words(words)).strip()
        confidence = _average_confidence(words)
        return OcrPageResult(
            page_number=page.page_number,
            text=text,
            words=words,
            method="managed_ocr",
            provider="azure_document_intelligence",
            provider_version=(
                f"{AZURE_DOCUMENT_INTELLIGENCE_PROVIDER_VERSION}:{self.api_version}"
            ),
            confidence=confidence,
            timing_ms=round((perf_counter() - started_at) * 1000, 3),
            cost_usd=self.cost_per_page_usd,
            quality_flags={
                "empty_text": not bool(text),
                "word_count": len(words),
                "low_confidence": confidence < 0.85,
            },
        )

    def _analyze_url(self) -> str:
        endpoint = (self.endpoint or "").rstrip("/")
        return (
            f"{endpoint}/documentintelligence/documentModels/"
            f"{self.model_id}:analyze?api-version={self.api_version}"
        )

    def _poll_operation(self, operation_url: str) -> dict[str, Any]:
        deadline = perf_counter() + self.timeout_seconds
        while True:
            remaining_poll = deadline - perf_counter()
            if remaining_poll <= 0:
                raise httpx.ReadTimeout("Azure OCR operation polling deadline exceeded")
            response = request_with_retries(
                lambda remaining: self.client.get(
                    operation_url,
                    timeout=min(self.timeout_seconds, remaining),
                    headers={"Ocp-Apim-Subscription-Key": self.api_key or ""},
                ),
                deadline_seconds=remaining_poll,
            )
            _raise_ocr_http_error(
                response, "Azure Document Intelligence operation polling failed"
            )
            payload = response.json()
            status = str(payload.get("status") or "").lower()
            if status == "succeeded":
                return cast(dict[str, Any], payload)
            if status in {"failed", "canceled", "cancelled"}:
                raise OcrError(
                    f"Azure Document Intelligence operation ended as {status}"
                )
            delay = retry_after(response)
            delay = self.poll_interval_seconds if delay is None else delay
            if delay:
                import time

                time.sleep(min(delay, max(0, deadline - perf_counter())))


def managed_ocr_provider_from_settings() -> ManagedOcrProvider:
    from app.core.config import settings

    if settings.MANAGED_OCR_PROVIDER == "google_document_ai":
        return GoogleDocumentAiOcrProvider(
            processor_name=settings.GOOGLE_DOCUMENT_AI_PROCESSOR_NAME,
            access_token=settings.GOOGLE_DOCUMENT_AI_ACCESS_TOKEN,
            cost_per_page_usd=_configured_page_cost(
                "GOOGLE_DOCUMENT_AI_COST_PER_PAGE_USD"
            ),
        )
    if settings.MANAGED_OCR_PROVIDER == "azure_document_intelligence":
        return AzureDocumentIntelligenceOcrProvider(
            endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
            api_key=settings.AZURE_DOCUMENT_INTELLIGENCE_KEY,
            model_id=settings.AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID,
            api_version=settings.AZURE_DOCUMENT_INTELLIGENCE_API_VERSION,
            cost_per_page_usd=_configured_page_cost(
                "AZURE_DOCUMENT_INTELLIGENCE_COST_PER_PAGE_USD"
            ),
        )
    raise ManagedOcrUnavailable("Managed OCR provider is disabled")


def _document_from_google_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OcrError("Google Document AI returned a non-object response")
    document = payload.get("document", payload)
    if not isinstance(document, dict):
        raise OcrError("Google Document AI response did not include a document")
    return cast(dict[str, Any], document)


def _google_words(document: dict[str, Any]) -> list[OcrWord]:
    text = str(document.get("text") or "")
    words: list[OcrWord] = []
    for page in _list_values(document.get("pages")):
        for token in _list_values(page.get("tokens")):
            layout = token.get("layout")
            if not isinstance(layout, dict):
                continue
            token_text = _google_anchor_text(text, layout.get("textAnchor"))
            if not token_text:
                continue
            confidence = _parse_normalized_confidence(layout.get("confidence"))
            words.append(
                OcrWord(
                    text=token_text,
                    bbox=_google_bbox(layout),
                    confidence=confidence,
                    reading_order=len(words) + 1,
                )
            )
    return words


def _google_anchor_text(text: str, anchor: Any) -> str:
    if not isinstance(anchor, dict):
        return ""
    chunks: list[str] = []
    for segment in _list_values(anchor.get("textSegments")):
        start = _parse_int(segment.get("startIndex"), default=0)
        end = _parse_int(segment.get("endIndex"), default=start)
        chunks.append(text[start:end])
    return "".join(chunks).strip()


def _google_bbox(layout: dict[str, Any]) -> dict[str, float]:
    bounding_poly = layout.get("boundingPoly")
    if not isinstance(bounding_poly, dict):
        return {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
    points = bounding_poly.get("normalizedVertices") or bounding_poly.get("vertices")
    return _bbox_from_points(points)


def _google_processor_location(processor_name: str) -> str:
    parts = processor_name.split("/")
    try:
        return parts[parts.index("locations") + 1]
    except ValueError, IndexError:
        return "us"


def _azure_analyze_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OcrError("Azure Document Intelligence returned a non-object response")
    result = payload.get("analyzeResult", payload)
    if not isinstance(result, dict):
        raise OcrError("Azure Document Intelligence response omitted analyzeResult")
    return cast(dict[str, Any], result)


def _azure_words(result: dict[str, Any]) -> list[OcrWord]:
    words: list[OcrWord] = []
    for page in _list_values(result.get("pages")):
        for word in _list_values(page.get("words")):
            content = str(word.get("content") or "").strip()
            if not content:
                continue
            words.append(
                OcrWord(
                    text=content,
                    bbox=_bbox_from_points(word.get("polygon")),
                    confidence=_parse_normalized_confidence(word.get("confidence")),
                    reading_order=len(words) + 1,
                )
            )
    return words


def _raise_ocr_http_error(response: httpx.Response, prefix: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text[:500]
        raise OcrError(f"{prefix}: {detail}") from exc


def _bbox_from_points(points: Any) -> dict[str, float]:
    vertices = _point_coordinates(points)
    if not vertices:
        return {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
    x_values = [x for x, _y in vertices]
    y_values = [y for _x, y in vertices]
    return {
        "x0": min(x_values),
        "y0": min(y_values),
        "x1": max(x_values),
        "y1": max(y_values),
    }


def _point_coordinates(points: Any) -> list[tuple[float, float]]:
    if not isinstance(points, list):
        return []
    if points and all(isinstance(point, int | float) for point in points):
        return [
            (float(points[index]), float(points[index + 1]))
            for index in range(0, len(points) - 1, 2)
        ]
    vertices: list[tuple[float, float]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        vertices.append(
            (
                _parse_float_like(point.get("x")),
                _parse_float_like(point.get("y")),
            )
        )
    return vertices


def _list_values(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _parse_normalized_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except TypeError, ValueError:
        return 0
    return max(0, min(confidence, 1))


def _parse_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        return default


def _parse_float_like(value: Any) -> float:
    try:
        return float(value)
    except TypeError, ValueError:
        return 0


def _parse_tesseract_tsv(output: str) -> list[OcrWord]:
    reader = csv.DictReader(StringIO(output), delimiter="\t", quoting=csv.QUOTE_NONE)
    words: list[OcrWord] = []
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        confidence = _parse_confidence(row.get("conf"))
        if confidence < 0:
            continue
        left = _parse_float(row.get("left"))
        top = _parse_float(row.get("top"))
        width = _parse_float(row.get("width"))
        height = _parse_float(row.get("height"))
        words.append(
            OcrWord(
                text=text,
                bbox={
                    "x0": left,
                    "y0": top,
                    "x1": left + width,
                    "y1": top + height,
                },
                confidence=confidence,
                reading_order=len(words) + 1,
            )
        )
    return words


def _tesseract_line_text(output: str) -> str:
    lines: dict[tuple[str | None, ...], list[str]] = {}
    for row in csv.DictReader(StringIO(output), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        if text and _parse_confidence(row.get("conf")) >= 0:
            key = tuple(
                row.get(field)
                for field in ("page_num", "block_num", "par_num", "line_num")
            )
            lines.setdefault(key, []).append(text)
    return "\n".join(" ".join(words) for words in lines.values())


def _join_words(words: list[OcrWord]) -> str:
    return " ".join(word.text for word in words).strip()


def _average_confidence(words: list[OcrWord]) -> float:
    if not words:
        return 0
    return round(sum(word.confidence for word in words) / len(words), 4)


def _parse_confidence(value: str | None) -> float:
    try:
        return float(value or "-1") / 100
    except ValueError:
        return -1


def _parse_float(value: str | None) -> float:
    try:
        return float(value or "0")
    except ValueError:
        return 0


def _configured_page_cost(name: str) -> float | None:
    configured = os.getenv(name)
    if configured is None:
        return None
    price = float(configured)
    if not math.isfinite(price) or price < 0:
        raise ValueError(f"{name} must be a finite non-negative price")
    return price
