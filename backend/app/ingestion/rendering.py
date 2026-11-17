import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class PdfRenderingError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderedPageThumbnail:
    page_number: int
    content: bytes
    content_type: str = "image/png"


def render_page_thumbnail(
    content: bytes | Path,
    *,
    page_number: int,
    scale_to: int = 320,
) -> RenderedPageThumbnail:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise PdfRenderingError(
            "Poppler pdftoppm is required to render page thumbnails"
        )
    if page_number < 1:
        raise PdfRenderingError("Page numbers are one-based")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = content if isinstance(content, Path) else tmp_path / "source.pdf"
        output_prefix = tmp_path / "page"
        if isinstance(content, bytes):
            input_path.write_bytes(content)
        command = [
            pdftoppm,
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-singlefile",
            "-png",
            "-scale-to",
            str(scale_to),
            str(input_path),
            str(output_prefix),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            raise PdfRenderingError("Timed out while rendering PDF page") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise PdfRenderingError(f"PDF page render failed: {detail}")

        output_path = output_prefix.with_suffix(".png")
        if not output_path.exists():
            raise PdfRenderingError("PDF renderer did not produce a PNG thumbnail")
        return RenderedPageThumbnail(
            page_number=page_number,
            content=output_path.read_bytes(),
        )
