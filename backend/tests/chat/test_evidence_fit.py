from types import SimpleNamespace

from app.chat.worker import _fit_prompt


def _item(identifier: str, size: int) -> SimpleNamespace:
    return SimpleNamespace(
        evidence_id=identifier,
        authoritative_text=identifier + "x" * size,
        instrument_slug="constitution-1999",
        canonical_path=f"constitution-1999.section{identifier}",
        citation=f"Section {identifier}",
        instrument_title="Constitution",
        instrument_short_title="Constitution",
        instrument_type="constitution",
        title=None,
        ancestor_citations=[],
        legal_status="historical",
        edition_label="Historical",
    )


BASE = {"question": "q", "previous_question": None, "conversation_context": []}


def test_oversized_packets_drop_lowest_ranked_matches_before_context() -> None:
    selected = [_item("E1", 3000), _item("E2", 3000), _item("E3", 3000)]
    context = [_item("E4", 3000), _item("E5", 3000)]

    kept, kept_context, _, size = _fit_prompt(selected, context, BASE, 7000)

    assert size <= 7000
    assert kept_context == []
    assert [item.evidence_id for item in kept] == ["E1", "E2"]


def test_fitting_packets_are_left_untouched() -> None:
    selected = [_item("E1", 100), _item("E2", 100)]
    context = [_item("E3", 100)]

    kept, kept_context, _, size = _fit_prompt(selected, context, BASE, 24000)

    assert kept == selected
    assert kept_context == context
    assert size < 24000


def test_best_match_is_never_dropped_even_when_it_alone_is_too_large() -> None:
    kept, kept_context, _, size = _fit_prompt(
        [_item("E1", 9000), _item("E2", 100)], [_item("E3", 100)], BASE, 5000
    )

    assert [item.evidence_id for item in kept] == ["E1"]
    assert kept_context == []
    assert size > 5000


def test_low_ranked_matches_go_before_companion_context() -> None:
    selected = [_item(f"E{n}", 1000) for n in range(1, 7)]
    context = [_item("E7", 1000)]

    kept, kept_context, _, size = _fit_prompt(selected, context, BASE, 7000)

    assert size <= 7000
    assert [item.evidence_id for item in kept] == ["E1", "E2", "E3", "E4"]
    assert kept_context == context
