from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.ingestion.extraction import (
    NATIVE_PDF_EXTRACTOR_VERSION,
    NativePdfExtractor,
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


def _pdf_with_pages(texts: list[str]) -> bytes:
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
            f"BT /F1 12 Tf 36 450 Td ({_escape_pdf_text(text)}) Tj ET".encode()
        )
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
