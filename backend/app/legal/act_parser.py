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

ACT_PARSER_VERSION = "act-hierarchy-v3"
_ARRANGEMENT = re.compile(r"arrangement\s+of\s+(?:sections|provisions)", re.I)
_ENACTMENT = re.compile(r"^[^\w(]*(?:BE\s+IT\s+)?ENACTED\b", re.I)
_BACK_MATTER = re.compile(
    r"^(?:I\s+ASSENT|I,?\s+certify\b|EXPLANATORY\s+MEMORANDUM\s*$|SUBSIDIARY\s+LEGISLATION\s*$|Schedule\s+to\s+(?:the\s+)?(?:Administration|Nigeria Police).+Bill|Printed\s+and\s+Published)\b",
    re.I,
)
_BARE_SECTION = re.compile(r"^(\d+[a-z]?)\s+(?=\(\d+\))(.+)$", re.I)
_ACT_SECTION = re.compile(r"^[^\w(]*(\d+[a-z]?)\s*(?:[.\-–—]|,(?=\s|\())\s*(.*)$", re.I)
_PLURAL_SCHEDULE = re.compile(r"^SCHEDULES\s*$", re.I)
_REFERENCED_SCHEDULE = re.compile(
    r"^[^\w(]*SCHEDULE\s+((?:Sections?|s\.|ss\.)\s*\S.*)$", re.I
)
_NUMBERED_SCHEDULE = re.compile(
    r"^[^\w(]*(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH?|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|\d+(?:ST|ND|RD|TH)?)\s+SCHEDULE\b\s*(.*)$",
    re.I,
)
_ARRANGEMENT_ENTRY = re.compile(r"^(\d+[a-z]?)\s*[.\-–—]?\s+([A-Z].+)$", re.I)
# Title block after the arrangement: "CHAPTER L5", the long title, bracketed notes.
_TITLE_BLOCK = re.compile(
    r"^(?:CHAPTER\s+[A-Z]*\d+\b|An\s+Act\s+to\b|\[.*|[A-Z][A-Z\s,()&-]{3,}\bACT(?:,?\s+\d{4})?$)",
    re.I,
)


# OCR splits some two-digit numbers ("7 4. Labour required ..."). A split marker
# is only read as a section when the joined number is the next one in sequence.
_SPLIT_NUMBER = re.compile(r"^(\d)\s(\d)[._]*\s+(\S.*)$")
# A text layer may spell the first subsection "(I)" or "(l)" for "(1)".
_FIRST_SUBSECTION = re.compile(r"^\((?:1|I|l)\)")


def _next_in_sequence(line: str, previous: int) -> tuple[str, str] | None:
    """Return (number, rest) when line is a split two-digit number that follows previous."""
    match = _SPLIT_NUMBER.match(line)
    if match and int(match.group(1) + match.group(2)) == previous + 1:
        return match.group(1) + match.group(2), match.group(3)
    return None


def _section_marker(line: str) -> re.Match[str] | None:
    # Accept observed punctuation variants without repairing OCR digits/words.
    return (
        _SECTION_RE.match(line) or _ACT_SECTION.match(line) or _BARE_SECTION.match(line)
    )


def _schedule_heading(line: str) -> tuple[str | None, str | None] | None:
    """Return (ordinal, title) for a real schedule heading, else None.

    Bracketed margin cross-references ("[First Schedule.]"), wrapped sentences
    ("Eighth Schedule to this Act, or") and title-case margin notes ("Schedule")
    are not headings. An unnumbered heading must be written in capitals.
    """
    if line.lstrip().startswith("["):
        return None
    match = _SCHEDULE_RE.match(line) or _NUMBERED_SCHEDULE.match(line)
    if match:
        ordinal, rest = match.group(1), (match.group(2) or "").strip()
        if rest and rest[0].islower():
            return None
        if not ordinal and not line.strip().isupper():
            return None
        return ordinal, rest or None
    referenced = _REFERENCED_SCHEDULE.match(line)
    if referenced and line.strip().split()[0].isupper():
        return None, referenced.group(1).strip()
    return None


@dataclass
class ActParse:
    nodes: list[ParsedProvision]
    arrangement: dict[str, str] = field(default_factory=dict)
    arrangement_pages: list[int] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    stripped_running_lines: int = 0


def _signature(line: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"\d+", "#", line)).casefold()


def _running_signatures(pages: list[SourcePage]) -> set[str]:
    """Signatures of page headers/footers that repeat on many pages.

    Only the first and last line of a page can qualify, and lines that look like
    provision markers never do, so legal wording is not removed.
    """
    counts: dict[str, int] = {}
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        edges = {lines[0], lines[-1]} if lines else set()
        for line in edges:
            if (
                sum(ch.isalpha() for ch in line) < 3
                or line.startswith("(")
                or _section_marker(line)
            ):
                continue
            counts[_signature(line)] = counts.get(_signature(line), 0) + 1
    threshold = max(3, len(pages) // 4)
    return {sig for sig, count in counts.items() if count >= threshold}


def _lines(
    pages: list[SourcePage], running: set[str] | None = None
) -> list[tuple[int, str]]:
    running = running or set()
    result: list[tuple[int, str]] = []
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        for position, line in enumerate(lines):
            at_edge = position in (0, len(lines) - 1)
            if at_edge and running and _signature(line) in running:
                continue
            result.append((page.page_number, line))
    return result


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
            _FIRST_SUBSECTION.match(match.group(2))
            or (i + 1 < len(lines) and _FIRST_SUBSECTION.match(lines[i + 1][1]))
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
    previous = 0
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
            or _schedule_heading(line)
        ):
            current = None
            continue
        match = _section_marker(line) or _ARRANGEMENT_ENTRY.match(line)
        split = None if match else _next_in_sequence(line, previous)
        if split:
            issues.append(
                f"Arrangement entry '{line[:40]}' on page {page} is read as section "
                f"{split[0]}; the source spacing is not retained"
            )
        entry = (match.group(1).lower(), match.group(2)) if match else split
        if entry and entry[1].strip():
            current, title = entry[0], entry[1].strip()
            if current.isdigit():
                previous = int(current)
            if current in titles:
                issues.append(f"Arrangement repeats section {current}")
            titles[current] = title
        elif re.fullmatch(r"\d+[a-z]?[.,]?", line, re.I):
            issues.append(f"Unresolved arrangement marker on page {page}: {line}")
            current = None
        elif current and _TITLE_BLOCK.match(line):
            current = None
        elif current:
            titles[current] += " " + line
    return titles, sorted(pages), issues


def parse_act_pages(pages: list[SourcePage], instrument_slug: str) -> ActParse:
    running = _running_signatures(pages)
    lines = _lines(pages, running)
    start = _body_start(lines)
    titles, arrangement_pages, issues = _arrangement(lines[:start])
    arrangement_chapters = {
        _normalize_number(match.group(1))
        for _page, line in lines[:start]
        if (match := _CHAPTER_RE.match(line))
    }
    result = ActParse(
        [],
        titles,
        arrangement_pages,
        issues,
        stripped_running_lines=sum(len(_lines(pages)) - len(lines) for _ in (0,)),
    )
    current_chapter: ParsedProvision | None = None
    current_part: ParsedProvision | None = None
    current_schedule: ParsedProvision | None = None
    current: ParsedProvision | None = None
    text_lines: list[str] = []
    seen: set[str] = set()
    ordinal = 0
    last_section = 0

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
            # A repeated all-caps Act title just before the back matter is not text.
            while text_lines and _TITLE_BLOCK.match(text_lines[-1]):
                text_lines.pop()
            finish()
            break
        if _ARRANGEMENT.search(line):
            result.issues.append(
                f"Unexpected arrangement heading in body on page {page}"
            )
        chapter = _CHAPTER_RE.match(line)
        part = _PART_RE.match(line)
        schedule = _schedule_heading(line)
        # A wrapped reference to Chapter IV inside an Act is not a new chapter.
        if (
            chapter
            and current
            and _normalize_number(chapter.group(1)) not in arrangement_chapters
        ):
            chapter = None
        match = chapter or part
        match_rest = (
            " ".join(s or "" for s in match.groups()[1:]).strip() if match else ""
        )
        # "Part XII of this Act ..." and "Part V and VI of that Schedule ..." are
        # wrapped sentences, not headings: a heading never starts lowercase.
        if match and not (
            re.match(r"^(?:of|to)\b", match_rest, re.I)
            or (match_rest and match_rest[0].islower())
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
        plural = _PLURAL_SCHEDULE.match(line) and line.strip().isupper()
        if plural and index + 1 < len(lines) and _schedule_heading(lines[index + 1][1]):
            # A "SCHEDULES" title that introduces numbered schedules is not one.
            finish()
            continue
        if schedule or plural:
            finish()
            current_chapter = current_part = None
            if schedule is None:
                result.issues.append(
                    f"Unnumbered plural schedule heading on page {page}"
                )
            label = schedule[0] if schedule else None
            if label and label.upper() == "EIGHT":
                result.issues.append(
                    f'Schedule heading "{line}" on page {page} is read as the '
                    "eighth schedule; the source spelling is retained"
                )
            current_schedule = structure(
                ProvisionKind.SCHEDULE,
                _normalize_number(
                    "EIGHTH" if label and label.upper() == "EIGHT" else label or "1"
                )
                if schedule
                else "1",
                schedule[1] if schedule else line,
                page,
            )
            if schedule:
                current_schedule.parser_metadata["source_heading"] = line
            # Unnumbered forms, tables and Roman clauses in a schedule are text
            # on the schedule node until an explicit numbered item appears.
            current = current_schedule
            continue
        section = _section_marker(line)
        split_section = (
            None
            if section or current_schedule
            else _next_in_sequence(line, last_section)
        )
        if split_section and split_section[0] in titles:
            result.issues.append(
                f"Section marker '{line[:40]}' on page {page} is read as section "
                f"{split_section[0]}; the source spacing is not retained"
            )
            section = _section_marker(f"{split_section[0]}. {split_section[1]}")
        if section:
            number, rest = section.group(1).lower(), section.group(2).strip()
            # "1.—(1)" marks the section number; the dash is not wording.
            rest = re.sub(r"^[—–-]\s*(?=\()", "", rest)
            parent = current_part or current_schedule or current_chapter
            prefix = parent.canonical_path if parent else instrument_slug
            kind = (
                ProvisionKind.SCHEDULE_ITEM
                if current_schedule
                else ProvisionKind.SECTION
            )
            path = f"{prefix}.{'item' if current_schedule else 'section'}{number}"
            numeric = re.match(r"\d+", number)
            if (
                not current_schedule
                and numeric
                and int(numeric.group()) < last_section
                and current
            ):
                # Body sections run in order, so a lower number here is a wrapped
                # cross-reference ("163 (1) (b) of this Act"), kept as text.
                result.issues.append(
                    f"Out-of-sequence section marker {number} on page {page} "
                    f"after section {last_section} kept as text"
                )
                text_lines.append(line)
                continue
            if path in seen:
                result.issues.append(
                    f"Repeated section/item marker on page {page}: {number}"
                )
                if current:
                    text_lines.append(line)
                continue
            finish()
            if not current_schedule and numeric:
                last_section = max(last_section, int(numeric.group()))
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
