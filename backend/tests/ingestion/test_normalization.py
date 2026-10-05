from app.ingestion.normalization import legacy_hyphen_loss_matches, normalize_page_text
from app.ingestion.text_alignment import aligned_source_spans, unique_text_range


def test_normalization_preserves_hard_hyphens_and_legal_markers() -> None:
    result = normalize_page_text("(1) Attorney-\nGeneral;\n(a) un-\naudited accounts.")
    assert result.text == "(1) Attorney-\nGeneral;\n(a) un-\naudited accounts."


def test_whitespace_cleanup_is_audited_and_idempotent() -> None:
    original = "  13.\u00a0Each  Secretariat ;\n\n(a) Accounts :  "
    result = normalize_page_text(original)
    assert result.text == "13. Each Secretariat;\n(a) Accounts:"
    assert result.changes == [
        "nonbreaking_spaces",
        "line_whitespace",
        "spaces_before_punctuation",
    ]
    assert "".join(result.text.split()) == "".join(original.split())
    assert normalize_page_text(result.text).changes == []


def test_alignment_rejects_ambiguous_or_substantive_changes() -> None:
    assert unique_text_range("shall submit", "shall submit; shall submit") is None
    assert unique_text_range("submit to", "su bmit t") is None
    assert unique_text_range("31st", "31\nst") == (0, 5)


def test_repeated_text_requires_unique_parent_context() -> None:
    source = "Section 1. Pay two-\nthirds.\nSection 2. Pay two-\nthirds."
    target = "Pay two-thirds."
    assert unique_text_range(target, source) is None
    match = unique_text_range(target, source, context="Section 2. Pay two-thirds.")
    assert match is not None
    assert source[match[0] : match[1]] == "Pay two-\nthirds."
    aligned = aligned_source_spans(
        target, [{"text": source}], context="Section 2. Pay two-thirds."
    )
    assert aligned is not None
    assert aligned[0]["source_text_start"] == match[0]


def test_legacy_hyphen_restoration_cannot_change_words_or_other_punctuation() -> None:
    assert legacy_hyphen_loss_matches("AttorneyGeneral", "Attorney-\nGeneral")
    assert not legacy_hyphen_loss_matches("Attorney General", "Attorney-General")
    assert not legacy_hyphen_loss_matches("twothirds", "two-\nthirds;")
    assert not legacy_hyphen_loss_matches("two thirds", "one-\nthird")


def test_alignment_retains_context_and_bounds_when_narrowing_span_text() -> None:
    bbox = {"x0": 1, "y0": 2, "x1": 3, "y1": 4}
    original = "12. Previous item.\n13. Each Secretariat shall su bmit.\n14. Next item."
    spans = aligned_source_spans(
        "Each Secretariat shall submit.", [{"text": original, "bbox": bbox}]
    )
    assert spans is not None
    assert len(spans) == 1
    assert spans[0]["text"] == "Each Secretariat shall su bmit."
    assert spans[0]["original_span_text"] == original
    assert spans[0]["bbox"] == bbox
    assert (
        original[spans[0]["source_text_start"] : spans[0]["source_text_end"]]
        == spans[0]["text"]
    )
