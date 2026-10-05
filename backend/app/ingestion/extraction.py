from dataclasses import dataclass
from io import BytesIO
from time import perf_counter
from typing import Any, Protocol

from pypdf import PdfReader

NATIVE_PDF_EXTRACTOR_VERSION = "pypdf-native-layout-v2"


class NativeExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextSpan:
    page_number: int
    text: str
    bbox: dict[str, float]
    reading_order: int


@dataclass(frozen=True)
class PageExtraction:
    page_number: int
    text: str
    spans: list[TextSpan]
    method: str
    provider_version: str
    confidence: float
    timing_ms: float
    quality_flags: dict[str, Any]
    plain_text: str = ""


class PdfExtractor(Protocol):
    def extract(
        self, content: bytes, *, included_pages: set[int] | None = None
    ) -> list[PageExtraction]:
        """Extract page text and coordinate spans from a PDF."""


class NativePdfExtractor:
    def extract(
        self, content: bytes, *, included_pages: set[int] | None = None
    ) -> list[PageExtraction]:
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise NativeExtractionError("Password-protected PDFs are not supported")
        except NativeExtractionError:
            raise
        except Exception as exc:
            raise NativeExtractionError(
                "PDF could not be opened for extraction"
            ) from exc

        extractions: list[PageExtraction] = []
        for index, page in enumerate(reader.pages):
            page_number = index + 1
            if included_pages is not None and page_number not in included_pages:
                continue
            started_at = perf_counter()
            spans: list[TextSpan] = []
            try:
                extracted_text = (
                    page.extract_text(
                        visitor_text=_text_span_visitor(
                            page_number=page_number,
                            spans=spans,
                        )
                    )
                    or ""
                )
            except Exception as exc:
                raise NativeExtractionError(
                    f"PDF page {page_number} text extraction failed"
                ) from exc
            # Visitors expose PDF fragments, not lines. Sorting them by y can
            # move raised ordinal suffixes ahead of their numbers. Preserve
            # stream order for evidence and let the layout engine reconstruct
            # page text separately.
            ordered_spans = [
                TextSpan(
                    page_number=span.page_number,
                    text=span.text,
                    bbox=span.bbox,
                    reading_order=index + 1,
                )
                for index, span in enumerate(spans)
            ]
            text, layout_flags = _page_text_with_layout(page, extracted_text)
            timing_ms = (perf_counter() - started_at) * 1000
            extractions.append(
                PageExtraction(
                    page_number=page_number,
                    text=text,
                    spans=ordered_spans,
                    method="native_pdf",
                    provider_version=NATIVE_PDF_EXTRACTOR_VERSION,
                    confidence=0.96 if text.strip() else 0.0,
                    timing_ms=round(timing_ms, 3),
                    quality_flags={
                        "span_count": len(ordered_spans),
                        "empty_text": not bool(text.strip()),
                        "needs_ocr": not bool(text.strip()),
                        **layout_flags,
                    },
                    plain_text=extracted_text,
                )
            )
        return extractions


def _page_text_with_layout(page: Any, plain_text: str) -> tuple[str, dict[str, Any]]:
    """Accept layout repair only when every non-whitespace character agrees.

    This allows joining split glyphs and superscripts without guessing words,
    adding punctuation, or dropping/reordering source content. Uncertain pages
    retain the plain extraction and an explicit diagnostic.
    """
    try:
        layout_text = (
            page.extract_text(
                extraction_mode="layout", layout_mode_space_vertically=False
            )
            or ""
        )
    except Exception:
        return plain_text, {"text_strategy": "plain", "layout_failed": True}
    agrees = "".join(layout_text.split()) == "".join(plain_text.split())
    if agrees:
        return layout_text, {"text_strategy": "layout", "layout_content_verified": True}
    return plain_text, {
        "text_strategy": "plain",
        "layout_content_verified": False,
        "layout_content_mismatch": True,
    }


def _text_span_visitor(*, page_number: int, spans: list[TextSpan]) -> Any:
    def visitor(
        text: str,
        _current_matrix: Any,
        text_matrix: Any,
        _font_dictionary: Any,
        font_size: float,
    ) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        x = float(text_matrix[4])
        y = float(text_matrix[5])
        width = max(len(cleaned) * float(font_size) * 0.45, 1.0)
        height = max(float(font_size), 1.0)
        spans.append(
            TextSpan(
                page_number=page_number,
                text=cleaned,
                bbox={
                    "x0": round(x, 3),
                    "y0": round(y, 3),
                    "x1": round(x + width, 3),
                    "y1": round(y + height, 3),
                },
                reading_order=len(spans) + 1,
            )
        )

    return visitor
