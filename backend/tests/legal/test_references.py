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
        "Section 33-37",
        "Sections 33 and 37",
        "Section 33, 37",
        "Section 33 paragraph ab",
        "Section 33 and Section 37",
        "Section 33 paragraph (ii)",
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
