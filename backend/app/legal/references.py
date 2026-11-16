"""Deterministic, instrument-scoped references to canonical provisions."""

import re
from dataclasses import dataclass, replace
from typing import overload

from sqlalchemy import and_
from sqlalchemy.orm import Mapped
from sqlalchemy.sql.elements import ColumnElement

from app.legal.instruments import CONSTITUTION_SLUG as CONSTITUTION_SLUG
from app.legal.instruments import LawMention, instrument_label, law_mentions

_START = re.compile(r"(?<!\w)(?:sections?\b|s\.(?=\s*\d)|s(?=\s*\d)|§)", re.I)
_REFERENCE = re.compile(
    r"\s*(?P<section>\d+[a-z]?)(?![\w])"
    r"(?:\s*\(\s*(?P<subsection>\d+[a-z]?)\s*\)|"
    r"\s*[,;]?\s*subsection\s*\(?\s*(?P<subsection_word>\d+[a-z]?)\s*\)?)?"
    r"(?:\s*\(\s*(?P<paragraph>[a-z])\s*\)|"
    r"\s*[,;]?\s*paragraph\s*\(?\s*(?P<paragraph_word>[a-z])(?![a-z0-9])\s*\)?)?",
    re.I,
)
_CONTINUATION = re.compile(r"\s*(?:,\s*(?:(?:and|or)\s+)?|\b(?:and|or)\s+)", re.I)
_RANGE = re.compile(r"\s*(?:[-–—]|\bto\b)\s*", re.I)
_TOKEN = re.compile(
    r"(?:\d+[a-z]?(?:\(\d+[a-z]?\))?(?:\([a-z]\))?|\(\d+[a-z]?\)|\([a-z]\))", re.I
)
_PROSE_OTHER_INSTRUMENT = re.compile(
    r"\s+(?:of|under|in)\s+(?!the\s+(?:1999\s+)?constitution\b)"
    r"(?:the\s+)?(?:[\w-]+\s+|\([\w -]+\)\s+){0,8}"
    r"(?:act|code|bill|regulations?|law|decree|ACJL)\b",
    re.I,
)
_COMMA_PARENTHETICAL_LAW = re.compile(
    r"\s*,\s*(?:[\w-]+\s+){1,8}\([\w -]+\)\s+"
    r"(?:act|code|bill|regulations?|law|decree|ACJL)\b",
    re.I,
)
_MAX_REFERENCES = 20
_PREFIX_CONTEXT = frozenset(
    "the this that of under in from by per to and or see explain compare about does say says is read show me what describe interpret for at summarise summarize please regarding concerning".split()
)


@dataclass(frozen=True)
class SectionReference:
    section: str
    subsection: str | None = None
    paragraph: str | None = None
    instrument_slug: str = CONSTITUTION_SLUG

    @property
    def suffix(self) -> str:
        """Qualified identity, independent of an instrument's chapter/part layout."""
        return f"{self.instrument_slug}{self.provision_suffix}"

    @property
    def provision_suffix(self) -> str:
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
            + (
                f", {instrument_label(self.instrument_slug)}"
                if self.instrument_slug != CONSTITUTION_SLUG
                else ""
            )
        )


@overload
def matches_reference(path: str, reference: SectionReference) -> bool: ...


@overload
def matches_reference(
    path: Mapped[str], reference: SectionReference
) -> ColumnElement[bool]: ...


def matches_reference(
    path: str | Mapped[str], reference: SectionReference
) -> bool | ColumnElement[bool]:
    """Use identical instrument and hierarchy boundaries in memory and SQL."""
    prefix = f"{reference.instrument_slug}."
    if isinstance(path, str):
        return path.startswith(prefix) and path.endswith(reference.provision_suffix)
    return and_(
        path.startswith(prefix, autoescape=True),
        path.endswith(reference.provision_suffix, autoescape=True),
    )


@dataclass(frozen=True)
class ReferenceParse:
    references: tuple[SectionReference, ...] = ()
    error: str | None = None

    @property
    def reference(self) -> SectionReference | None:
        return self.references[0] if len(self.references) == 1 else None


def _from_match(
    match: re.Match[str], instrument_slug: str = CONSTITUTION_SLUG
) -> SectionReference:
    return SectionReference(
        match.group("section").lower(),
        (match.group("subsection") or match.group("subsection_word") or "").lower()
        or None,
        (match.group("paragraph") or match.group("paragraph_word") or "").lower()
        or None,
        instrument_slug,
    )


def _endpoint(token: str, start: SectionReference) -> SectionReference | None:
    if token.startswith("("):
        value = token[1:-1].lower()
        if value.isdigit() and start.subsection and not start.paragraph:
            return SectionReference(
                start.section, value, instrument_slug=start.instrument_slug
            )
        if len(value) == 1 and value.isalpha() and start.paragraph:
            return SectionReference(
                start.section, start.subsection, value, start.instrument_slug
            )
        return None
    match = _REFERENCE.fullmatch(token)
    return _from_match(match, start.instrument_slug) if match else None


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
            SectionReference(
                start.section, start.subsection, chr(n), start.instrument_slug
            )
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
            SectionReference(
                start.section, str(n), instrument_slug=start.instrument_slug
            )
            for n in range(lower, upper + 1)
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
        return [
            SectionReference(str(n), instrument_slug=start.instrument_slug)
            for n in range(lower, upper + 1)
        ]
    return None


REFERENCE_FORMAT_MESSAGE = "Try a reference like Section 35, Section 35(1) or Section 35(1)(c). Lists and ranges can include up to 20 sections."
UNKNOWN_LAW_MESSAGE = "The law name or year in this reference is unrecognised or conflicting. Sections are available for laws included in the selected published edition."


def _unsupported() -> ReferenceParse:
    return ReferenceParse(error=REFERENCE_FORMAT_MESSAGE)


def _unknown_law() -> ReferenceParse:
    return ReferenceParse(error=UNKNOWN_LAW_MESSAGE)


def _reference_markers(
    query: str, *, prose: bool
) -> tuple[list[re.Match[str]], list[LawMention | None]]:
    starts = list(_START.finditer(query))
    if prose:
        starts = [
            marker for marker in starts if re.match(r"\s*\d", query[marker.end() :])
        ]
    if not starts:
        return [], []
    mentions = law_mentions(query)
    prefixes = [
        next(
            (
                law
                for law in reversed(mentions)
                if law.end <= marker.start()
                and re.fullmatch(r"\s*[:,\-]?\s*", query[law.end : marker.start()])
            ),
            None,
        )
        for marker in starts
    ]
    # A suffix immediately before a comma-separated next marker belongs to
    # the preceding reference, rather than qualifying the next one twice.
    for index in range(1, len(starts)):
        law = prefixes[index]
        if law is None or law.start < starts[index - 1].end():
            continue
        preceding = query[starts[index - 1].end() : law.start]
        gap = query[law.end : starts[index].start()]
        if re.search(r"\b(?:of|under|in)\s+(?:(?:the|this)\s+)?$", preceding, re.I) or (
            "," in gap and re.search(r"[\d)]\s*,?\s*$", preceding)
        ):
            prefixes[index] = None
    return starts, prefixes


def parse_section_reference(
    query: str, *, prose: bool = False, default_instrument_slug: str = CONSTITUTION_SLUG
) -> ReferenceParse:
    """Parse explicit references, retaining order and duplicates.

    Prose mode ignores unnumbered uses of "section" and ordinary conjunctions
    around citations while retaining malformed-citation and instrument checks.
    """
    starts, prefixes = _reference_markers(query, prose=prose)
    if not starts:
        return ReferenceParse()
    references: list[SectionReference] = []
    for index, marker in enumerate(starts):
        prefix = prefixes[index]
        if prefix and not prefix.valid_year:
            return _unknown_law()
        # Reject a recognised alias embedded in a different law's name.
        modifier = (
            re.search(r"\b([\w-]+)\s+$", query[: prefix.start]) if prefix else None
        )
        if modifier and modifier.group(1).casefold() not in _PREFIX_CONTEXT:
            return _unknown_law()
        before = query[: marker.start()]
        if prefix is None and re.search(
            r"\b(?:act|code|bill|regulation|law|decree)\s*(?:\d{4})?\s*[:,\-]?\s*$",
            before,
            re.I,
        ):
            return _unknown_law()
        acronym = re.search(r"\b([A-Z]{2,})(?:\s+\d{4})?\s*$", before)
        if (
            prefix is None
            and acronym
            and acronym.group(1).casefold() not in _PREFIX_CONTEXT
        ):
            return _unknown_law()
        next_prefix = prefixes[index + 1] if index + 1 < len(starts) else None
        end = (
            next_prefix.start
            if next_prefix
            else starts[index + 1].start()
            if index + 1 < len(starts)
            else len(query)
        )
        fragment = query[marker.end() : end]
        match = _REFERENCE.match(fragment)
        if not match:
            if len(starts) == 1 and not re.search(r"\d|[()]", fragment):
                return ReferenceParse()
            return _unsupported()
        group_start = len(references)
        current = _from_match(match, prefix.slug if prefix else default_instrument_slug)
        references.append(current)
        position = match.end()
        while position < len(fragment):
            remaining = fragment[position:]
            qualifier = re.match(
                r"\s*(?:,\s*)?(?:(?:of|under|in)\s+(?:(?:the|this)\s+)?)?",
                remaining,
                re.I,
            )
            assert qualifier is not None
            qualified = remaining[qualifier.end() :]
            laws = law_mentions(qualified)
            law = laws[0] if laws and laws[0].start == 0 else None
            # "This Act" is relative to the source or selected Act, never a
            # fallback to the Constitution. Explicit named laws still win.
            own_act = re.match(r"\s+(?:of|under|in)\s+this\s+Act\b", remaining, re.I)
            if own_act and default_instrument_slug != CONSTITUTION_SLUG:
                law = LawMention(
                    0, own_act.end() - qualifier.end(), default_instrument_slug, True
                )
            if law:
                if not law.valid_year or (prefix and prefix.slug != law.slug):
                    return _unknown_law()
                references[group_start:] = [
                    replace(ref, instrument_slug=law.slug)
                    for ref in references[group_start:]
                ]
                current = replace(current, instrument_slug=law.slug)
                position += qualifier.end() + law.end
                tail = fragment[position:]
                # A second numbered group needs its own section marker and law.
                if re.match(r"\s*(?:,|and|to|[-–—])\s*\d", tail, re.I):
                    return _unsupported()
                prefix = law
                continue
            if qualifier.end() and re.match(
                r"[A-Z]{2,}(?!\w)", remaining[qualifier.end() :]
            ):
                return _unknown_law()
            if (
                _PROSE_OTHER_INSTRUMENT.match(remaining)
                or _COMMA_PARENTHETICAL_LAW.match(remaining)
                or re.match(
                    # Ordinary prose such as "shall invalidate any law"
                    # does not name another instrument.
                    r"\s*,?\s*(?:[A-Z][\w-]*\s+){0,8}(?:Act|Code|Bill|Regulations?|Law|Decree|ACJL)\b"
                    if prose
                    else r"\s*,?\s*(?:[\w-]+\s+){0,8}(?:act|code|bill|regulations?|law|decree|acjl)\b",
                    remaining,
                    0 if prose else re.I,
                )
            ):
                return _unknown_law()
            range_match = _RANGE.match(remaining)
            # An explanation addressed "to me/us" is prose, not a range.
            if re.match(r"\s+to\s+(?:me|us)\b", remaining, re.I):
                break
            separator = _CONTINUATION.match(remaining) if not range_match else None
            if not range_match and not separator:
                if prose and re.match(r"\s*;", remaining):
                    break
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


def source_reference_groups(
    text: str, *, instrument_slug: str = CONSTITUTION_SLUG
) -> list[tuple[SectionReference, ...]]:
    """Check each numbered source group independently; unsupported laws stay out.

    Strict parsing of a user's query or an answer still rejects the whole
    input on an unsupported citation. Source prose can contain an unavailable
    law alongside useful independent references, so its failures are local.
    """
    markers, prefixes = _reference_markers(text, prose=True)
    groups: list[tuple[SectionReference, ...]] = []
    for index, marker in enumerate(markers):
        prefix = prefixes[index]
        start = prefix.start if prefix else marker.start()
        if prefix:
            modifier = re.search(r"\b[\w-]+\s+$", text[:start])
            if modifier:
                start = modifier.start()
        else:
            # Retain an unknown prefix name so Evidence Act/ACJL cannot
            # silently become a reference to the source instrument.
            unknown = re.search(
                r"\b(?:act|code|bill|regulations?|law|decree|ACJL)\b(?:\s+\d{4})?\s*[:,\-]?\s*$",
                text[:start],
                re.I,
            )
            if unknown and not (index and "," in unknown.group()):
                start = unknown.start()
        next_prefix = prefixes[index + 1] if index + 1 < len(markers) else None
        end = (
            next_prefix.start
            if next_prefix
            else markers[index + 1].start()
            if index + 1 < len(markers)
            else len(text)
        )
        parsed = parse_section_reference(
            text[start:end], prose=True, default_instrument_slug=instrument_slug
        )
        if not parsed.error and parsed.references:
            groups.append(parsed.references)
    return groups


def source_references(
    text: str, *, instrument_slug: str = CONSTITUTION_SLUG
) -> tuple[SectionReference, ...]:
    return tuple(
        dict.fromkeys(
            reference
            for group in source_reference_groups(text, instrument_slug=instrument_slug)
            for reference in group
        )
    )
