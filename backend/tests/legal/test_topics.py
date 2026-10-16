import pytest

from app.ingestion.pgvector_repository import lexical_tsquery
from app.legal.topics import (
    companion_sections,
    match_topics,
    section_title,
    tokens,
    topic_sections,
)


@pytest.mark.parametrize(
    ("question", "section"),
    [
        ("Can police search my phone?", "37"),
        ("wetin constitution talk about police checking my phone", "37"),
        ("police detained me for 3 days without charge", "35"),
        ("can police arrest me in another state", "35"),
        ("can police torture a suspect", "34"),
        ("can I buy land in another state", "43"),
        ("can government take my land without paying", "44"),
        ("how old must you be to become president", "131"),
        ("A candidate asks about disqualification from the presidency", "137"),
        ("can the governor be sued while in office", "308"),
        ("is Nigeria a secular state", "10"),
        ("can the government stop me from leaving Nigeria", "41"),
        ("Which provision allows a citizen to renounce Nigerian citizenship?", "29"),
        ("how can I recall my senator", "69"),
        ("What does the presidential oath require?", "oath-president"),
    ],
)
def test_everyday_questions_lead_with_the_right_provision(
    question: str, section: str
) -> None:
    assert topic_sections(question)[0][0] == section


def test_specific_topics_outrank_umbrella_topics() -> None:
    slugs = [match.slug for match in match_topics("can I hold dual citizenship")]
    assert slugs[0] == "dual-citizenship"
    assert "citizenship" in slugs


def test_phrase_words_must_appear_close_together() -> None:
    # "state ... police" is not the state-police topic.
    assert "police" not in {
        match.slug for match in match_topics("can police arrest me in another state")
    }
    assert match_topics("can a state have its own police")[0].slug == "police"


def test_multi_word_matches_weigh_more_than_single_words() -> None:
    assert topic_sections("can police search my phone") == [("37", 2.5)]
    assert topic_sections("privacy") == [("37", 1.5)]
    assert topic_sections("what is the capital of France") == []


def test_tokens_normalise_plurals_and_verb_forms() -> None:
    assert tokens("Searches phones tapped killed married voting leaving") == [
        "search",
        "phon",
        "tap",
        "kill",
        "marry",
        "vot",
        "leav",
    ]
    assert tokens("Nigerian presidency disqualification") == [
        "nigeria",
        "president",
        "disqualify",
    ]


def test_section_titles_come_from_the_source_table_of_contents() -> None:
    assert (
        section_title("constitution-1999.chapter4.section37")
        == "Right to private and family life"
    )
    assert (
        section_title("constitution-1999.chapter4.section35.subsection4.paragrapha")
        == "Right to personal liberty"
    )
    assert (
        section_title("constitution-1999.chapter6.part1.section137")
        == "Disqualifications (President)"
    )
    assert section_title("constitution-1999.chapter4") == "Fundamental rights"
    assert section_title("constitution-1999.schedule7.oath-president") is None


def test_asking_what_to_do_brings_in_enforcement() -> None:
    sections = [
        number
        for number, _weight in topic_sections(
            "What can I do if the police search my phone without permission?"
        )
    ]
    assert sections[:2] == ["37", "46"]
    assert "46" not in [
        number for number, _ in topic_sections("can police search my phone")
    ]


def test_companions_bring_restrictions_into_context() -> None:
    assert companion_sections("37") == ("45",)
    assert companion_sections("131") == ("137",)
    assert companion_sections("33") == ()


def test_keyword_query_ors_content_words_with_prefixes() -> None:
    assert lexical_tsquery("Can the police search my phone?") == (
        "police:* | search:* | phone:*"
    )
    assert lexical_tsquery("what is the Constitution?") is None
    # Only alphanumeric words reach to_tsquery.
    assert lexical_tsquery("bail & (detention) | !x") == "bail:* | detention:*"
