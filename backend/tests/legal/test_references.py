import pytest

from app.legal.references import SectionReference, parse_section_reference


@pytest.mark.parametrize(
    "query",
    [
        "Section 33(2)(a)",
        "s.33(2)(a)",
        "§33(2)(a)",
        "Section 33 subsection 2 paragraph a",
        "section 33, subsection (2), paragraph (a)",
        "What does Section 33(2)(a) say?",
    ],
)
def test_reference_formats_resolve_to_identical_hierarchy(query: str) -> None:
    parsed = parse_section_reference(query)
    assert parsed.error is None
    assert parsed.reference == SectionReference("33", "2", "a")
    assert parsed.reference.suffix == ".section33.subsection2.paragrapha"


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
        "Section 33 of the Evidence Act",
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
    assert parse_section_reference("Section 8 of the Evidence Act").error


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
    assert parse_section_reference("Section 33 of the Evidence Act", prose=True).error
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
