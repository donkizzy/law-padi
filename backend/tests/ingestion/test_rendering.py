import shutil
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.ingestion.rendering import PdfRenderingError, render_page_thumbnail


@pytest.mark.skipif(not shutil.which("pdftoppm"), reason="Poppler is not installed")
def test_render_page_thumbnail_outputs_png_bytes() -> None:
    thumbnail = render_page_thumbnail(_pdf_bytes(), page_number=1, scale_to=160)

    assert thumbnail.page_number == 1
    assert thumbnail.content_type == "image/png"
    assert thumbnail.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(thumbnail.content) > 100


def test_render_page_thumbnail_requires_one_based_page_number() -> None:
    with pytest.raises(PdfRenderingError, match="one-based"):
        render_page_thumbnail(_pdf_bytes(), page_number=0)


def _pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=120, height=160)
    writer.write(output)
    return output.getvalue()
