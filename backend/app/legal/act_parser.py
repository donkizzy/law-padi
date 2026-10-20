"""Conservative Act structure parsing; arrangement mismatches require review.

Section numbers always come from body markers. Arrangement entries supply
headings and validation targets, never missing authoritative text or identities.
Roman subclauses remain inside their containing paragraph's exact wording.
"""

import re
from dataclasses import dataclass, field

from app.legal.enums import ProvisionKind
from app.legal.parser import (
    _CHAPTER_RE,
    _PART_RE,
    _SCHEDULE_RE,
    _SECTION_RE,
    ParsedProvision,
    SourcePage,
    _append_section_children,
    _normalize_number,
)

ACT_PARSER_VERSION = "act-hierarchy-v2"
_ARRANGEMENT = re.compile(r"arrangement\s+of\s+(?:sections|provisions)", re.I)
_ENACTMENT = re.compile(r"^[^\w(]*(?:BE\s+IT\s+)?ENACTED\b", re.I)
_BACK_MATTER = re.compile(
    r"^(?:I\s+ASSENT|I\s+certify\s+that\s+this\s+Bill|Schedule\s+to\s+(?:the\s+)?(?:Administration|Nigeria Police).+Bill|Printed\s+and\s+Published)\b",
    re.I,
)
_BARE_SECTION = re.compile(r"^(\d+[a-z]?)\s+(?=\(\d+\))(.+)$", re.I)
_ACT_SECTION = re.compile(r"^[^\w(]*(\d+[a-z]?)\s*(?:[.\-–—]|,(?=\s|\())\s*(.*)$", re.I)
_PLURAL_SCHEDULE = re.compile(r"^SCHEDULES\s*$", re.I)
_NUMBERED_SCHEDULE = re.compile(
    r"^[^\w(]*(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|\d+(?:ST|ND|RD|TH)?)\s+SCHEDULE\b\s*(.*)$",
    re.I,
)
_ARRANGEMENT_ENTRY = re.compile(r"^(\d+[a-z]?)\s*[.\-–—]?\s+([A-Z].+)$", re.I)


def _section_marker(line: str) -> re.Match[str] | None:
    # Accept observed punctuation variants without repairing OCR digits/words.
    return (
        _SECTION_RE.match(line) or _ACT_SECTION.match(line) or _BARE_SECTION.match(line)
    )


@dataclass
class ActParse:
    nodes: list[ParsedProvision]
    arrangement: dict[str, str] = field(default_factory=dict)
    arrangement_pages: list[int] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _lines(pages: list[SourcePage]) -> list[tuple[int, str]]:
    return [
        (page.page_number, line.strip())
        for page in pages
        for line in page.text.splitlines()
        if line.strip()
    ]


def _body_start(lines: list[tuple[int, str]]) -> int:
    enactment = next(
        (i for i, (_page, line) in enumerate(lines) if _ENACTMENT.match(line)), None
    )
    if enactment is not None:
        return enactment + 1
    arrangement = next(
        (i for i, (_page, line) in enumerate(lines) if _ARRANGEMENT.search(line)), None
    )
    if arrangement is None:
        return 0
    for i in range(arrangement + 1, len(lines)):
        match = _section_marker(lines[i][1])
        if match and (
            match.group(2).startswith("(1)")
            or (i + 1 < len(lines) and lines[i + 1][1].startswith("(1)"))
        ):
            # Retain a preceding part heading on the same body page.
            return next(
                (
                    j
                    for j in range(i - 1, arrangement, -1)
                    if lines[j][0] == lines[i][0] and _PART_RE.match(lines[j][1])
                ),
                i,
            )
    return len(lines)


def _arrangement(
    lines: list[tuple[int, str]],
) -> tuple[dict[str, str], list[int], list[str]]:
    titles: dict[str, str] = {}
    pages: set[int] = set()
    issues: list[str] = []
    active = False
    current: str | None = None
    for page, line in lines:
        if _ARRANGEMENT.search(line):
            active = True
            current = None
            continue
        if not active:
            continue
        pages.add(page)
        if (
            _PART_RE.match(line)
            or _CHAPTER_RE.match(line)
            or _ENACTMENT.match(line)
            or _SCHEDULE_RE.match(line)
            or _NUMBERED_SCHEDULE.match(line)
        ):
            current = None
            continue
        match = _section_marker(line) or _ARRANGEMENT_ENTRY.match(line)
        if match and match.group(2).strip():
            current = match.group(1).lower()
            title = match.group(2).strip()
            if current in titles:
                issues.append(f"Arrangement repeats section {current}")
            titles[current] = title
        elif re.fullmatch(r"\d+[a-z]?[.,]?", line, re.I):
            issues.append(f"Unresolved arrangement marker on page {page}: {line}")
            current = None
        elif current:
            titles[current] += " " + line
    return titles, sorted(pages), issues


def parse_act_pages(pages: list[SourcePage], instrument_slug: str) -> ActParse:
    lines = _lines(pages)
    start = _body_start(lines)
    titles, arrangement_pages, issues = _arrangement(lines[:start])
    arrangement_chapters = {
        _normalize_number(match.group(1))
        for _page, line in lines[:start]
        if (match := _CHAPTER_RE.match(line))
    }
    result = ActParse([], titles, arrangement_pages, issues)
    current_chapter: ParsedProvision | None = None
    current_part: ParsedProvision | None = None
    current_schedule: ParsedProvision | None = None
    current: ParsedProvision | None = None
    text_lines: list[str] = []
    seen: set[str] = set()
    ordinal = 0

    def append(node: ParsedProvision) -> ParsedProvision:
        if node.heading and len(node.heading) > 512:
            result.issues.append(
                f"Oversized heading requires review: {node.canonical_path}"
            )
            node.parser_metadata["unresolved_heading"] = node.heading
            node.heading = None
        if node.canonical_path in seen:
            result.issues.append(f"Duplicate provision path: {node.canonical_path}")
            return node
        node.parser_metadata = {
            **node.parser_metadata,
            "parser_version": ACT_PARSER_VERSION,
        }
        seen.add(node.canonical_path)
        result.nodes.append(node)
        return node

    def finish() -> None:
        nonlocal current, text_lines
        if current is not None:
            current.text = "\n".join(text_lines).strip() or None
            current.parser_confidence = 0.9 if current.text else 0.5
            if current.text and current.kind == ProvisionKind.SECTION:
                _append_section_children(current, current.text, append)
        current = None
        text_lines = []

    def structure(
        kind: ProvisionKind, number: str, heading: str | None, page: int
    ) -> ParsedProvision:
        nonlocal ordinal
        ordinal += 1
        parent = (
            current_schedule
            if kind == ProvisionKind.PART and current_schedule
            else current_chapter
            if kind == ProvisionKind.PART
            else None
        )
        prefix = parent.canonical_path if parent else instrument_slug
        return append(
            ParsedProvision(
                kind=kind,
                number=number,
                heading=heading,
                canonical_path=f"{prefix}.{kind.value}{number}",
                sort_key=f"{ordinal:05d}",
                parent_path=parent.canonical_path if parent else None,
                page_start=page,
                page_end=page,
            )
        )

    for index in range(start, len(lines)):
        page, line = lines[index]
        if _BACK_MATTER.match(line):
            finish()
            break
        if _ARRANGEMENT.search(line):
            result.issues.append(
                f"Unexpected arrangement heading in body on page {page}"
            )
        chapter = _CHAPTER_RE.match(line)
        part = _PART_RE.match(line)
        schedule = _SCHEDULE_RE.match(line) or _NUMBERED_SCHEDULE.match(line)
        # A wrapped reference to Chapter IV inside an Act is not a new chapter.
        if (
            chapter
            and current
            and _normalize_number(chapter.group(1)) not in arrangement_chapters
        ):
            chapter = None
        match = chapter or part
        if match and not re.match(
            r"^(?:of|to)\b", " ".join(s or "" for s in match.groups()[1:]), re.I
        ):
            finish()
            number = _normalize_number(match.group(1))
            heading = " ".join(s for s in match.groups()[1:] if s).strip() or None
            if chapter:
                current_chapter = structure(
                    ProvisionKind.CHAPTER, number, heading, page
                )
                current_part = None
                current_schedule = None
            else:
                current_part = structure(ProvisionKind.PART, number, heading, page)
            continue
        if schedule or _PLURAL_SCHEDULE.match(line):
            finish()
            current_chapter = current_part = None
            if schedule is None:
                result.issues.append(
                    f"Unnumbered plural schedule heading on page {page}"
                )
            current_schedule = structure(
                ProvisionKind.SCHEDULE,
                _normalize_number(schedule.group(1) or "1") if schedule else "1",
                schedule.group(2) if schedule else line,
                page,
            )
            # Unnumbered forms, tables and Roman clauses in a schedule are text
            # on the schedule node until an explicit numbered item appears.
            current = current_schedule
            continue
        section = _section_marker(line)
        if section:
            number, rest = section.group(1).lower(), section.group(2).strip()
            parent = current_part or current_schedule or current_chapter
            prefix = parent.canonical_path if parent else instrument_slug
            kind = (
                ProvisionKind.SCHEDULE_ITEM
                if current_schedule
                else ProvisionKind.SECTION
            )
            path = f"{prefix}.{'item' if current_schedule else 'section'}{number}"
            if path in seen:
                result.issues.append(
                    f"Repeated section/item marker on page {page}: {number}"
                )
                if current:
                    text_lines.append(line)
                continue
            finish()
            ordinal += 1
            title = titles.get(number) if not current_schedule else None
            if title and rest.casefold().rstrip(".") == title.casefold().rstrip("."):
                rest = ""
            current = append(
                ParsedProvision(
                    kind=kind,
                    number=number,
                    heading=title,
                    canonical_path=path,
                    sort_key=f"{ordinal:05d}",
                    parent_path=parent.canonical_path if parent else None,
                    page_start=page,
                    page_end=page,
                    parser_metadata={
                        "heading_source": "arrangement" if title else "needs_review"
                    },
                )
            )
            text_lines = [rest] if rest else []
            continue
        if current:
            current.page_end = page
            text_lines.append(line)
        elif current_part and current_part.heading is None:
            # Wrapped part titles precede the first numbered section.
            if len(line) <= 512:
                current_part.heading = line
            else:
                result.issues.append(f"Oversized part heading on page {page}")
                current_part.parser_metadata["unresolved_heading"] = line
    finish()
    return result
