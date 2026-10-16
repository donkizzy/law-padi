"""Deterministic Constitution references; never infer a missing legal identity."""

import re
from dataclasses import dataclass

_START = re.compile(r"(?<!\w)(?:sections?\b|s\.(?=\s*\d)|s\b(?=\s*\d)|§)", re.I)
_REFERENCE = re.compile(
    r"\s*(?P<section>\d+[a-z]?)(?![\w])"
    r"(?:\s*\(\s*(?P<subsection>\d+[a-z]?)\s*\)|"
    r"\s*[,;]?\s*subsection\s*\(?\s*(?P<subsection_word>\d+[a-z]?)\s*\)?)?"
    r"(?:\s*\(\s*(?P<paragraph>[a-z])\s*\)|"
    r"\s*[,;]?\s*paragraph\s*\(?\s*(?P<paragraph_word>[a-z])(?![a-z0-9])\s*\)?)?",
    re.I,
)
_CONTINUATION = re.compile(r"\s*(?:,\s*(?:and\s+)?|\band\s+)", re.I)
_RANGE = re.compile(r"\s*(?:[-–—]|\bto\b)\s*", re.I)
_TOKEN = re.compile(
    r"(?:\d+[a-z]?(?:\(\d+[a-z]?\))?(?:\([a-z]\))?|\(\d+[a-z]?\)|\([a-z]\))", re.I
)
_OTHER_INSTRUMENT = re.compile(
    r"\b(?:of|under|in)\s+(?!the\s+(?:1999\s+)?constitution\b)"
    r"(?:the\s+)?[\w\s]*?\b(?:act|code|bill|regulation|law|decree)\b",
    re.I,
)
_PROSE_OTHER_INSTRUMENT = re.compile(
    r"\s+of\s+(?!the\s+(?:1999\s+)?constitution\b)"
    r"(?:the\s+)?(?:[\w-]+\s+){0,4}(?:act|code|bill|regulation|law|decree)\b",
    re.I,
)
_MAX_REFERENCES = 20


@dataclass(frozen=True)
class SectionReference:
    section: str
    subsection: str | None = None
    paragraph: str | None = None

    @property
    def suffix(self) -> str:
        value = f".section{self.section}"
        if self.subsection:
            value += f".subsection{self.subsection}"
        if self.paragraph:
            value += f".paragraph{self.paragraph}"
        return value

    @property
    def citation(self) -> str:
        return (
            f"Section {self.section}"
            + (f"({self.subsection})" if self.subsection else "")
            + (f"({self.paragraph})" if self.paragraph else "")
        )


@dataclass(frozen=True)
class ReferenceParse:
    references: tuple[SectionReference, ...] = ()
    error: str | None = None

    @property
    def reference(self) -> SectionReference | None:
        return self.references[0] if len(self.references) == 1 else None


def _from_match(match: re.Match[str]) -> SectionReference:
    return SectionReference(
        match.group("section").lower(),
        (match.group("subsection") or match.group("subsection_word") or "").lower()
        or None,
        (match.group("paragraph") or match.group("paragraph_word") or "").lower()
        or None,
    )


def _endpoint(token: str, start: SectionReference) -> SectionReference | None:
    if token.startswith("("):
        value = token[1:-1].lower()
        if value.isdigit() and start.subsection and not start.paragraph:
            return SectionReference(start.section, value)
        if len(value) == 1 and value.isalpha() and start.paragraph:
            return SectionReference(start.section, start.subsection, value)
        return None
    match = _REFERENCE.fullmatch(token)
    return _from_match(match) if match else None


def _expand(
    start: SectionReference, end: SectionReference
) -> list[SectionReference] | None:
    if (
        start.paragraph
        and end.paragraph
        and (start.section, start.subsection)
        == (
            end.section,
            end.subsection,
        )
    ):
        lower, upper = ord(start.paragraph), ord(end.paragraph)
        if upper < lower or upper - lower + 1 > _MAX_REFERENCES:
            return None
        return [
            SectionReference(start.section, start.subsection, chr(n))
            for n in range(lower, upper + 1)
        ]
    if (
        start.subsection
        and end.subsection
        and not start.paragraph
        and not end.paragraph
        and start.section == end.section
    ):
        if not start.subsection.isdigit() or not end.subsection.isdigit():
            return None
        lower, upper = int(start.subsection), int(end.subsection)
        if upper < lower or upper - lower + 1 > _MAX_REFERENCES:
            return None
        return [
            SectionReference(start.section, str(n)) for n in range(lower, upper + 1)
        ]
    if (
        not start.subsection
        and not start.paragraph
        and not end.subsection
        and not end.paragraph
    ):
        if not start.section.isdigit() or not end.section.isdigit():
            return None
        lower, upper = int(start.section), int(end.section)
        if upper < lower or upper - lower + 1 > _MAX_REFERENCES:
            return None
        return [SectionReference(str(n)) for n in range(lower, upper + 1)]
    return None


def _unsupported() -> ReferenceParse:
    return ReferenceParse(
        error="Try a reference like Section 35, Section 35(1) or Section 35(1)(c). Lists and ranges can include up to 20 sections."
    )


def parse_section_reference(query: str, *, prose: bool = False) -> ReferenceParse:
    """Parse explicit references, retaining order and duplicates.

    Prose mode ignores unnumbered uses of "section" and ordinary conjunctions
    around citations while retaining malformed-citation and instrument checks.
    """
    starts = list(_START.finditer(query))
    if prose:
        starts = [
            marker for marker in starts if re.match(r"\s*\d", query[marker.end() :])
        ]
    if not starts:
        return ReferenceParse()
    references: list[SectionReference] = []
    for index, marker in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(query)
        fragment = query[marker.end() : end]
        match = _REFERENCE.match(fragment)
        if prose:
            other_instrument = bool(
                match and _PROSE_OTHER_INSTRUMENT.match(fragment[match.end() :])
            )
        else:
            other_instrument = bool(_OTHER_INSTRUMENT.search(fragment))
        if other_instrument:
            return ReferenceParse(
                error="Law Padi covers Nigeria's Constitution only, so it can't look up sections of other laws."
            )
        if not match:
            if len(starts) == 1 and not re.search(r"\d|[()]", fragment):
                return ReferenceParse()
            return _unsupported()
        current = _from_match(match)
        references.append(current)
        position = match.end()
        while position < len(fragment):
            remaining = fragment[position:]
            range_match = _RANGE.match(remaining)
            separator = _CONTINUATION.match(remaining) if not range_match else None
            if not range_match and not separator:
                if re.match(
                    r"\s*(?:[()\d§;,]|[-–—]|\b(?:to|and|or|subsection|paragraph)\b)",
                    remaining,
                    re.I,
                ):
                    return _unsupported()
                break
            delimiter = range_match or separator
            assert delimiter is not None
            position += delimiter.end()
            token = _TOKEN.match(fragment[position:])
            if not token:
                if (
                    prose
                    and separator
                    and not re.match(
                        r"\s*(?:\d|\(|subsection\b|paragraph\b)",
                        fragment[position:],
                        re.I,
                    )
                ):
                    break
                # A comma after a valid citation can also introduce ordinary
                # prose, such as "Section 7, which ...". Keep rejecting
                # malformed hierarchy suffixes and unfinished ranges.
                if (
                    separator
                    and "," in delimiter.group()
                    and re.match(r"\s*[a-z]", fragment[position:], re.I)
                    and not re.match(
                        r"\s*(?:subsection|paragraph)\b", fragment[position:], re.I
                    )
                ):
                    break
                if (
                    separator
                    and index + 1 < len(starts)
                    and not fragment[position:].strip()
                ):
                    break
                return _unsupported()
            candidate = _endpoint(token.group(), current)
            if candidate is None:
                return _unsupported()
            if range_match:
                expanded = _expand(current, candidate)
                if expanded is None:
                    return _unsupported()
                references.extend(expanded[1:])
            else:
                references.append(candidate)
            current = candidate
            position += token.end()
            if len(references) > _MAX_REFERENCES:
                return _unsupported()
        if len(references) > _MAX_REFERENCES:
            return _unsupported()
    return ReferenceParse(tuple(references))
