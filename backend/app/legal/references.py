"""Deterministic user references; this never infers missing legal identities."""

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


@dataclass(frozen=True)
class ReferenceParse:
    reference: SectionReference | None = None
    error: str | None = None


def parse_section_reference(query: str) -> ReferenceParse:
    starts = list(_START.finditer(query))
    if not starts:
        return ReferenceParse()
    if len(starts) != 1:
        return ReferenceParse(error="Search one section reference at a time.")
    start = starts[0]
    match = _REFERENCE.match(query, start.end())
    if not match:
        if (
            not re.search(r"\d|[()]", query[start.end() :])
            and query[start.end() :].strip()
        ):
            return ReferenceParse()
        return ReferenceParse(error="Use a reference such as Section 33(2)(a).")
    remainder = query[match.end() :].lstrip()
    # Never truncate unsupported nested clauses, ranges, or malformed markers.
    if re.match(
        r"^(?:[()\d§]|[-–—]|[,;]\s*\d|[,;]?\s*(?:and|or|to)\s+\d|[,;]?\s*(?:subsection|paragraph)\b)",
        remainder,
        re.I,
    ):
        return ReferenceParse(
            error="Use one section, subsection, or paragraph reference, such as Section 33(2)(a)."
        )
    return ReferenceParse(
        reference=SectionReference(
            section=match.group("section").lower(),
            subsection=(
                match.group("subsection") or match.group("subsection_word") or ""
            ).lower()
            or None,
            paragraph=(
                match.group("paragraph") or match.group("paragraph_word") or ""
            ).lower()
            or None,
        )
    )
