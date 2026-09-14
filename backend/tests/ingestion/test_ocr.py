import json
import shutil
from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.core.config import settings
from app.ingestion.ocr import (
    AzureDocumentIntelligenceOcrProvider,
    GoogleDocumentAiOcrProvider,
    ManagedOcrUnavailable,
    OcrError,
    OcrPageInput,
    TesseractOcrProvider,
    managed_ocr_provider_from_settings,
)
from app.ingestion.rendering import render_page_thumbnail


@pytest.mark.skipif(
    not shutil.which("tesseract") or not shutil.which("pdftoppm"),
    reason="Tesseract and Poppler are required for local OCR",
)
def test_tesseract_ocr_provider_extracts_text_confidence_and_coordinates() -> None:
    thumbnail = render_page_thumbnail(
        _pdf_with_text("37. Right to private and family life"),
        page_number=1,
        scale_to=1800,
    )

    result = TesseractOcrProvider().extract_page(
        OcrPageInput(
            page_number=1,
            image=thumbnail.content,
            content_type=thumbnail.content_type,
        )
    )

    assert result.page_number == 1
    assert result.method == "local_ocr"
    assert result.provider == "tesseract"
    assert result.cost_usd == 0
    assert result.confidence > 0
    assert "right" in result.text.lower()
    assert result.words
    assert result.words[0].bbox["x1"] > result.words[0].bbox["x0"]
    assert result.quality_flags["word_count"] == len(result.words)


def test_tesseract_ocr_provider_requires_png_input() -> None:
    with pytest.raises(OcrError, match="PNG"):
        TesseractOcrProvider(executable="/bin/echo").extract_page(
            OcrPageInput(
                page_number=1,
                image=b"not-a-png",
                content_type="application/octet-stream",
            )
        )


def test_managed_ocr_adapters_fail_closed_without_configuration() -> None:
    page = OcrPageInput(
        page_number=1, image=b"\x89PNG\r\n\x1a\n", content_type="image/png"
    )

    with pytest.raises(ManagedOcrUnavailable, match="Google Document AI"):
        GoogleDocumentAiOcrProvider().extract_page(page)
    with pytest.raises(ManagedOcrUnavailable, match="Azure Document Intelligence"):
        AzureDocumentIntelligenceOcrProvider().extract_page(page)


def test_google_document_ai_provider_maps_rest_response() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert body["rawDocument"]["mimeType"] == "image/png"
        assert body["rawDocument"]["content"]
        return httpx.Response(
            200,
            json={
                "document": {
                    "text": "37. Right",
                    "pages": [
                        {
                            "pageNumber": 1,
                            "tokens": [
                                {
                                    "layout": {
                                        "textAnchor": {
                                            "textSegments": [
                                                {"startIndex": "0", "endIndex": "3"}
                                            ]
                                        },
                                        "confidence": 0.97,
                                        "boundingPoly": {
                                            "normalizedVertices": [
                                                {"x": 0.1, "y": 0.2},
                                                {"x": 0.3, "y": 0.2},
                                                {"x": 0.3, "y": 0.4},
                                                {"x": 0.1, "y": 0.4},
                                            ]
                                        },
                                    }
                                },
                                {
                                    "layout": {
                                        "textAnchor": {
                                            "textSegments": [
                                                {"startIndex": "4", "endIndex": "9"}
                                            ]
                                        },
                                        "confidence": 0.93,
                                        "boundingPoly": {
                                            "normalizedVertices": [
                                                {"x": 0.35, "y": 0.2},
                                                {"x": 0.6, "y": 0.2},
                                                {"x": 0.6, "y": 0.4},
                                                {"x": 0.35, "y": 0.4},
                                            ]
                                        },
                                    }
                                },
                            ],
                        }
                    ],
                }
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = GoogleDocumentAiOcrProvider(
            processor_name="projects/p/locations/eu/processors/proc",
            access_token="token",
            client=client,
        ).extract_page(
            OcrPageInput(page_number=7, image=b"png-bytes", content_type="image/png")
        )

    assert str(requests[0].url) == (
        "https://eu-documentai.googleapis.com/v1/"
        "projects/p/locations/eu/processors/proc:process"
    )
    assert requests[0].headers["authorization"] == "Bearer token"
    assert result.page_number == 7
    assert result.method == "managed_ocr"
    assert result.provider == "google_document_ai"
    assert result.text == "37. Right"
    assert [word.text for word in result.words] == ["37.", "Right"]
    assert result.confidence == 0.95
    assert result.words[0].bbox == {"x0": 0.1, "y0": 0.2, "x1": 0.3, "y1": 0.4}


def test_azure_document_intelligence_provider_maps_polling_response() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert request.content == b"png-bytes"
            return httpx.Response(
                202,
                headers={"Operation-Location": "https://azure.test/operations/1"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "analyzeResult": {
                    "content": "37. Right",
                    "pages": [
                        {
                            "pageNumber": 1,
                            "words": [
                                {
                                    "content": "37.",
                                    "confidence": 0.98,
                                    "polygon": [1, 2, 3, 2, 3, 4, 1, 4],
                                },
                                {
                                    "content": "Right",
                                    "confidence": 0.92,
                                    "polygon": [4, 2, 8, 2, 8, 4, 4, 4],
                                },
                            ],
                        }
                    ],
                },
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = AzureDocumentIntelligenceOcrProvider(
            endpoint="https://azure.test",
            api_key="key",
            client=client,
            poll_interval_seconds=0,
        ).extract_page(
            OcrPageInput(page_number=9, image=b"png-bytes", content_type="image/png")
        )

    assert str(requests[0].url) == (
        "https://azure.test/documentintelligence/documentModels/"
        "prebuilt-layout:analyze?api-version=2024-11-30"
    )
    assert requests[0].headers["ocp-apim-subscription-key"] == "key"
    assert str(requests[1].url) == "https://azure.test/operations/1"
    assert result.page_number == 9
    assert result.method == "managed_ocr"
    assert result.provider == "azure_document_intelligence"
    assert result.text == "37. Right"
    assert [word.text for word in result.words] == ["37.", "Right"]
    assert result.confidence == 0.95
    assert result.words[1].bbox == {"x0": 4.0, "y0": 2.0, "x1": 8.0, "y1": 4.0}


def test_managed_ocr_provider_from_settings_selects_configured_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MANAGED_OCR_PROVIDER", "azure_document_intelligence")
    monkeypatch.setattr(
        settings, "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://azure.test"
    )
    monkeypatch.setattr(settings, "AZURE_DOCUMENT_INTELLIGENCE_KEY", "key")

    provider = managed_ocr_provider_from_settings()

    assert isinstance(provider, AzureDocumentIntelligenceOcrProvider)


def _pdf_with_text(text: str) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=120)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )
    content = StreamObject()
    content._data = f"BT /F1 18 Tf 24 70 Td ({_escape_pdf_text(text)}) Tj ET".encode()
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
