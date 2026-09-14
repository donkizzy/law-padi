import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from app.core.config import settings
from app.ingestion.blob_store import BlobStoreError, LocalBlobStore
from app.legal.enums import ProvisionKind
from app.legal.models import SourceDocument

PARSER_VERSION = "constitution-hierarchy-v2"

_CHAPTER_RE = re.compile(
    r"^CHAPTER\s+([IVXLCDM]+|\d+)\b(?:\s*[-:]\s*(.*)|\s+(.*))?$", re.I
)
_PART_RE = re.compile(
    r"^PART\s+([IVXLCDM]+|\d+|[A-Z])\b(?:\s*[-:]\s*(.*)|\s+(.*))?$", re.I
)
_SECTION_RE = re.compile(r"^(\d+[A-Za-z]?)\s*[\.\-–—]\s*(.*)$")
_SUBSECTION_RE = re.compile(r"(?m)^\s*\((\d+[A-Za-z]?)\)\s+")
_PARAGRAPH_RE = re.compile(r"(?m)^\s*\(([a-z])\)\s+")
_SUBSECTION_LINE_RE = re.compile(r"^\((\d+[A-Za-z]?)\)\s+")
_PARAGRAPH_LINE_RE = re.compile(r"^\(([a-z])\)\s+")
_SCHEDULE_RE = re.compile(
    r"^(?:(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|\d+(?:ST|ND|RD|TH)?)\s+)?SCHEDULE\b(?:\s*[-:]\s*(.*))?$",
    re.I,
)


class ParserError(Exception):
    pass


class NoExtractableTextError(ParserError):
    pass


@dataclass
class SourcePage:
    page_number: int
    text: str


@dataclass
class ParsedProvision:
    kind: ProvisionKind
    number: str | None
    heading: str | None
    canonical_path: str
    sort_key: str
    parent_path: str | None
    page_start: int | None = None
    page_end: int | None = None
    text: str | None = None
    parser_confidence: float | None = None
    parser_metadata: dict[str, Any] = field(default_factory=dict)


def normalize_legal_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def legal_text_sha256(text: str) -> str:
    return hashlib.sha256(normalize_legal_text(text).encode()).hexdigest()


def extract_source_pages(source: SourceDocument) -> list[SourcePage]:
    if not source.storage_key:
        raise ParserError("Source document does not have a stored file")
    if source.mime_type != "application/pdf":
        raise ParserError("V1 ingestion accepts Constitution PDF sources only")

    store = LocalBlobStore(Path(settings.INGESTION_STORAGE_DIR))
    try:
        with store.open_read(source.storage_key) as source_file:
            return _extract_pdf_pages(source_file)
    except BlobStoreError as exc:
        raise ParserError("Source document storage key is invalid") from exc
    except FileNotFoundError:
        raise ParserError("Stored source document file was not found")


def parse_constitution_pages(
    pages: list[SourcePage], instrument_slug: str
) -> list[ParsedProvision]:
    parsed: list[ParsedProvision] = []
    paths_seen: set[str] = set()
    current_chapter: ParsedProvision | None = None
    current_part: ParsedProvision | None = None
    current_schedule: ParsedProvision | None = None
    current_text_node: ParsedProvision | None = None
    current_text_lines: list[str] = []
    schedule_item_count = 0

    def append_node(node: ParsedProvision) -> ParsedProvision:
        if node.canonical_path in paths_seen:
            raise ParserError(
                f"Duplicate provision path detected: {node.canonical_path}"
            )
        paths_seen.add(node.canonical_path)
        parsed.append(node)
        return node

    def finish_text_node() -> None:
        nonlocal current_text_node, current_text_lines
        if not current_text_node:
            return
        text = "\n".join(line for line in current_text_lines if line).strip()
        if not text:
            current_text_node = None
            current_text_lines = []
            return
        current_text_node.text = text
        current_text_node.heading = current_text_node.heading or _heading_from_text(
            text
        )
        current_text_node.parser_confidence = _confidence_for_text(text)
        current_text_node.parser_metadata = {
            **current_text_node.parser_metadata,
            "subsection_count": len(_SUBSECTION_RE.findall(text)),
            "paragraph_count": len(_PARAGRAPH_RE.findall(text)),
            "parser_version": PARSER_VERSION,
        }
        if current_text_node.kind == ProvisionKind.SECTION:
            _append_section_children(current_text_node, text, append_node)
        current_text_node = None
        current_text_lines = []

    for page in pages:
        for raw_line in page.text.splitlines():
            line = _clean_line(raw_line)
            if not line:
                continue

            chapter_match = _CHAPTER_RE.match(line)
            if chapter_match:
                finish_text_node()
                number = _normalize_number(chapter_match.group(1))
                heading = _coalesce_heading(
                    chapter_match.group(2), chapter_match.group(3)
                )
                current_chapter = append_node(
                    ParsedProvision(
                        kind=ProvisionKind.CHAPTER,
                        number=number,
                        heading=heading,
                        canonical_path=f"{instrument_slug}.chapter{number}",
                        sort_key=f"{_sort_number(number):03d}",
                        parent_path=None,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        parser_metadata={"parser_version": PARSER_VERSION},
                    )
                )
                current_part = None
                current_schedule = None
                continue

            part_match = _PART_RE.match(line)
            if part_match and current_schedule is None:
                finish_text_node()
                number = _normalize_number(part_match.group(1))
                heading = _coalesce_heading(part_match.group(2), part_match.group(3))
                parent_path = (
                    current_chapter.canonical_path if current_chapter else None
                )
                prefix = parent_path or instrument_slug
                current_part = append_node(
                    ParsedProvision(
                        kind=ProvisionKind.PART,
                        number=number,
                        heading=heading,
                        canonical_path=f"{prefix}.part{number}",
                        sort_key=f"{current_chapter.sort_key if current_chapter else '000'}.{_sort_number(number):03d}",
                        parent_path=parent_path,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        parser_metadata={"parser_version": PARSER_VERSION},
                    )
                )
                continue

            schedule_match = _SCHEDULE_RE.match(line)
            if schedule_match:
                finish_text_node()
                schedule_item_count = 0
                number = _normalize_number(schedule_match.group(1) or "1")
                heading = _coalesce_heading(schedule_match.group(2))
                current_schedule = append_node(
                    ParsedProvision(
                        kind=ProvisionKind.SCHEDULE,
                        number=number,
                        heading=heading,
                        canonical_path=f"{instrument_slug}.schedule{number}",
                        sort_key=f"900.{_sort_number(number):03d}",
                        parent_path=None,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        parser_metadata={"parser_version": PARSER_VERSION},
                    )
                )
                current_chapter = None
                current_part = None
                continue

            section_match = _SECTION_RE.match(line)
            if section_match:
                finish_text_node()
                number = _normalize_number(section_match.group(1))
                rest = section_match.group(2).strip()
                if current_schedule:
                    schedule_item_count += 1
                    parent_path = current_schedule.canonical_path
                    current_text_node = append_node(
                        ParsedProvision(
                            kind=ProvisionKind.SCHEDULE_ITEM,
                            number=number,
                            heading=_heading_from_text(rest),
                            canonical_path=f"{parent_path}.item{number}",
                            sort_key=f"{current_schedule.sort_key}.{schedule_item_count:04d}",
                            parent_path=parent_path,
                            page_start=page.page_number,
                            page_end=page.page_number,
                            parser_metadata={"parser_version": PARSER_VERSION},
                        )
                    )
                else:
                    parent_path = (
                        current_part.canonical_path
                        if current_part
                        else current_chapter.canonical_path
                        if current_chapter
                        else None
                    )
                    parent_sort = (
                        current_part.sort_key
                        if current_part
                        else current_chapter.sort_key
                        if current_chapter
                        else "000"
                    )
                    prefix = parent_path or instrument_slug
                    current_text_node = append_node(
                        ParsedProvision(
                            kind=ProvisionKind.SECTION,
                            number=number,
                            heading=_heading_from_text(rest),
                            canonical_path=f"{prefix}.section{number.lower()}",
                            sort_key=f"{parent_sort}.{_sort_number(number):04d}",
                            parent_path=parent_path,
                            page_start=page.page_number,
                            page_end=page.page_number,
                            parser_metadata={"parser_version": PARSER_VERSION},
                        )
                    )
                current_text_lines = [rest] if rest else []
                continue

            if current_text_node:
                current_text_node.page_end = page.page_number
                current_text_lines.append(line)

    finish_text_node()
    text_nodes = [node for node in parsed if node.text]
    if not text_nodes:
        raise ParserError("No Constitution sections or schedule items were detected")
    return parsed


def _extract_pdf_pages(path: Path | BinaryIO) -> list[SourcePage]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ParserError("PDF parsing dependency is not installed") from exc

    reader = PdfReader(path)
    pages = [
        SourcePage(page_number=index + 1, text=page.extract_text() or "")
        for index, page in enumerate(reader.pages)
    ]
    if not any(page.text.strip() for page in pages):
        raise NoExtractableTextError(
            "This PDF does not contain extractable text. OCR-only scans are not supported in V1."
        )
    return pages


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\u00a0", " ")).strip()


def _coalesce_heading(*parts: str | None) -> str | None:
    heading = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    return heading or None


def _heading_from_text(text: str) -> str | None:
    heading = re.split(r"(?<=[.;:])\s+", text.strip(), maxsplit=1)[0].strip()
    if not heading:
        return None
    if len(heading) > 120:
        return f"{heading[:117].rstrip()}..."
    return heading


def _confidence_for_text(text: str) -> float:
    if _SUBSECTION_RE.search(text):
        return 0.94
    if len(text.split()) >= 10:
        return 0.9
    return 0.78


def _append_section_children(
    section: ParsedProvision,
    text: str,
    append_node: Any,
) -> None:
    subsection_segments = _marker_segments(text, _SUBSECTION_LINE_RE)
    if subsection_segments:
        for subsection_index, segment in enumerate(subsection_segments, start=1):
            number = _normalize_number(segment.marker)
            subsection = append_node(
                ParsedProvision(
                    kind=ProvisionKind.SUBSECTION,
                    number=number,
                    heading=_heading_from_text(segment.text),
                    canonical_path=f"{section.canonical_path}.subsection{number.lower()}",
                    sort_key=f"{section.sort_key}.{subsection_index:03d}",
                    parent_path=section.canonical_path,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    text=segment.text,
                    parser_confidence=_confidence_for_text(segment.text),
                    parser_metadata={
                        "parser_version": PARSER_VERSION,
                        "paragraph_count": len(_PARAGRAPH_RE.findall(segment.text)),
                    },
                )
            )
            _append_paragraph_children(subsection, segment.text, append_node)
        return

    _append_paragraph_children(section, text, append_node)


def _append_paragraph_children(
    parent: ParsedProvision,
    text: str,
    append_node: Any,
) -> None:
    for paragraph_index, segment in enumerate(
        _marker_segments(text, _PARAGRAPH_LINE_RE), start=1
    ):
        number = segment.marker.lower()
        append_node(
            ParsedProvision(
                kind=ProvisionKind.PARAGRAPH,
                number=number,
                heading=_heading_from_text(segment.text),
                canonical_path=f"{parent.canonical_path}.paragraph{number}",
                sort_key=f"{parent.sort_key}.{paragraph_index:03d}",
                parent_path=parent.canonical_path,
                page_start=parent.page_start,
                page_end=parent.page_end,
                text=segment.text,
                parser_confidence=_confidence_for_text(segment.text),
                parser_metadata={"parser_version": PARSER_VERSION},
            )
        )


@dataclass(frozen=True)
class _MarkerSegment:
    marker: str
    text: str


def _marker_segments(text: str, pattern: re.Pattern[str]) -> list[_MarkerSegment]:
    segments: list[_MarkerSegment] = []
    current_marker: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            if current_marker:
                segments.append(
                    _MarkerSegment(
                        marker=current_marker,
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_marker = match.group(1)
            current_lines = [line.strip()]
            continue
        if current_marker:
            current_lines.append(line.strip())
    if current_marker:
        segments.append(
            _MarkerSegment(
                marker=current_marker,
                text="\n".join(current_lines).strip(),
            )
        )
    return segments


def _normalize_number(value: str) -> str:
    cleaned = value.strip().upper().rstrip(".")
    ordinal = {
        "FIRST": "1",
        "SECOND": "2",
        "THIRD": "3",
        "FOURTH": "4",
        "FIFTH": "5",
        "SIXTH": "6",
        "SEVENTH": "7",
        "EIGHTH": "8",
        "NINTH": "9",
        "TENTH": "10",
    }.get(cleaned)
    if ordinal:
        return ordinal
    cleaned = re.sub(r"(ST|ND|RD|TH)$", "", cleaned)
    if cleaned.isdigit():
        return cleaned
    roman_value = _roman_to_int(cleaned)
    if roman_value is not None:
        return str(roman_value)
    return cleaned.lower()


def _sort_number(value: str) -> int:
    match = re.match(r"(\d+)", value)
    if match:
        return int(match.group(1))
    return sum(ord(char) for char in value)


def _roman_to_int(value: str) -> int | None:
    if not value or not re.fullmatch(r"[IVXLCDM]+", value):
        return None
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for char in reversed(value):
        current = values[char]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total
