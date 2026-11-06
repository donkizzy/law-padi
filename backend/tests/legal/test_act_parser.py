"""Act structure regression fixtures contain synthetic wording, not legal advice."""

import pytest

from app.ingestion.structure_validators import validate_document_graph
from app.legal.act_parser import (
    ACT_PARSER_VERSION,
    parse_act_pages,
    parse_order_rules_pages,
    parse_scheduled_code_pages,
)
from app.legal.citations import rules_citation
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


def test_title_block_after_arrangement_and_subsidiary_legislation_back_matter() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. First heading.\n2. Short title.\n"
                "CHAPTER L5\nTEST ACT\nAn Act to do a synthetic thing.\n[1978 No. 6.]\n"
                "1. Synthetic first section.\n(1) A synthetic clause.\n2. Short title\nThis Act may be cited as the Test Act.\n"
                "TEST ACT\nSUBSIDIARY LEGISLATION\nNo Subsidiary",
            )
        ],
    )
    nodes = graph.node_by_path
    assert nodes["test-act.section2"].heading == "Short title."
    assert nodes["test-act.section2"].text == "This Act may be cited as the Test Act."


def test_ocr_split_numbers_and_roman_first_subsection_are_read_and_flagged() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "ARRANGEMENT OF SECTIONS\n1. Manner of payment.\n2. Advances.\n"
                "3. Records.\n4 . Offences.\n1 0. Short title.\n",
            ),
            SourcePage(
                2,
                "1. Manner of payment\n(I) Wages are paid in legal tender.\n"
                "2. Advances\n(1) An advance is limited.\n"
                "3. Records\nAn employer keeps records.\n",
            ),
        ],
    )
    issues = " ".join(graph.metadata["parser_issues"])
    # The arrangement is read through the "(I)" first subsection, so section 1
    # is a body section and not an arrangement repeat.
    assert "Arrangement repeats" not in issues
    assert graph.node_by_path["test-act.section1"].text.startswith("(I) Wages")

    pages = [
        SourcePage(
            1, "ARRANGEMENT OF SECTIONS\n73. Forced labour.\n7 4. Emergencies.\n"
        ),
        SourcePage(
            2,
            "73. Forced labour\n(1) A person shall not require forced labour.\n"
            "7 4. Emergencies\n(1) The Minister may make regulations.\n",
        ),
    ]
    split = parse_instrument_pages(
        instrument_type="act", instrument_slug="test-act", pages=pages
    )
    assert "test-act.section74" in split.node_by_path
    assert any(
        "read as section 74" in issue for issue in split.metadata["parser_issues"]
    )


def test_year_markers_split_schedule_letters_and_outline_items_stay_text() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(1, "ARRANGEMENT OF SECTIONS\n1. Pensions.\n2. Short title.\n"),
            SourcePage(
                2,
                "1. Pensions\n(1) Benefits are paid under the Pension Reform Act,\n"
                "2004. This line is a wrapped margin note year.\n"
                "2. Short title\nThis Act may be cited as the Test Act.\n"
                "SCHEDULES Section 9 (1)(d)\nFIRST S CHEDULE\nLIST OF DISEASES\n"
                "1. Diseases Caused by Agents\n1.1. Chemical Agents\n"
                "1.1.1 Diseases caused by lead.\n2. Target Organ Systems\n",
            ),
        ],
    )
    nodes = graph.node_by_path
    issues = " ".join(graph.metadata["parser_issues"])
    assert "Year-like marker 2004" in issues
    assert "has a split letter" in issues
    assert "test-act.section3" not in nodes
    assert "SCHEDULES" not in (nodes["test-act.section2"].text or "")
    assert "1.1.1 Diseases caused by lead." in nodes["test-act.schedule1.item1"].text
    assert "test-act.schedule1.item2" in nodes


def test_misprinted_enacting_clause_still_starts_the_body() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(1, "ARRANGEMENT OF SECTIONS\n1. Objective\n2. Citation\n"),
            SourcePage(
                2,
                "ENECTED by the National Assembly of the Federal Republic of Nigeria\n"
                "1. The objective of this Act is stated here.\n"
                "2. This Act may be cited as the Test Act.\n",
            ),
        ],
    )
    nodes = graph.node_by_path
    assert "test-act.section1" in nodes
    assert "test-act.section2" in nodes


def test_wrapped_schedule_reference_ending_a_sentence_is_not_a_heading() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(1, "ARRANGEMENT OF SECTIONS\n1. Relief\n2. Citation\n"),
            SourcePage(
                2,
                "ENACTED by the National Assembly\n"
                "1. Relief is given in place of any allowances under Part I of the\n"
                "First Schedule.\n"
                "2. This Act may be cited as the Test Act.\n"
                "SCHEDULES\nFirst Schedule\nRates\n1. Rate one.\n",
            ),
        ],
    )
    nodes = graph.node_by_path
    assert "test-act.section2" in nodes
    assert "First Schedule." in nodes["test-act.section1"].text
    assert "test-act.schedule1" in nodes


def test_chapters_spelled_in_words_and_late_arrangement_heading() -> None:
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug="test-act",
        pages=[
            SourcePage(
                1,
                "CHAPTER ONE - OBJECTIVE\n1. Objective\nCHAPTER TWO - TAX\n"
                "Part I - Imposition\n2. Imposition\nARRANGEMENT OF SECTIONS\n",
            ),
            SourcePage(
                2,
                "ENACTED by the National Assembly\nCHAPTER ONE - OBJECTIVE\n"
                "1. The objective is stated.\nCHAPTER TWO - TAX\nPart I - Imposition\n"
                "2. Tax is imposed.\n",
            ),
        ],
    )
    nodes = graph.node_by_path
    assert "test-act.chapter2.part1" in nodes
    sections = {n.number for n in nodes.values() if n.kind == "section"}
    assert sections == {"1", "2"}
    assert "Unresolved" not in " ".join(graph.metadata["parser_issues"])


CODE_CATALOGUE = {
    "enabling_heading": "Test Code Act (enabling provisions)",
    "enabling_titles": {"1": "Short title.", "2": "The Code."},
    "part_first_chapter": {"1": "1"},
    "stop_line": "Federal sections",
    "sections": {
        "1": "Interpretation.",
        "10A": "Added section.",
        "11": "Second section.",
    },
    "chapters": {"1": "Opening"},
    "parts": {"1": "Introductory"},
}


def test_scheduled_code_keeps_code_sections_apart_from_the_enabling_act() -> None:
    result = parse_scheduled_code_pages(
        [
            SourcePage(
                1,
                "1. Short title\nThis Act may be cited as the Test Code Act.\n2. The Code\nThe Code is set out in the Schedule.\nSCHEDULE\nThe Code\nPART 1\nIntroductory\nCHAPTER 1\nOpening\n1. Interpretation\nSynthetic wording ending here. l0A. Added section\n",
            ),
            SourcePage(
                2,
                "Synthetic added wording.\n7. A numbered line inside a section\n11. Second section\nLast wording.\nFederal sections\n3 4 5",
            ),
        ],
        "test-code",
        CODE_CATALOGUE,
    )
    paths = {node.canonical_path: node for node in result.nodes}
    assert "test-code.scheduleact.item1" in paths
    assert paths["test-code.scheduleact.item2"].kind == "schedule_item"
    assert paths["test-code.part1.chapter1.section1"].kind == "section"
    assert paths["test-code.part1.chapter1.section10a"].number == "10A"
    assert "numbered line" in (paths["test-code.part1.chapter1.section10a"].text or "")
    assert paths["test-code.part1.chapter1.section11"].text == "Last wording."
    assert not result.issues


def test_reviewed_titles_replace_an_unreadable_arrangement_and_gate_markers() -> None:
    result = parse_act_pages(
        [
            SourcePage(1, "ARRANGEMENT OF SECTIONS\n] Garbled.\nI2 Also garbled."),
            SourcePage(
                2,
                "ENACTED by the National Assembly\n1. First wording.\n5. A number that is not the next section.\n2. Second wording cited as the Test Act,\n2024.",
            ),
        ],
        "test-act",
        reviewed_titles={"1": "First.", "2": "Second."},
    )
    assert [node.number for node in result.nodes if node.kind == "section"] == [
        "1",
        "2",
    ]
    assert result.arrangement == {"1": "First.", "2": "Second."}
    assert not result.issues
    assert "not the next section" in (result.nodes[0].text or "")


def test_reviewed_titles_keep_restarted_form_numbering_as_wording() -> None:
    result = parse_act_pages(
        [
            SourcePage(
                1,
                "ENACTED by the National Assembly\n1. First wording.\nSCHEDULE\nFORM 1\n1. First form line.\nFORM 2\n1. Second form line.",
            )
        ],
        "test-act",
        reviewed_titles={"1": "First."},
    )
    assert not result.issues
    assert "Second form line" in (result.nodes[-1].text or "")


def test_orders_and_rules_keep_rule_numbers_unique_across_orders() -> None:
    catalogue = {
        "sections": {
            "Preamble.1": "Preamble",
            "I.1": "Citation",
            "I.2": "",
            "II": "Orders",
            "III.1": "Citation",
        },
        "parts": {"I": "Start", "II": "Orders", "III": "End"},
        "forms": {"1": "Notice"},
    }
    text = """Preamble
ORDER I—START
1. Citation
Preamble
1. The Court shall act.
ORDER I—START
1. These Rules apply.
3. This number is wording, not a rule.
2.—(a) First limb;
(b) Second limb.
(i) A roman clause stays inside (b).
ORDER II—ORDERS
The Court may make orders.
ORDER III—END
1. Last rule.
APPENDIX
A. SCHEDULE OF FEES
The fee is one hundred naira.
B. FORMS
FORM NO. 1
In the matter of an application.
MADE at Abuja"""
    result = parse_order_rules_pages(
        [SourcePage(page_number=1, text=text)], "test-rules", catalogue
    )
    assert result.issues == []
    nodes = {node.canonical_path: node for node in result.nodes}
    rule = nodes["test-rules.orderi.rule2"]
    assert rule.number == "I.2" and rule.heading is None
    assert "This number is wording" in str(nodes["test-rules.orderi.rule1"].text)
    assert "(i) A roman clause" in str(nodes["test-rules.orderi.rule2.paragraphb"].text)
    assert nodes["test-rules.orderii.rule0"].text == "The Court may make orders."
    assert nodes["test-rules.schedulea"].text == "The fee is one hundred naira."
    assert nodes["test-rules.scheduleb.item1"].heading == "Notice"
    assert "Abuja" not in str(nodes["test-rules.scheduleb.item1"].text)


@pytest.mark.parametrize(
    ("path", "citation"),
    [
        ("r.preamble.rule3.paragraphe", "Preamble, paragraph 3(e)"),
        ("r.orderii", "Order II"),
        ("r.orderiv.rule4.paragraphc", "Order IV Rule 4(c)"),
        ("r.orderxi.rule0", "Order XI"),
        ("r.schedulea", "Appendix A"),
        ("r.scheduleb.item2", "Appendix B, Form 2"),
        ("r.part1.section4", None),
        ("r.schedule1.item2", None),
    ],
)
def test_rules_are_cited_by_order_and_rule(path: str, citation: str | None) -> None:
    assert rules_citation(path) == citation
