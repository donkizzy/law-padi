from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.ingestion.extraction import (
    NATIVE_PDF_EXTRACTOR_VERSION,
    NativePdfExtractor,
    _page_text_with_layout,
)


def test_native_pdf_extractor_preserves_text_and_source_coordinates() -> None:
    extraction = NativePdfExtractor().extract(
        _pdf_with_pages(
            [
                "1. Supremacy of the Constitution",
                "37. Right to private and family life",
            ]
        ),
        included_pages={2},
    )

    assert len(extraction) == 1
    page = extraction[0]
    assert page.page_number == 2
    assert page.method == "native_pdf"
    assert page.provider_version == NATIVE_PDF_EXTRACTOR_VERSION
    assert "Right to private and family life" in page.text
    assert page.confidence == 0.96
    assert page.quality_flags["span_count"] >= 1

    span = page.spans[0]
    assert span.page_number == 2
    assert span.reading_order == 1
    assert "Right to private" in span.text
    assert span.bbox["x1"] > span.bbox["x0"]
    assert span.bbox["y1"] > span.bbox["y0"]


def test_layout_rejoins_fragments_without_changing_source_characters() -> None:
    class Page:
        def extract_text(self, **_kwargs: object) -> str:
            return "13. Each Secretariat shall submit on 31st March."

    text, flags = _page_text_with_layout(
        Page(), "13. Each Secretariat shall su bmit on 31 st March."
    )
    assert "submit on 31st" in text
    assert flags["layout_content_verified"] is True


def test_layout_cannot_add_missing_letters_or_drop_punctuation() -> None:
    class Page:
        def extract_text(self, **_kwargs: object) -> str:
            return "submit to the Minister"

    original = "su bmit t the Minister;"
    text, flags = _page_text_with_layout(Page(), original)
    assert text == original
    assert flags["layout_content_mismatch"] is True


def test_layout_failure_preserves_plain_text() -> None:
    class Page:
        def extract_text(self, **_kwargs: object) -> str:
            raise ValueError("Unsupported layout")

    text, flags = _page_text_with_layout(Page(), "original text")
    assert text == "original text"
    assert flags["layout_failed"] is True


def test_native_extraction_keeps_superscript_with_its_number() -> None:
    extraction = NativePdfExtractor().extract(
        _pdf_with_pages(
            ["unused"],
            operations=(
                "BT /F1 12 Tf 1 0 0 1 36 450 Tm (31) Tj "
                "/F1 7 Tf 1 0 0 1 50 454 Tm (st) Tj "
                "/F1 12 Tf 1 0 0 1 60 450 Tm ( March) Tj ET"
            ),
        )
    )[0]
    assert "".join(extraction.text.split()) == "31stMarch"
    assert extraction.spans[0].text == "31"
    assert extraction.spans[1].text.strip() == "st"
    assert extraction.plain_text


def _pdf_with_pages(texts: list[str], *, operations: str | None = None) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=500)
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
        content._data = (
            operations or f"BT /F1 12 Tf 36 450 Td ({_escape_pdf_text(text)}) Tj ET"
        ).encode()
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
