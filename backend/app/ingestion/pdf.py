import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pypdf import PdfReader

from app.ingestion.malware import (
    MalwareScanError as MalwareScanError,
)
from app.ingestion.malware import (
    StaticPdfSafetyScanner,
)
from app.legal.enums import PageInclusionStatus, PageRole

PDF_PROFILER_VERSION = "pdf-profile-v1"
_TOC_RE = re.compile(r"(table\s+of\s+contents|contents)", re.I)
_SCHEDULE_RE = re.compile(r"\b(schedule|schedules)\b", re.I)
_LEGAL_BODY_RE = re.compile(
    r"\b(chapter|part|section|sections?)\b|^\s*\d+[A-Za-z]?\s*[\.\-]", re.I | re.M
)


class PdfInspectionError(ValueError):
    pass


@dataclass(frozen=True)
class PdfInspection:
    sha256: str
    size_bytes: int
    page_count: int


@dataclass(frozen=True)
class PageProfile:
    page_number: int
    role: PageRole
    inclusion_status: PageInclusionStatus
    inclusion_reason: str
    text_density: float
    orientation: str
    column_count: int
    image_coverage: float
    width: float
    height: float
    quality_signals: dict[str, Any]
    extracted_text: str


def inspect_pdf_bytes(
    content: bytes,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
    max_pages: int,
) -> PdfInspection:
    if not content.startswith(b"%PDF"):
        raise PdfInspectionError("Uploaded source is not a valid PDF")
    sha256 = hashlib.sha256(content).hexdigest()
    if expected_sha256 and sha256 != expected_sha256:
        raise PdfInspectionError("Uploaded object SHA-256 does not match")
    if expected_size is not None and len(content) != expected_size:
        raise PdfInspectionError("Uploaded object size does not match")

    reader = _reader_for(content)
    page_count = len(reader.pages)
    if page_count == 0:
        raise PdfInspectionError("Uploaded source does not contain any PDF pages")
    if page_count > max_pages:
        raise PdfInspectionError("Source PDFs must contain 1,000 pages or fewer")
    return PdfInspection(sha256=sha256, size_bytes=len(content), page_count=page_count)


def scan_pdf_bytes(content: bytes) -> dict[str, Any]:
    return StaticPdfSafetyScanner().scan(content).to_metrics()


def profile_pdf_pages(content: bytes, *, max_pages: int) -> list[PageProfile]:
    inspect_pdf_bytes(content, max_pages=max_pages)
    reader = _reader_for(content)
    page_texts = [_extract_text(page) for page in reader.pages]
    repeated_headers = _repeated_edge_lines(page_texts, first=True)
    repeated_footers = _repeated_edge_lines(page_texts, first=False)
    page_count = len(reader.pages)

    profiles: list[PageProfile] = []
    for index, page in enumerate(reader.pages):
        page_number = index + 1
        text = page_texts[index]
        clean_text = _clean_text(text)
        width = float(page.mediabox.width or 0)
        height = float(page.mediabox.height or 0)
        rotation_degrees = _page_rotation(page)
        image_count = _image_count(page)
        image_coverage = min(image_count * 0.25, 1.0)
        role = _classify_page_role(
            clean_text,
            page_number=page_number,
            page_count=page_count,
        )
        inclusion_status = (
            PageInclusionStatus.SUGGESTED_INCLUDE
            if role in {PageRole.LEGAL_BODY, PageRole.SCHEDULE}
            else PageInclusionStatus.SUGGESTED_EXCLUDE
        )
        inclusion_reason = _inclusion_reason(role)
        word_count = len(clean_text.split())
        char_count = len(clean_text)
        text_density = _text_density(char_count=char_count, width=width, height=height)
        first_line = _edge_line(clean_text, first=True)
        last_line = _edge_line(clean_text, first=False)
        profiles.append(
            PageProfile(
                page_number=page_number,
                role=role,
                inclusion_status=inclusion_status,
                inclusion_reason=inclusion_reason,
                text_density=text_density,
                orientation=_page_orientation(
                    width=width, height=height, rotation_degrees=rotation_degrees
                ),
                column_count=_estimate_column_count(clean_text, width=width),
                image_coverage=image_coverage,
                width=width,
                height=height,
                quality_signals={
                    "profiler_version": PDF_PROFILER_VERSION,
                    "char_count": char_count,
                    "word_count": word_count,
                    "has_extractable_text": bool(clean_text),
                    "requires_ocr": char_count < 40,
                    "image_count": image_count,
                    "rotation_degrees": rotation_degrees,
                    "repeated_header_detected": first_line in repeated_headers,
                    "repeated_footer_detected": last_line in repeated_footers,
                },
                extracted_text=text,
            )
        )
    return profiles


def _reader_for(content: bytes) -> PdfReader:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise PdfInspectionError("Password-protected PDFs are not supported")
        return reader
    except PdfInspectionError:
        raise
    except Exception:
        raise PdfInspectionError("Uploaded source is corrupt or unreadable")


def _extract_text(page: Any) -> str:
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def _classify_page_role(text: str, *, page_number: int, page_count: int) -> PageRole:
    if _SCHEDULE_RE.search(text):
        return PageRole.SCHEDULE
    if _TOC_RE.search(text) or _looks_like_toc(text):
        return PageRole.TABLE_OF_CONTENTS
    if _LEGAL_BODY_RE.search(text):
        return PageRole.LEGAL_BODY
    if page_number == 1:
        return PageRole.FRONT_MATTER
    if page_number == page_count:
        return PageRole.BACK_MATTER
    return PageRole.LEGAL_BODY


def _looks_like_toc(text: str) -> bool:
    dotted_lines = sum(
        1 for line in text.splitlines() if re.search(r"\.{3,}\s*\d+$", line)
    )
    return dotted_lines >= 3


def _inclusion_reason(role: PageRole) -> str:
    if role == PageRole.FRONT_MATTER:
        return "Suggested exclusion: front matter before the legal body"
    if role == PageRole.TABLE_OF_CONTENTS:
        return "Suggested exclusion: table of contents"
    if role == PageRole.BACK_MATTER:
        return "Suggested exclusion: back matter after the legal body"
    if role == PageRole.SCHEDULE:
        return "Suggested inclusion: schedules are part of the Constitution"
    return "Suggested inclusion: legal body text"


def _text_density(*, char_count: int, width: float, height: float) -> float:
    area = max(width * height, 1.0)
    return round(min(char_count / area * 100.0, 1.0), 4)


def _page_rotation(page: Any) -> int:
    try:
        return int(page.get("/Rotate") or 0) % 360
    except TypeError, ValueError:
        return 0


def _page_orientation(*, width: float, height: float, rotation_degrees: int) -> str:
    base_orientation = "landscape" if width > height else "portrait"
    if rotation_degrees:
        return f"{base_orientation}_rotated_{rotation_degrees}"
    return base_orientation


def _estimate_column_count(text: str, *, width: float) -> int:
    long_lines = [line for line in text.splitlines() if len(line) > 80]
    if width >= 700 and len(long_lines) >= 4:
        return 2
    return 1


def _image_count(page: Any) -> int:
    resources = page.get("/Resources") or {}
    xobjects = resources.get("/XObject")
    if not xobjects:
        return 0
    try:
        xobjects = xobjects.get_object()
    except AttributeError:
        pass
    count = 0
    for item in xobjects.values():
        try:
            obj = item.get_object()
        except AttributeError:
            obj = item
        if obj.get("/Subtype") == "/Image":
            count += 1
    return count


def _repeated_edge_lines(texts: list[str], *, first: bool) -> set[str]:
    lines = [_edge_line(_clean_text(text), first=first) for text in texts]
    return {
        line
        for line, count in Counter(line for line in lines if len(line) >= 5).items()
        if count > 1
    }


def _edge_line(text: str, *, first: bool) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[0] if first else lines[-1]


def _clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()
