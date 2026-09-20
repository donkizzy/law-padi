import pytest

from app.ingestion.retrieval import build_retrieval_documents
from app.ingestion.structure_validators import (
    extractor_disagreement_issue,
    validate_document_graph,
)
from app.legal.instrument_parser import (
    ConstitutionParser,
    DocumentGraph,
    DocumentNode,
    instrument_parser_for,
    parse_instrument_pages,
)
from app.legal.parser import SourcePage as ParserSourcePage


def _node(path: str, **overrides) -> DocumentNode:
    values = {
        "kind": "section",
        "number": "37",
        "heading": None,
        "canonical_path": path,
        "sort_key": "00037",
        "parent_path": None,
        "page_start": 1,
        "page_end": 1,
        "text": "Right to privacy.",
        "parser_confidence": 0.95,
        "parser_metadata": {"source_spans": [{"page": 1}]},
    }
    values.update(overrides)
    return DocumentNode(**values)


def test_instrument_parser_registry_supports_constitution_only() -> None:
    assert isinstance(instrument_parser_for("constitution"), ConstitutionParser)
    with pytest.raises(ValueError, match="No instrument parser"):
        instrument_parser_for("regulation")


def test_constitution_parser_returns_document_graph() -> None:
    pages = [
        ParserSourcePage(page_number=1, text="CHAPTER IV Fundamental Rights"),
        ParserSourcePage(page_number=1, text="37. Right to private and family life"),
    ]
    graph = parse_instrument_pages(
        instrument_type="constitution", instrument_slug="constitution-1999", pages=pages
    )

    assert isinstance(graph, DocumentGraph)
    assert graph.instrument_type == "constitution"
    assert any(node.kind == "section" for node in graph.nodes)


def test_validators_flag_duplicates_missing_parents_and_punctuation() -> None:
    graph = DocumentGraph(
        instrument_slug="constitution-1999",
        instrument_type="constitution",
        nodes=[
            _node("constitution.section37"),
            _node("constitution.section37", text="Duplicate path"),
            _node(
                "constitution.section37.subsection1",
                kind="subsection",
                number="1",
                parent_path="constitution.section-missing",
                text="Unbalanced (text",
            ),
        ],
    )

    issues = validate_document_graph(graph)
    types = {issue.issue_type for issue in issues}

    assert "duplicate_canonical_path" in types
    assert "missing_parent" in types
    assert "unbalanced_punctuation" in types
    assert any(issue.blocking for issue in issues)


def test_toc_without_sections_is_blocking() -> None:
    graph = DocumentGraph(
        instrument_slug="constitution-1999",
        instrument_type="constitution",
        nodes=[],
    )
    issues = validate_document_graph(
        graph, page_roles=[{"page_number": 1, "role": "table_of_contents"}]
    )

    assert any(
        issue.issue_type == "toc_reconciliation" and issue.blocking for issue in issues
    )


def test_extractor_disagreement_flags_sharp_gaps() -> None:
    issue = extractor_disagreement_issue(
        canonical_path="constitution.section37",
        native_confidence=0.95,
        ocr_confidence=0.4,
    )
    assert issue is not None
    assert issue.issue_type == "extractor_disagreement"
    assert not issue.blocking

    assert (
        extractor_disagreement_issue(
            canonical_path="constitution.section37",
            native_confidence=0.9,
            ocr_confidence=0.85,
        )
        is None
    )


def test_retrieval_builder_rejects_non_english() -> None:
    with pytest.raises(ValueError, match="English-only"):
        build_retrieval_documents(
            release_version="draft-x",
            entries=[],
            versions_by_id={},
            provisions_by_id={},
            language="yo",
        )


def test_validators_flag_numbering_gaps_cross_page_and_missing_spans() -> None:
    graph = DocumentGraph(
        instrument_slug="constitution-1999",
        instrument_type="constitution",
        nodes=[
            _node(
                "constitution.section37",
                number="37",
                page_start=1,
                page_end=1,
            ),
            _node(
                "constitution.section40",
                number="40",
                page_start=2,
                page_end=2,
            ),
            _node(
                "constitution.section41",
                number="41",
                page_start=3,
                page_end=5,
                text="",
            ),
            _node(
                "constitution.section42",
                number="42",
                page_start=6,
                page_end=6,
                parser_metadata={},
            ),
        ],
    )

    issues = validate_document_graph(graph)
    by_type = {issue.issue_type for issue in issues}

    assert "numbering_gap" in by_type
    assert "cross_page_join_empty" in by_type
    assert "source_span_coverage" in by_type
    assert not any(
        issue.blocking for issue in issues if issue.issue_type == "numbering_gap"
    )


def test_toc_with_parsed_sections_raises_no_issue() -> None:
    graph = DocumentGraph(
        instrument_slug="constitution-1999",
        instrument_type="constitution",
        nodes=[_node("constitution.section37", number="37")],
    )

    issues = validate_document_graph(
        graph, page_roles=[{"page_number": 1, "role": "table_of_contents"}]
    )

    assert not [issue for issue in issues if issue.issue_type == "toc_reconciliation"]


def test_parsed_provisions_from_graph_falls_back_for_unknown_kind() -> None:
    from app.legal.enums import ProvisionKind
    from app.legal.instrument_parser import parsed_provisions_from_graph

    graph = DocumentGraph(
        instrument_slug="constitution-1999",
        instrument_type="constitution",
        nodes=[_node("constitution.mystery", kind="preamble")],
    )

    provisions = parsed_provisions_from_graph(graph)

    assert provisions[0].kind == ProvisionKind.SECTION
    assert provisions[0].canonical_path == "constitution.mystery"
