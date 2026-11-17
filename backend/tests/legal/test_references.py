import pytest

from app.legal.references import (
    SectionReference,
    matches_reference,
    parse_section_reference,
)


@pytest.mark.parametrize(
    "query",
    [
        "Section 33(2)(a)",
        "s.33(2)(a)",
        "§33(2)(a)",
        "Section 33 subsection 2 paragraph a",
        "section 33, subsection (2), paragraph (a)",
        "What does Section 33(2)(a) say?",
        "Explain Section 33(2)(a) to me",
        "Explain Section 33(2)(a) to us, please",
    ],
)
def test_reference_formats_resolve_to_identical_hierarchy(query: str) -> None:
    parsed = parse_section_reference(query)
    assert parsed.error is None
    assert parsed.reference == SectionReference("33", "2", "a")
    assert (
        parsed.reference.suffix == "constitution-1999.section33.subsection2.paragrapha"
    )


@pytest.mark.parametrize(
    "slug", ["constitution-1999", "acja-2015", "police-act-2020", "law_with%wildcards"]
)
def test_reference_requires_exact_instrument_and_hierarchy(slug: str) -> None:
    reference = SectionReference("9", instrument_slug=slug)
    assert matches_reference(f"{slug}.part2.section9", reference)
    assert matches_reference(f"{slug}.section9", reference)
    assert not matches_reference("other-law.part2.section9", reference)
    assert not matches_reference(f"{slug}-other.part2.section9", reference)
    assert not matches_reference(f"{slug}.part2.section90", reference)
    assert not matches_reference(f"{slug}.part2.section9.subsection1", reference)


@pytest.mark.parametrize(
    "query",
    [
        "Section 33(2)(a)(i)",
        "Section 33(2",
        "Section 33 paragraph ab",
        "Section 33 paragraph (ii)",
        "Sections 40-33",
        "Sections 1-21",
        "Section 33(2)-34(2)",
        "Section 33 of the Trade Disputes Act",
    ],
)
def test_unsupported_reference_is_never_silently_truncated(query: str) -> None:
    parsed = parse_section_reference(query)
    assert parsed.error
    assert parsed.reference is None


@pytest.mark.parametrize(
    "query", ["privacy", "Which section covers privacy?", "freedom of expression"]
)
def test_topic_queries_do_not_become_references(query: str) -> None:
    parsed = parse_section_reference(query)
    assert parsed.error is None
    assert parsed.reference is None


def test_direct_section_paragraph_and_plain_section() -> None:
    assert parse_section_reference("Section 38(a)").reference == SectionReference(
        "38", None, "a"
    )
    assert parse_section_reference(
        "What does Section 37 say?"
    ).reference == SectionReference("37")


def test_comma_after_citation_can_introduce_prose() -> None:
    assert parse_section_reference(
        "Section 7, which establishes elected councils, is historical wording."
    ).reference == SectionReference("7")
    assert parse_section_reference("Section 7, subsection foo").error


def test_other_instrument_check_is_scoped_to_citation() -> None:
    parsed = parse_section_reference(
        "A state law governs the councils, subject to section 8 of this Constitution."
    )
    assert parsed.reference == SectionReference("8")
    assert parse_section_reference("Section 8 of the Trade Disputes Act").error


def test_prose_mode_ignores_unnumbered_section_mentions() -> None:
    parsed = parse_section_reference(
        "Section 7's guarantee is subject to this section, meaning Section 8.",
        prose=True,
    )
    assert [reference.section for reference in parsed.references] == ["7", "8"]
    assert parsed.error is None
    assert parse_section_reference("Section (33)").error


def test_prose_mode_keeps_numeric_citations_without_treating_prose_as_a_list() -> None:
    parsed = parse_section_reference(
        "Section 7 guarantees councils, and a state law sets their functions. "
        "It is subject to Section 8 and this section also covers elections.",
        prose=True,
    )
    assert [reference.section for reference in parsed.references] == ["7", "8"]
    assert parsed.error is None
    assert parse_section_reference(
        "Section 33 of the Trade Disputes Act", prose=True
    ).error
    assert parse_section_reference("Section 33(2", prose=True).error


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Sections 33, 37 and 39", ["33", "37", "39"]),
        ("Sections 33–40", [str(number) for number in range(33, 41)]),
        ("Section 33(1)–(3)", ["33(1)", "33(2)", "33(3)"]),
        ("Section 33(2)(a)–(c)", ["33(2)(a)", "33(2)(b)", "33(2)(c)"]),
        ("Section 33 and Section 37", ["33", "37"]),
        ("Sections 33, 33", ["33", "33"]),
    ],
)
def test_lists_and_ranges_keep_input_order(query: str, expected: list[str]) -> None:
    parsed = parse_section_reference(query)
    assert parsed.error is None
    assert [
        reference.citation.removeprefix("Section ") for reference in parsed.references
    ] == expected


@pytest.mark.parametrize(
    "query,slug,number",
    [
        ("section 9 of the ACJA", "acja-2015", "9"),
        ("ACJA s.9", "acja-2015", "9"),
        ("ACJA 2015: s9", "acja-2015", "9"),
        ("Section 9, ACJA 2015", "acja-2015", "9"),
        ("Administration of Criminal Justice Act 2015 section 9", "acja-2015", "9"),
        ("section 9 under the ACJ Act", "acja-2015", "9"),
        ("s.29 Police Act", "police-act-2020", "29"),
        ("Nigeria Police Act 2020 section 49", "police-act-2020", "49"),
        ("Nigerian Police Act section 9", "police-act-2020", "9"),
        ("section 35 of the Constitution", "constitution-1999", "35"),
        ("1999 Constitution s.35", "constitution-1999", "35"),
        ("Constitution,\n1999 s.35", "constitution-1999", "35"),
    ],
)
def test_qualified_law_aliases(query: str, slug: str, number: str) -> None:
    for prose in (False, True):
        parsed = parse_section_reference(query, prose=prose)
        assert parsed.error is None
        assert parsed.reference == SectionReference(number, instrument_slug=slug)


@pytest.mark.parametrize(
    "query",
    [
        "Section 41 of the Joint Revenue Board of Nigeria (Establishment) Act, 2025",
        "Section 41, Joint Revenue Board Act 2025",
        "Section 41 of the JRB Act",
        "Joint Revenue Board of Nigeria (Establishment) Act 2025 s.41",
    ],
)
def test_jrb_reference_cannot_match_the_constitution(query: str) -> None:
    slug = "joint-revenue-board-of-nigeria-establishment-act-2025"
    for prose in (False, True):
        parsed = parse_section_reference(query, prose=prose)
        assert parsed.error is None
        reference = parsed.reference
        assert reference is not None
        assert reference == SectionReference("41", instrument_slug=slug)
        assert matches_reference(f"{slug}.part6.section41", reference)
        assert not matches_reference("constitution-1999.chapter4.section41", reference)


@pytest.mark.parametrize(
    "query",
    [
        "Trade Disputes Act s.9",
        "Section 9, Trade Disputes Act",
        "s.9 of the Trade Disputes Act",
        "Police Act 2015 s.9",
        "s.9 ACJA 2020",
        "ACJA s.9 of Police Act",
        "Sections 9 of ACJA and 49 of Police Act",
        "Lagos Police Act s.9",
        "FOIA s.9",
        "s.9 of the FOIA",
        "Section 41 of the Joint Revenue Board of Nigeria (Establishment) Act, 2024",
        "Section 41 of the Joint Revenue Board of Nigeria (Amendment) Act, 2025",
        "Section 41, Joint Revenue Board of Nigeria (Amendment) Act, 2025",
    ],
)
def test_unrecognised_or_conflicting_laws_never_fall_back(query: str) -> None:
    for prose in (False, True):
        parsed = parse_section_reference(query, prose=prose)
        assert parsed.error
        assert not parsed.references


def test_qualified_groups_ranges_and_sentence_boundaries() -> None:
    parsed = parse_section_reference("Sections 9-11 of ACJA and Police Act s.49")
    assert parsed.error is None
    assert [(ref.instrument_slug, ref.section) for ref in parsed.references] == [
        ("acja-2015", "9"),
        ("acja-2015", "10"),
        ("acja-2015", "11"),
        ("police-act-2020", "49"),
    ]
    assert parse_section_reference("ACJA s.9 and Constitution s.9").references == (
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("9"),
    )
    # A passing mention elsewhere does not turn a bare reference into an Act.
    assert parse_section_reference(
        "Does Section 37 relate to ACJA?"
    ).reference == SectionReference("37")
    assert parse_section_reference("ACJA s.9. Section 37.", prose=True).references[
        -1
    ] == SectionReference("37")


def test_source_default_never_overwrites_an_explicit_law() -> None:
    assert parse_section_reference(
        "Section 35 of the Constitution", default_instrument_slug="acja-2015"
    ).reference == SectionReference("35")
    assert parse_section_reference(
        "Section 9", default_instrument_slug="acja-2015"
    ).reference == SectionReference("9", instrument_slug="acja-2015")


def test_repeated_markers_each_use_the_explicit_or_default_law() -> None:
    assert parse_section_reference("ACJA s.9 and s.10").references == (
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("10"),
    )
    assert parse_section_reference("s.9 of ACJA, s.10 of Police Act").references == (
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("10", instrument_slug="police-act-2020"),
    )
    assert parse_section_reference("s.9 ACJA, s.10").references == (
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("10"),
    )


@pytest.mark.parametrize("prose", [False, True])
@pytest.mark.parametrize(
    "query",
    [
        "section 33 of the Lagos State ACJL",
        "section 33 under the Lagos State Administration of Criminal Justice Law",
        "Lagos State ACJL section 33",
    ],
)
def test_state_procedure_law_cannot_become_a_constitution_reference(
    query: str, prose: bool
) -> None:
    parsed = parse_section_reference(query, prose=prose)
    assert parsed.error
    assert parsed.references == ()


@pytest.mark.parametrize("prose", [False, True])
def test_new_section_marker_resets_to_default_law(prose: bool) -> None:
    parsed = parse_section_reference(
        "section 9 of the ACJA and section 35", prose=prose
    )
    assert parsed.error is None
    assert parsed.references == (
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("35"),
    )
    # An unmarked continuation stays within its explicitly named group.
    assert parse_section_reference("ACJA sections 9 and 10").references == (
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("10", instrument_slug="acja-2015"),
    )
