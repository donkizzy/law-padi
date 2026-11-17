"""Every published law can be cited by name, and only by its own names."""

import json
from pathlib import Path

import pytest

from app.legal.instruments import instrument_label, instrument_names, law_mentions
from app.legal.references import (
    UNKNOWN_LAW_MESSAGE,
    SectionReference,
    parse_section_reference,
    source_references,
)
from app.legal.titles import DATA_DIR

ROOT = Path(__file__).resolve().parents[3]


def _published_slugs() -> list[str]:
    """Each published law ships a title catalogue or a retrieval benchmark."""
    catalogued = {
        path.name.removesuffix("-section-titles.json")
        for path in DATA_DIR.glob("*-section-titles.json")
    }
    benchmarked = {
        slug
        for path in (ROOT / "eval/datasets").glob("*.json")
        if isinstance(data := json.loads(path.read_text()), dict)
        and isinstance(slug := data.get("instrument_slug"), str)
    }
    return sorted(catalogued | benchmarked)


PUBLISHED = _published_slugs()
NAMED = [
    (slug, name)
    for slug in PUBLISHED
    if slug in instrument_names()
    for name in instrument_names()[slug].names
]


def test_published_instruments_are_found() -> None:
    # Guards the discovery itself: an empty list would make the checks vacuous.
    assert {"constitution-1999", "evidence-act-2011", "nigeria-tax-act-2025"} <= set(
        PUBLISHED
    )
    assert len(PUBLISHED) >= 20


@pytest.mark.parametrize("slug", PUBLISHED)
def test_every_published_instrument_has_citation_names(slug: str) -> None:
    entry = instrument_names().get(slug)
    assert entry is not None, f"{slug} has no entry in instrument-names.json"
    assert entry.names
    assert entry.years
    assert instrument_label(slug) == entry.label != slug


@pytest.mark.parametrize("prose", [False, True])
@pytest.mark.parametrize(("slug", "name"), NAMED)
def test_every_published_instrument_resolves_by_name(
    slug: str, name: str, prose: bool
) -> None:
    year = sorted(instrument_names()[slug].years)[0]
    expected = SectionReference("1", instrument_slug=slug)
    for query in (
        f"Section 1 of the {name}",
        f"section 1 of the {name} {year}",
        f"Section 1, {name}, {year}",
        f"{name} section 1",
        f"{name} {year} s.1",
    ):
        parsed = parse_section_reference(query, prose=prose)
        assert parsed.error is None, query
        assert parsed.reference == expected, query


@pytest.mark.parametrize(("slug", "name"), NAMED)
def test_a_name_belongs_to_exactly_one_instrument(slug: str, name: str) -> None:
    mentions = law_mentions(f"see the {name} today")
    assert [(mention.slug, mention.valid_year) for mention in mentions] == [
        (slug, True)
    ]


@pytest.mark.parametrize(("slug", "name"), NAMED)
def test_a_wrong_year_is_never_resolved(slug: str, name: str) -> None:
    del slug
    parsed = parse_section_reference(f"Section 1 of the {name} 1888")
    assert parsed.error == UNKNOWN_LAW_MESSAGE
    assert not parsed.references


@pytest.mark.parametrize(
    ("query", "slug", "section"),
    [
        ("Section 84 of the Evidence Act 2011", "evidence-act-2011", "84"),
        ("Evidence Act section 84", "evidence-act-2011", "84"),
        ("section 7 Labour Act", "labour-act", "7"),
        ("section 1 of the Land Use Act", "land-use-act-1978", "1"),
        ("Section 35 of the Police Act", "police-act-2020", "35"),
        (
            "Section 24 of the Cybercrimes (Prohibition, Prevention, etc.) Act, 2015",
            "cybercrimes-prohibition-prevention-etc-act-2015",
            "24",
        ),
        (
            "Section 24 of the Cybercrimes (Amendment) Act 2024",
            "cybercrimes-prohibition-prevention-etc-amendment-act-2024",
            "24",
        ),
        (
            "section 3 of the National Minimum Wage (Amendment) Act",
            "national-minimum-wage-amendment-act-2024",
            "3",
        ),
        (
            "section 3 of the National Minimum Wage Act",
            "national-minimum-wage-act-2019",
            "3",
        ),
        (
            "section 1 of the Employees Compensation Act",
            "employees-compensation-act-2010",
            "1",
        ),
        (
            "section 1 of the Employees’ Compensation Act",
            "employees-compensation-act-2010",
            "1",
        ),
        ("Penal Code Act section 222", "penal-code-act-abuja", "222"),
        ("section 316 of the Criminal Code", "criminal-code-act", "316"),
        ("NDPA s.24", "nigeria-data-protection-act-2023", "24"),
        (
            "FCCPA section 17",
            "federal-competition-and-consumer-protection-act-2018",
            "17",
        ),
    ],
)
def test_reported_citations_resolve_to_the_named_law(
    query: str, slug: str, section: str
) -> None:
    parsed = parse_section_reference(query)
    assert parsed.error is None
    assert parsed.reference == SectionReference(section, instrument_slug=slug)


def test_selected_law_can_also_be_named_in_the_query() -> None:
    parsed = parse_section_reference(
        "Section 84 of the Evidence Act",
        default_instrument_slug="evidence-act-2011",
    )
    assert parsed.reference == SectionReference(
        "84", instrument_slug="evidence-act-2011"
    )


def test_citation_uses_the_published_short_title() -> None:
    assert (
        SectionReference("84", instrument_slug="evidence-act-2011").citation
        == "Section 84, Evidence Act 2011"
    )
    assert SectionReference("35").citation == "Section 35"


@pytest.mark.parametrize(
    "query",
    [
        "Section 33 of the Freedom of Information Act",
        "Section 9, Freedom of Information Act",
        "Section 9, Health and Safety at Work Act",
        "Lagos State Land Use Act section 1",
        "Section 84 of the Evidence (Amendment) Act",
    ],
)
def test_laws_outside_the_registry_are_still_unrecognised(query: str) -> None:
    for prose in (False, True):
        parsed = parse_section_reference(query, prose=prose)
        assert parsed.error
        assert not parsed.references


def test_source_cross_references_keep_the_named_law() -> None:
    assert source_references(
        "Subject to section 84 of the Evidence Act, see section 35 of this Constitution."
    ) == (
        SectionReference("84", instrument_slug="evidence-act-2011"),
        SectionReference("35"),
    )


def test_unknown_source_law_never_expands_to_the_constitution() -> None:
    assert source_references(
        "See Section 9, Freedom of Information Act; and Section 37 of this Constitution."
    ) == (SectionReference("37"),)
