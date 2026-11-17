"""Recognised citation names, independent of publication or source verification.

The names live in ``data/instrument-names.json``. Recognition never grants
access: canonical lookups still require release entries.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

CONSTITUTION_SLUG = "constitution-1999"
ACJA_SLUG = "acja-2015"
POLICE_SLUG = "police-act-2020"

NAMES_PATH = Path(__file__).parent / "data" / "instrument-names.json"
_TRAILING_YEAR = re.compile(r"[\s,]*\b\d{4}$")


@dataclass(frozen=True)
class InstrumentNames:
    slug: str
    label: str
    years: frozenset[str]
    names: tuple[str, ...]


def _strip_year(name: str) -> str:
    return _TRAILING_YEAR.sub("", " ".join(name.split()))


@cache
def instrument_names() -> dict[str, InstrumentNames]:
    data = json.loads(NAMES_PATH.read_text(encoding="utf-8"))["instruments"]
    registry: dict[str, InstrumentNames] = {}
    for slug, entry in data.items():
        candidates = [entry["title"], entry["label"], *entry["aliases"]]
        names = dict.fromkeys(_strip_year(name) for name in candidates)
        registry[slug] = InstrumentNames(
            slug=slug,
            label=entry["label"],
            years=frozenset(entry["years"]),
            names=tuple(name for name in names if name),
        )
    return registry


def _name_pattern(name: str) -> str:
    """Match a written name with optional punctuation and flexible spacing."""
    parts: list[str] = []
    for char in name:
        if char.isspace():
            parts.append(r"\s+")
        elif char in ".,":
            parts.append(re.escape(char) + "?")
        elif char in "'’":
            parts.append("['’]?")
        elif char == "(":
            parts.append(r"\(?\s*")
        elif char == ")":
            parts.append(r"\s*\)?")
        else:
            parts.append(re.escape(char))
    return "".join(parts).replace(r"\s+\(?", r"\s*\(?")


@cache
def _aliases() -> tuple[tuple[str, re.Pattern[str]], ...]:
    # Longer names come first, so "Penal Code Act" is never read as
    # "Penal Code" followed by a stray word.
    named = sorted(
        (
            (slug, name)
            for slug, entry in instrument_names().items()
            for name in entry.names
        ),
        key=lambda item: -len(item[1]),
    )
    return tuple((slug, re.compile(_name_pattern(name), re.I)) for slug, name in named)


@cache
def _law_name() -> re.Pattern[str]:
    return re.compile(
        r"(?<!\w)(?:"
        + "|".join(pattern.pattern for _, pattern in _aliases())
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
    registry = instrument_names()
    result = []
    for match in _law_name().finditer(text):
        name = (
            text[match.start() : match.start("year")].rstrip(" ,\t\r\n")
            if match.group("year")
            else match.group()
        )
        slug = next(slug for slug, alias in _aliases() if alias.fullmatch(name))
        year = match.group("year")
        result.append(
            LawMention(
                match.start(),
                match.end(),
                slug,
                year is None or year in registry[slug].years,
            )
        )
    return result


def instrument_label(slug: str) -> str:
    entry = instrument_names().get(slug)
    return entry.label if entry else slug
