import os
import shutil
from functools import partial

import pytest

from app.ingestion.rendering import PdfRenderingError, render_page_thumbnail
from tests.factories.pdf import pdf_bytes

_pdf_bytes = partial(pdf_bytes, width=120, height=160)


def test_render_page_thumbnail_outputs_png_bytes() -> None:
    if not shutil.which("pdftoppm"):
        reason = "Required OCR/rendering tools missing: pdftoppm"
        if os.environ.get("CI"):
            pytest.fail(reason)
        pytest.skip(reason)
    thumbnail = render_page_thumbnail(_pdf_bytes(), page_number=1, scale_to=160)

    assert thumbnail.page_number == 1
    assert thumbnail.content_type == "image/png"
    assert thumbnail.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(thumbnail.content) > 100


def test_render_page_thumbnail_requires_one_based_page_number() -> None:
    with pytest.raises(PdfRenderingError, match="one-based"):
        render_page_thumbnail(_pdf_bytes(), page_number=0)
