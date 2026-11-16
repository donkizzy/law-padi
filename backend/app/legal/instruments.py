"""Recognised citation names, independent of publication or source verification."""

import re
from dataclasses import dataclass

CONSTITUTION_SLUG = "constitution-1999"
ACJA_SLUG = "acja-2015"
POLICE_SLUG = "police-act-2020"

# Recognition never grants access: canonical lookups still require release entries.
INSTRUMENT_NAMES = {
    CONSTITUTION_SLUG: (
        "Constitution",
        "1999",
        (
            r"(?:1999\s+)?Constitution(?:\s+of\s+the\s+Federal\s+Republic\s+of\s+Nigeria)?",
        ),
    ),
    ACJA_SLUG: (
        "ACJA 2015",
        "2015",
        (
            r"Administration\s+of\s+Criminal\s+Justice\s+Act",
            r"ACJ\s+Act",
            r"ACJA",
        ),
    ),
    POLICE_SLUG: ("Police Act 2020", "2020", (r"(?:Nigerian?\s+)?Police\s+Act",)),
    "joint-revenue-board-of-nigeria-establishment-act-2025": (
        "Joint Revenue Board Act 2025",
        "2025",
        (
            r"Joint\s+Revenue\s+Board\s+of\s+Nigeria\s*\(Establishment\)\s+Act",
            r"Joint\s+Revenue\s+Board\s+Act",
            r"JRB\s+Act",
        ),
    ),
}
_ALIASES = [
    (slug, re.compile(pattern, re.I))
    for slug, (_, _, aliases) in INSTRUMENT_NAMES.items()
    for pattern in aliases
]
LAW_NAME = re.compile(
    r"(?<!\w)(?:"
    + "|".join(pattern.pattern for _, pattern in _ALIASES)
    + r")(?!\w)(?:\s*,?\s*(?P<year>\d{4})(?!\w))?",
    re.I,
)


@dataclass(frozen=True)
class LawMention:
    start: int
    end: int
    slug: str
    valid_year: bool


def law_mentions(text: str) -> list[LawMention]:
    result = []
    for match in LAW_NAME.finditer(text):
        name = (
            text[match.start() : match.start("year")].rstrip(" ,\t\r\n")
            if match.group("year")
            else match.group()
        )
        slug = next(slug for slug, alias in _ALIASES if alias.fullmatch(name))
        result.append(
            LawMention(
                match.start(),
                match.end(),
                slug,
                match.group("year") in (None, INSTRUMENT_NAMES[slug][1]),
            )
        )
    return result


def instrument_label(slug: str) -> str:
    return INSTRUMENT_NAMES[slug][0] if slug in INSTRUMENT_NAMES else slug
