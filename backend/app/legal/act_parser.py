"""Conservative Act structure parsing; arrangement mismatches require review.

Section numbers always come from body markers. Arrangement entries supply
headings and validation targets, never missing authoritative text or identities.
Roman subclauses remain inside their containing paragraph's exact wording.
"""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

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
_ENACTMENT = re.compile(r"^[^\w(]*(?:BE\s+IT\s+)?EN[AE]CTED\b", re.I)
_BACK_MATTER = re.compile(
    r"^(?:I\s+ASSENT|I,?\s+certify\b|EXPLANATORY\s+MEMORANDUM\s*$|SUBSIDIARY\s+LEGISLATION\s*$|Schedule\s+to\s+(?:the\s+)?(?:Administration|Nigeria Police).+Bill|Printed\s+and\s+Published)\b",
    re.I,
)
_BARE_SECTION = re.compile(r"^(\d+[a-z]?)\s+(?=\(\d+\))(.+)$", re.I)
_ACT_SECTION = re.compile(r"^[^\w(]*(\d+[a-z]?)\s*(?:[.\-–—]|,(?=\s|\())\s*(.*)$", re.I)
_PLURAL_SCHEDULE = re.compile(
    r"^SCHEDULES(?:\s+(?:Sections?|s\.|ss\.)\s*\S.*)?\s*$", re.I
)
_REFERENCED_SCHEDULE = re.compile(
    r"^[^\w(]*SCHEDULE\s+((?:Sections?|s\.|ss\.)\s*\S.*)$", re.I
)
_NUMBERED_SCHEDULE = re.compile(
    r"^[^\w(]*(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH?|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|\d+(?:ST|ND|RD|TH)?)\s+S\s?CHEDULE\b\s*(.*)$",
    re.I,
)
_OUTLINE_ITEM = re.compile(r"^\d+(?:\.\d+)+\.?\s")
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


_PREAMBLE = re.compile(r"^PREAMBLE$", re.I)
_ORDER_HEADING = re.compile(r"^ORDER\s+([IVXL]+)\s*[—–_-]", re.I)
_APPENDIX = re.compile(r"^APPENDIX$", re.I)
_APPENDIX_PART = re.compile(r"^([AB])\.\s+(SCHEDULE OF FEES|FORMS)$", re.I)
_FORM_HEADING = re.compile(r"^FORM NO\.\s*(\d+)$", re.I)
_STOP_RULES = re.compile(r"^MADE at\b", re.I)


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
        # A wrapped "First Schedule." ending a sentence is a reference.
        if rest and not any(c.isalnum() for c in rest) and not line.strip().isupper():
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
    # The heading can be extracted after its entries on a page (separate text block).
    heading_page = next(
        (page for page, line in lines if _ARRANGEMENT.search(line)), None
    )
    for page, line in lines:
        if page == heading_page:
            active = True
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


_CODE_SECTION = re.compile(r"^[^\w(]*l?(\d+(?:\s?[A-Z]{1,2}(?=\s*\.))?)\s*\.?\s*(.*)$")
_CODE_CHAPTER = re.compile(r"^CHAPTER\s+(\d+[A-Z]?|[IVXL]+)\s*$")
_CODE_PART = re.compile(r"^PART\s+\d+\s*$")


def parse_scheduled_code_pages(
    pages: list[SourcePage], instrument_slug: str, code: dict[str, Any]
) -> ActParse:
    """Parse an Act whose real content is a Code set out in its Schedule.

    The Code's provisions are the sections people cite, so they stay plain
    sections. The enabling Act numbers its own sections 1 to 7, so they are held
    as items of a separate schedule to keep "section 2" unambiguous. A marker only
    counts when it is the next label in the reviewed arrangement catalogue; any
    other numbered line is wording.
    """
    # A corrected historical edition needs its own provision identity.
    instrument_slug = code.get("path_root", instrument_slug)
    enabling: dict[str, str] = code["enabling_titles"]
    titles: dict[str, str] = code["sections"]
    chapters: dict[str, str] = code["chapters"]
    parts: dict[str, str] = code["parts"]
    part_at_chapter = {
        chapter: part for part, chapter in code["part_first_chapter"].items()
    }
    lines = _lines(pages, _running_signatures(pages))
    result = ActParse([], dict(titles))
    seen: set[str] = set()
    order = list(enabling)
    position = 0
    in_code = False
    current: ParsedProvision | None = None
    text_lines: list[str] = []
    ordinal = 0
    current_part: ParsedProvision | None = None
    current_chapter: ParsedProvision | None = None

    def append(node: ParsedProvision) -> ParsedProvision:
        node.parser_metadata = {
            **node.parser_metadata,
            "parser_version": ACT_PARSER_VERSION,
        }
        if node.canonical_path in seen:
            result.issues.append(f"Duplicate provision path: {node.canonical_path}")
            return node
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

    def next_ordinal() -> str:
        nonlocal ordinal
        ordinal += 1
        return f"{ordinal:05d}"

    page = pages[0].page_number if pages else 1
    enabling_schedule = append(
        ParsedProvision(
            kind=ProvisionKind.SCHEDULE,
            number="Act",
            heading=code["enabling_heading"],
            canonical_path=f"{instrument_slug}.scheduleact",
            sort_key=next_ordinal(),
            parent_path=None,
            page_start=page,
            page_end=page,
        )
    )
    queue = deque(lines)
    while queue:
        page, line = queue.popleft()
        upcoming = order[position] if position < len(order) else None
        if upcoming:
            # The text layer can run the next section's heading into the last line.
            title = (titles if in_code else enabling)[upcoming]
            spelled = re.sub(r"^1", "(?:1|l)", re.escape(upcoming))
            inline = re.search(
                rf" {spelled}\.? {re.escape(title.split()[0])}", line, re.I
            )
            if inline:
                queue.appendleft((page, line[inline.start() + 1 :]))
                line = line[: inline.start()]
        if not in_code and line == "SCHEDULE":
            finish()
            in_code = True
            order = list(titles)
            position = 0
            continue
        if in_code and line.startswith(code["stop_line"]):
            finish()
            break
        if in_code and _CODE_PART.match(line):
            finish()
            continue
        chapter = _CODE_CHAPTER.match(line) if in_code else None
        if chapter and chapter.group(1) in chapters:
            finish()
            number = chapter.group(1)
            if current_chapter is not None and current_chapter.number == number:
                continue  # the printed heading is repeated across a page break
            if number in part_at_chapter:
                part_number = part_at_chapter[number]
                current_part = append(
                    ParsedProvision(
                        kind=ProvisionKind.PART,
                        number=part_number,
                        heading=parts[part_number],
                        canonical_path=f"{instrument_slug}.part{part_number}",
                        sort_key=next_ordinal(),
                        parent_path=None,
                        page_start=page,
                        page_end=page,
                    )
                )
            parent = current_part
            prefix = parent.canonical_path if parent else instrument_slug
            current_chapter = append(
                ParsedProvision(
                    kind=ProvisionKind.CHAPTER,
                    number=number,
                    heading=chapters[number],
                    canonical_path=f"{prefix}.chapter{number.lower()}",
                    sort_key=next_ordinal(),
                    parent_path=parent.canonical_path if parent else None,
                    page_start=page,
                    page_end=page,
                )
            )
            continue
        marker = _CODE_SECTION.match(line)
        expected = order[position] if position < len(order) else None
        label = marker.group(1).replace(" ", "") if marker else None
        if line.startswith("l") and label:
            label = "1" + label
        if marker and label is not None and label == expected:
            finish()
            position += 1
            number, rest = label, marker.group(2).strip()
            parent = current_chapter if in_code else enabling_schedule
            assert parent is not None
            title = (titles if in_code else enabling)[number]
            if rest.casefold().rstrip(".") == title.casefold().rstrip("."):
                rest = ""
            suffix = "section" if in_code else "item"
            current = append(
                ParsedProvision(
                    kind=ProvisionKind.SECTION
                    if in_code
                    else ProvisionKind.SCHEDULE_ITEM,
                    number=number,
                    heading=title,
                    canonical_path=f"{parent.canonical_path}.{suffix}{number.lower()}",
                    sort_key=next_ordinal(),
                    parent_path=parent.canonical_path,
                    page_start=page,
                    page_end=page,
                    parser_metadata={
                        "heading_source": "source_arrangement_catalogue",
                        **(
                            {"printed_marker": line[:20]}
                            if line.startswith("l")
                            else {}
                        ),
                    },
                )
            )
            text_lines = [rest] if rest else []
            continue
        if current:
            current.page_end = page
            text_lines.append(line)
    finish()
    return result


def parse_order_rules_pages(
    pages: list[SourcePage], instrument_slug: str, catalogue: dict[str, Any]
) -> ActParse:
    """Parse court rules laid out as Orders and Rules with a lettered Appendix.

    Rule numbers restart in each Order, so a rule's number carries its Order
    ("II.3") to stay unique. As with reviewed Acts, a numbered line only opens a
    rule when it is the next label in the catalogue; any other is wording. An
    Order without numbered rules holds one rule labelled by the Order alone.
    """
    titles: dict[str, str] = catalogue["sections"]
    orders: dict[str, str] = catalogue["parts"]
    forms: dict[str, str] = catalogue["forms"]
    # "FORM NO. 2" tops each form's page, so it must not read as a running header.
    lines = _lines(pages)
    # The arrangement also lists "Preamble"; the Rules start at the last one.
    starts = [i for i, (_, line) in enumerate(lines) if _PREAMBLE.match(line)]
    lines = lines[starts[-1] :] if starts else []
    result = ActParse([], dict(titles))
    seen: set[str] = set()
    current: ParsedProvision | None = None
    part: ParsedProvision | None = None
    schedule: ParsedProvision | None = None
    prefix = ""
    text_lines: list[str] = []
    ordinal = 0
    pending = list(titles)

    def append(node: ParsedProvision) -> ParsedProvision:
        node.parser_metadata = {
            **node.parser_metadata,
            "parser_version": ACT_PARSER_VERSION,
        }
        if node.canonical_path in seen:
            result.issues.append(f"Duplicate provision path: {node.canonical_path}")
            return node
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

    def node(kind: ProvisionKind, **fields: Any) -> ParsedProvision:
        nonlocal ordinal
        ordinal += 1
        return append(
            ParsedProvision(
                kind=kind,
                sort_key=f"{ordinal:05d}",
                page_end=fields["page_start"],
                **fields,
            )
        )

    def open_rule(label: str, rule: str, page: int) -> None:
        nonlocal current
        assert part is not None
        pending.remove(label)
        current = node(
            ProvisionKind.SECTION,
            number=label,
            heading=titles[label] or None,
            canonical_path=f"{part.canonical_path}.rule{rule}",
            parent_path=part.canonical_path,
            page_start=page,
            parser_metadata={"heading_source": "source_arrangement_catalogue"},
        )

    for page, line in lines:
        if _STOP_RULES.match(line):
            break
        if _PREAMBLE.match(line) and part is None:
            prefix = "Preamble"
            part = node(
                ProvisionKind.PART,
                number=None,
                heading="Preamble",
                canonical_path=f"{instrument_slug}.preamble",
                parent_path=None,
                page_start=page,
            )
            continue
        if part is None:
            continue
        if (order := _ORDER_HEADING.match(line)) and order.group(1).upper() in orders:
            finish()
            prefix = order.group(1).upper()
            part = node(
                ProvisionKind.PART,
                number=prefix,
                heading=orders[prefix],
                canonical_path=f"{instrument_slug}.order{prefix.lower()}",
                parent_path=None,
                page_start=page,
            )
            if prefix in pending:
                open_rule(prefix, "0", page)
            continue
        if _APPENDIX.match(line):
            finish()
            continue
        if appendix := _APPENDIX_PART.match(line):
            finish()
            letter = appendix.group(1).upper()
            schedule = node(
                ProvisionKind.SCHEDULE,
                number=letter,
                heading="Schedule of Fees" if letter == "A" else "Forms",
                canonical_path=f"{instrument_slug}.schedule{letter.lower()}",
                parent_path=None,
                page_start=page,
            )
            if letter == "A":
                current = schedule
            continue
        if schedule is not None:
            form = _FORM_HEADING.match(line)
            if form and form.group(1) in forms:
                finish()
                current = node(
                    ProvisionKind.SCHEDULE_ITEM,
                    number=form.group(1),
                    heading=forms[form.group(1)],
                    canonical_path=f"{schedule.canonical_path}.item{form.group(1)}",
                    parent_path=schedule.canonical_path,
                    page_start=page,
                )
                continue
        elif (marker := _ACT_SECTION.match(line)) and (
            f"{prefix}.{marker.group(1)}" == (pending[0] if pending else None)
        ):
            finish()
            open_rule(f"{prefix}.{marker.group(1)}", marker.group(1), page)
            text_lines = [marker.group(2).lstrip("—–- ").strip()]
            continue
        if current:
            current.page_end = page
            text_lines.append(line)
    finish()
    return result


def parse_act_pages(
    pages: list[SourcePage],
    instrument_slug: str,
    reviewed_titles: dict[str, str] | None = None,
) -> ActParse:
    """Parse an Act. reviewed_titles replaces a scan's unreadable arrangement.

    With a reviewed catalogue the body is reconciled against it, and a numbered
    line only opens a section when it is the next section in sequence, so a
    misread label is reported as a missing section and never guessed.
    """
    running = _running_signatures(pages)
    lines = _lines(pages, running)
    start = _body_start(lines)
    titles, arrangement_pages, issues = _arrangement(lines[:start])
    next_label: list[str] = []
    if reviewed_titles:
        titles = {key.lower(): value for key, value in reviewed_titles.items()}
        next_label = list(titles)
        issues = []
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
        plural = _PLURAL_SCHEDULE.match(line) and line.split()[0].isupper()
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
            if schedule and re.search(r"\bS\s+CHEDULE\b", line, re.I):
                result.issues.append(
                    f'Schedule heading "{line}" on page {page} has a split letter; '
                    "the source spelling is retained"
                )
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
        if current_schedule and _OUTLINE_ITEM.match(line):
            # "1.1.1 Diseases caused by ..." is an outline entry inside a schedule
            # list, not a numbered item.
            if current:
                current.page_end = page
            text_lines.append(line)
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
        if (
            section
            and reviewed_titles
            and not current_schedule
            and (not next_label or section.group(1).lower() != next_label[0])
        ):
            section = None
        if section:
            number, rest = section.group(1).lower(), section.group(2).strip()
            if next_label and not current_schedule:
                next_label.pop(0)
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
                and int(numeric.group()) >= 1000
                and current
            ):
                # A wrapped margin note ("Act No. 2,\n2004.") starts a line with a
                # calendar year. No Act has a thousand sections.
                result.issues.append(
                    f"Year-like marker {number} on page {page} kept as text"
                )
                text_lines.append(line)
                continue
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
                # Printed forms restart their numbering; with a reviewed catalogue
                # the sections are already gated, so this is only form wording.
                if not reviewed_titles:
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
