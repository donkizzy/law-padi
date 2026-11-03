"""Act structure regression fixtures contain synthetic wording, not legal advice."""

import pytest

from app.ingestion.structure_validators import validate_document_graph
from app.legal.act_parser import ACT_PARSER_VERSION
from app.legal.instrument_parser import parse_instrument_pages
from app.legal.parser import SourcePage
from app.legal.topics import section_title


def test_parts_arrangement_cross_page_text_and_roman_clauses() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\nPART I - PRELIMINARY\n1. First heading.\n2. Interpretation.\nPART II - POWERS\n3. Third heading.",
            ),
            SourcePage(
                3,
                "ENACTED by the National Assembly\nPART I - PRELIMINARY\n1. First heading.\n(1) Synthetic first clause.\n(a) Synthetic paragraph:\n(i) nested first Roman clause;\n(ii) nested second Roman clause.\n(2) Synthetic second clause.\n2. Interpretation.\nIn this Act, test means a synthetic fixture.",
            ),
            SourcePage(
                4,
                "The interpretation text continues on this page.\nPART II - POWERS\n3. A synthetic third section.",
            ),
        ],
    )
    nodes = graph.node_by_path
    assert graph.parser_version == ACT_PARSER_VERSION
    assert nodes["test-act.part1.section1"].heading == "First heading."
    assert nodes["test-act.part1.section1.subsection1.paragrapha"].text.endswith(
        "(ii) nested second Roman clause."
    )
    assert "test-act.part1.section1.subsection1.paragraphi" not in nodes
    assert nodes["test-act.part1.section2"].page_start == 3
    assert nodes["test-act.part1.section2"].page_end == 4
    assert nodes["test-act.part2.section3"].text == "A synthetic third section."
    assert all(
        node.parser_metadata["parser_version"] == ACT_PARSER_VERSION
        for node in graph.nodes
    )
    assert not [
        issue
        for issue in validate_document_graph(graph)
        if issue.issue_type == "act_arrangement_reconciliation"
    ]


def test_schedules_do_not_become_sections_and_assent_is_excluded() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. First heading.\nENACTED by the National Assembly\n1. Synthetic section text.\nFIRST SCHEDULE - FORMS\nIntroductory schedule text.\n1. First form.\n(i) Roman form clause.\n2. Second form.\nI ASSENT\n2. This is an authentication sheet, not another section.",
            )
        ],
    )
    nodes = graph.node_by_path
    assert nodes["test-act.schedule1"].text == "Introductory schedule text."
    assert (
        nodes["test-act.schedule1.item1"].text == "First form.\n(i) Roman form clause."
    )
    assert nodes["test-act.schedule1.item2"].text == "Second form."
    assert [node.number for node in graph.nodes if node.kind == "section"] == ["1"]


def test_missing_arrangement_sections_are_blocking_and_never_synthesized() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. First.\n2. Second.\n3. Third.\nENACTED by the National Assembly\n1. First body text.\n3. Third body text.",
            )
        ],
    )
    issues = [
        issue
        for issue in validate_document_graph(graph)
        if issue.issue_type == "act_arrangement_reconciliation"
    ]
    assert len(issues) == 1 and issues[0].blocking
    assert issues[0].evidence["missing_sections"] == ["2"]
    assert not any(node.number == "2" for node in graph.nodes)


def test_arrangement_only_never_becomes_authoritative_text() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[SourcePage(1, "ARRANGEMENT OF SECTIONS\n1. First.\n2. Second.")],
    )
    assert not graph.nodes
    assert any(issue.blocking for issue in validate_document_graph(graph))


def test_repeated_markers_are_visible_to_review_instead_of_overwriting_text() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. First.\nENACTED by the National Assembly\n1. Original text.\n1. Repeated marker text.",
            )
        ],
    )
    assert "Repeated marker" in graph.node_by_path["test-act.section1"].text
    assert any(
        issue.issue_type == "act_arrangement_reconciliation" and issue.blocking
        for issue in validate_document_graph(graph)
    )


@pytest.mark.parametrize(
    "slug,number,title",
    [
        ("acja-2015", "9", "Search of arrested suspect"),
        ("police-act-2020", "49", "Power to stop and search"),
    ],
)
def test_titles_and_expected_counts_are_specific_to_the_act(
    slug: str, number: str, title: str
) -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug=slug,
        pages=[SourcePage(1, f"PART II - POWERS\n{number}. (1) Synthetic body text.")],
    )
    assert graph.node_by_path[f"{slug}.part2.section{number}"].heading == title
    assert section_title(f"{slug}.part2.section{number}.subsection1", slug) == title
    assert section_title(f"{slug}.section{number}", "constitution-1999") is None
    assert len(graph.metadata["expected_sections"]) == (
        495 if slug == "acja-2015" else 142
    )
    assert any(
        issue.blocking
        for issue in validate_document_graph(graph)
        if issue.issue_type == "act_arrangement_reconciliation"
    )


def test_catalogue_paths_cannot_escape_the_data_directory() -> None:
    assert (
        section_title("../constitution-1999.section37", "../constitution-1999") is None
    )


def test_scan_punctuation_preserves_numbers_and_plural_schedule_boundary() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n49. Search.\n_ ENACTED by the National Assembly\nPART I - POWERS\n: 49, (1) Exact synthetic text.\nChapter IV\nreference continues here.\nSCHEDULES\n1. Form text.",
            )
        ],
    )
    assert (
        graph.node_by_path["test-act.part1.section49"].text
        == "(1) Exact synthetic text.\nChapter IV\nreference continues here."
    )
    assert not any(node.kind == "chapter" for node in graph.nodes)
    assert graph.node_by_path["test-act.schedule1.item1"].text == "Form text."
    assert [node.number for node in graph.nodes if node.kind == "section"] == ["49"]
    assert graph.metadata["parser_issues"]


def test_oversized_heading_keeps_review_evidence_without_failing_storage() -> None:
    heading = "Long synthetic heading " * 40
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                f"ARRANGEMENT OF SECTIONS\n1. {heading}\nENACTED by the National Assembly\n1. Original body text.",
            )
        ],
    )
    section = graph.node_by_path["test-act.section1"]
    assert section.heading is None
    assert section.parser_metadata["unresolved_heading"] == heading.strip()
    assert section.text == "Original body text."
    assert any(issue.blocking for issue in validate_document_graph(graph))


def test_repeated_numbers_across_parts_block_reconciliation() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. Heading.\nENACTED by the National Assembly\nPART I - FIRST\n1. First text.\nPART II - SECOND\n1. Second text.",
            )
        ],
    )
    issue = next(
        issue
        for issue in validate_document_graph(graph)
        if issue.issue_type == "act_arrangement_reconciliation"
    )
    assert issue.blocking
    assert issue.evidence["repeated_section_numbers"] == ["1"]


def test_schedule_heading_with_inline_statutory_references_starts_schedule() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "1. Body text.\nFIRST SCHEDULE __ Section 153 (2), 376 (9)\nFORM NO. 1\n1. Form clause.",
            )
        ],
    )
    assert [node.number for node in graph.nodes if node.kind == "section"] == ["1"]
    assert graph.node_by_path["test-act.schedule1.item1"].text == "Form clause."


def test_catalogue_count_cannot_replace_a_missing_source_arrangement() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[SourcePage(1, "1. Complete synthetic body text.")],
    )
    graph.metadata["expected_sections"] = ["1"]
    issue = next(
        issue
        for issue in validate_document_graph(graph)
        if issue.issue_type == "act_arrangement_reconciliation"
    )
    assert issue.blocking
    assert issue.evidence["arrangement_missing"]
    assert issue.evidence["missing_arrangement_sections"] == ["1"]


def _synthetic_gazette_pages() -> list[SourcePage]:
    header = "A 7{n} 2023 No. 1 Synthetic Act, 2023"
    return [
        SourcePage(
            1,
            header.format(n=17)
            + "\nARRANGEMENT OF SECTIONS\nPART I - PRELIMINARY\n1. First heading.\n2. Second heading.\n"
            "3. Third heading.\nSCHEDULE\n" + header.format(n=17),
        ),
        SourcePage(
            2,
            header.format(n=18)
            + "\nENACTED by the National Assembly\nPART I - PRELIMINARY\n"
            "1.—(1) Synthetic first clause.\n(2) Synthetic second clause.\nSchedule\n"
            "2. Synthetic second section refers to Part XII of this Act\n"
            "Part XII of this Act with respect to the matter, and\n"
            + header.format(n=18),
        ),
        SourcePage(
            3,
            header.format(n=19)
            + "\n3.—(1) Synthetic third clause, applied as in section\n"
            "2 (1) of the Synthetic Act.\n"
            "2 (1) wrapped cross reference kept as text.\n[First Schedule.]\n"
            "SCHEDULE Section 3(2)\n1. Synthetic schedule item.\n"
            "I, certify, in accordance with the Authentication Act.\n"
            "4. Not a section.\n" + header.format(n=19),
        ),
    ]


def test_gazette_layout_headers_margin_notes_and_wrapped_references() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=_synthetic_gazette_pages(),
    )
    nodes = graph.node_by_path
    sections = [node.number for node in graph.nodes if node.kind == "section"]
    assert sections == ["1", "2", "3"]
    assert nodes["test-act.part1.section1.subsection1"].text.startswith(
        "(1) Synthetic first"
    )
    assert "test-act.part1.section1.subsection2" in nodes
    # Running page headers are dropped; margin note "Schedule" is not a heading.
    assert all("No. 1 Synthetic Act" not in (node.text or "") for node in graph.nodes)
    assert not any(
        node.kind == "schedule" and node.page_start == 2 for node in graph.nodes
    )
    # Wrapped "Part XII of this Act" is text; "2 (1)" after section 3 is text.
    assert not any(node.kind == "part" and node.number == "12" for node in graph.nodes)
    assert "wrapped cross reference kept as text." in (
        nodes["test-act.part1.section3"].text or ""
    )
    assert "[First Schedule.]" in (nodes["test-act.part1.section3"].text or "")
    # A capitalised heading with a section reference opens the schedule; the
    # certification line ends the body.
    assert nodes["test-act.schedule1.item1"].text == "Synthetic schedule item."
    assert not [n for n in graph.nodes if n.number == "4"]


def test_schedules_title_ordinals_and_source_spelling() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. First heading.\nENACTED by the National Assembly\n"
                "1. Synthetic section text.\nSCHEDULES\nEIGHT SCHEDULE\nSynthetic title\n"
                "1. Item.\nELEVENTH SCHEDULE\n1. Another item.",
            )
        ],
    )
    schedules = {n.number for n in graph.nodes if n.kind == "schedule"}
    assert schedules == {"8", "11"}
