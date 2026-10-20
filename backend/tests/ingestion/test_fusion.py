import uuid

from app.ingestion.pgvector_repository import fuse_rankings, section_key
from app.legal.models import RetrievalSegment


def _segment(canonical_path: str) -> RetrievalSegment:
    return RetrievalSegment(
        id=uuid.uuid4(),
        provision_version_id=uuid.uuid4(),
        canonical_path=canonical_path,
    )


def test_section_key_groups_sub_provisions_under_their_section() -> None:
    assert (
        section_key("constitution-1999.chapter4.section35.subsection4.paragraphb")
        == "constitution-1999.chapter4.section35"
    )
    assert (
        section_key("constitution-1999.chapter4.section35")
        == "constitution-1999.chapter4.section35"
    )
    assert (
        section_key("constitution-1999.chapter4.section35a.subsection1")
        == "constitution-1999.chapter4.section35a"
    )
    # Section 3 must not swallow Section 35.
    assert section_key("constitution-1999.chapter1.section3") != section_key(
        "constitution-1999.chapter4.section35"
    )
    assert (
        section_key("constitution-1999.schedule3.item1")
        == "constitution-1999.schedule3.item1"
    )


def test_fusion_keeps_one_row_per_section() -> None:
    subsection = _segment("constitution-1999.chapter4.section35.subsection4")
    section = _segment("constitution-1999.chapter4.section35")
    paragraph = _segment("constitution-1999.chapter4.section35.subsection1.paragraphc")
    privacy = _segment("constitution-1999.chapter4.section37")

    ranked = fuse_rankings(
        dense=[(subsection, 0.1), (section, 0.2), (paragraph, 0.3), (privacy, 0.4)],
        top_k=5,
    )

    # The best-scoring row stands for its section, so its precise wording leads.
    assert [item.segment for item in ranked] == [subsection, privacy]


def test_lexical_weight_lets_dense_order_win() -> None:
    dense_first = _segment("constitution-1999.chapter4.section37")
    keyword_first = _segment("constitution-1999.chapter5.section129")
    others = [
        _segment(f"constitution-1999.chapter6.section{n}") for n in range(200, 218)
    ]
    dense = [
        (dense_first, 0.1),
        *((segment, 0.5) for segment in others),
        (keyword_first, 0.9),
    ]
    lexical = [(keyword_first, 0.9)]

    # At full weight, one keyword hit lifts a weak dense match into first place.
    full = fuse_rankings(dense=dense, lexical=lexical, top_k=3)
    assert full[0].segment is keyword_first

    reduced = fuse_rankings(dense=dense, lexical=lexical, top_k=30, lexical_weight=0.15)
    assert reduced[0].segment is dense_first
    keyword = next(item for item in reduced if item.segment is keyword_first)
    assert (keyword.dense_rank, keyword.lexical_rank) == (20, 1)


def test_without_dense_ranking_topic_order_beats_keyword_hits() -> None:
    qualification = _segment("constitution-1999.chapter6.part1.section131")
    disqualification = _segment("constitution-1999.chapter6.part1.section137")
    disqualification_detail = _segment(
        "constitution-1999.chapter6.part1.section137.subsection1.paragraphe"
    )
    keyword = _segment("constitution-1999.chapter6.part1.section146")

    ranked = fuse_rankings(
        lexical=[(keyword, 0.9), (disqualification_detail, 0.1)],
        topics=[(qualification, 2.5), (disqualification, 2.5)],
        top_k=3,
        lexical_weight=0.15,
    )

    # A keyword hit on a long section's paragraph must not outrank the
    # curated first choice when there is no dense ranking to break the tie.
    assert [item.segment for item in ranked] == [
        qualification,
        disqualification,
        keyword,
    ]


def test_topic_boost_lets_dense_order_pick_among_topic_sections() -> None:
    establishment = _segment("constitution-1999.chapter6.part3.section214")
    control = _segment("constitution-1999.chapter6.part3.section215")
    establishment_detail = _segment(
        "constitution-1999.chapter6.part3.section214.subsection2"
    )

    ranked = fuse_rankings(
        dense=[(establishment_detail, 0.1), (control, 0.2)],
        # Curated order lists control first; dense ranking should decide.
        topics=[(control, 2.5), (establishment, 2.5)],
        top_k=2,
    )

    # The boost reaches the subsection dense search matched, not only the
    # whole-section row the topic names.
    assert [item.segment for item in ranked] == [establishment_detail, control]


def test_mixed_law_ranking_limits_each_instrument_and_prioritises_rights() -> None:
    acts = [_segment(f"acja-2015.section{n}") for n in range(9, 15)]
    constitution = [
        _segment(f"constitution-1999.chapter4.section{n}") for n in (35, 37, 45, 46)
    ]
    police = _segment("police-act-2020.section49")
    candidates = [(row, 0.1) for row in [*acts, *constitution, police]]
    ranked = fuse_rankings(
        dense=candidates,
        topics=[(constitution[0], 2.5)],
        top_k=6,
        prefer_constitution=True,
        balance_instruments=True,
    )
    assert ranked[0].segment == constitution[0]
    assert len(ranked) == 6
    assert (
        sum(item.segment.canonical_path.startswith("acja-2015.") for item in ranked)
        == 3
    )
    assert (
        sum(
            item.segment.canonical_path.startswith("constitution-1999.")
            for item in ranked
        )
        <= 3
    )
    # Same-numbered sections of different laws remain separate identities.
    same_number = _segment("police-act-2020.section9")
    assert len(fuse_rankings(dense=[(acts[0], 0.1), (same_number, 0.2)], top_k=6)) == 2


def test_single_instrument_keeps_all_six_results() -> None:
    rows = [_segment(f"constitution-1999.section{n}") for n in range(25, 31)]
    ranked = fuse_rankings(
        dense=[(row, 0.1) for row in rows], top_k=6, prefer_constitution=True
    )
    assert [item.segment for item in ranked] == rows
    # Publishing other laws does not truncate a single-law candidate list.
    assert (
        len(
            fuse_rankings(
                dense=[(row, 0.1) for row in rows], top_k=6, balance_instruments=True
            )
        )
        == 6
    )


def test_demotion_is_qualified_by_instrument() -> None:
    act = _segment("police-act-2020.section89")
    constitution = _segment("constitution-1999.section89")
    ranked = fuse_rankings(
        dense=[(constitution, 0.1), (act, 0.2)],
        top_k=6,
        demoted={"constitution-1999:89"},
    )
    assert ranked[0].segment == act


def test_constitution_candidates_are_not_capped_by_act_membership() -> None:
    constitution = [_segment(f"constitution-1999.section{n}") for n in range(25, 31)]
    act = _segment("acja-2015.section9")
    ranked = fuse_rankings(
        dense=[*((row, 0.1) for row in constitution), (act, 0.9)],
        top_k=6,
        balance_instruments=True,
    )
    assert [row.segment for row in ranked] == constitution


def test_unmatched_or_weak_rights_candidate_is_not_promoted() -> None:
    acts = [_segment(f"acja-2015.section{n}") for n in range(9, 15)]
    unrelated = _segment("constitution-1999.section44")
    candidates = [(row, 0.1) for row in [*acts, unrelated]]
    ranked = fuse_rankings(
        dense=candidates, top_k=6, prefer_constitution=True, balance_instruments=True
    )
    assert ranked[0].segment == acts[0]
    assert len(ranked) == 6
    # Even a topic candidate cannot leap from outside the requested window.
    ranked = fuse_rankings(
        dense=candidates,
        topics=[(unrelated, 0.01)],
        top_k=2,
        prefer_constitution=True,
        balance_instruments=True,
    )
    assert ranked[0].segment == acts[0]


def test_competitive_matched_constitution_can_lead_an_act_answer() -> None:
    act = _segment("acja-2015.section9")
    privacy = _segment("constitution-1999.section37")
    ranked = fuse_rankings(
        dense=[(act, 0.1), (privacy, 0.2)],
        topics=[(act, 2.5), (privacy, 1.5)],
        top_k=6,
        prefer_constitution=True,
        balance_instruments=True,
    )
    assert ranked[0].segment == privacy
