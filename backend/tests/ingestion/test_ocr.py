import json
import os
import shutil
from functools import partial

import httpx
import pytest

from app.core.config import settings
from app.ingestion.ocr import (
    AzureDocumentIntelligenceOcrProvider,
    GoogleDocumentAiOcrProvider,
    ManagedOcrUnavailable,
    OcrError,
    OcrPageInput,
    TesseractOcrProvider,
    _tesseract_line_text,
    managed_ocr_provider_from_settings,
)
from app.ingestion.rendering import render_page_thumbnail
from tests.factories.pdf import pdf_with_text

_pdf_with_text = partial(pdf_with_text, height=120, font_size=18, x=24, y=70)


def test_act_ocr_keeps_line_and_block_boundaries_including_quotes() -> None:
    tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    for block, line, word, value in [
        (1, 1, 1, "9."),
        (1, 1, 2, '"Search"'),
        (1, 2, 1, "(1)"),
        (1, 2, 2, "Synthetic"),
        (2, 1, 1, "10."),
        (2, 1, 2, "Inventory"),
    ]:
        tsv += f"5\t1\t{block}\t1\t{line}\t{word}\t10\t10\t10\t10\t95\t{value}\n"
    assert _tesseract_line_text(tsv) == '9. "Search"\n(1) Synthetic\n10. Inventory'


def test_tesseract_ocr_provider_extracts_text_confidence_and_coordinates() -> None:
    if not shutil.which("tesseract") or not shutil.which("pdftoppm"):
        reason = "Required OCR/rendering tools missing: tesseract, pdftoppm"
        if os.environ.get("CI"):
            pytest.fail(reason)
        pytest.skip(reason)
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


def test_managed_ocr_records_configured_per_page_price() -> None:
    provider = GoogleDocumentAiOcrProvider(
        processor_name="test",
        access_token="test",
        endpoint_url="https://ocr.test/process",
        cost_per_page_usd=0.0015,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"document": {"text": "hello", "pages": []}}
                )
            )
        ),
    )
    result = provider.extract_page(OcrPageInput(1, b"png", "image/png"))
    assert result.cost_usd == 0.0015
