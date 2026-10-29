import pytest

from app.ingestion.pgvector_repository import lexical_tsquery
from app.legal.topics import (
    companion_sections,
    demoted_sections,
    match_topics,
    related_laws,
    section_title,
    title_sections,
    tokens,
    topic_sections,
)


@pytest.mark.parametrize(
    ("question", "section"),
    [
        ("Can police search my phone?", "constitution-1999:37"),
        (
            "wetin constitution talk about police checking my phone",
            "constitution-1999:37",
        ),
        ("police detained me for 3 days without charge", "constitution-1999:35"),
        ("can police arrest me in another state", "constitution-1999:35"),
        ("can police torture a suspect", "constitution-1999:34"),
        ("can I buy land in another state", "constitution-1999:43"),
        ("can government take my land without paying", "constitution-1999:44"),
        ("how old must you be to become president", "constitution-1999:131"),
        (
            "A candidate asks about disqualification from the presidency",
            "constitution-1999:137",
        ),
        ("can the governor be sued while in office", "constitution-1999:308"),
        ("is Nigeria a secular state", "constitution-1999:10"),
        ("can the government stop me from leaving Nigeria", "constitution-1999:41"),
        (
            "Which provision allows a citizen to renounce Nigerian citizenship?",
            "constitution-1999:29",
        ),
        ("how can I recall my senator", "constitution-1999:69"),
        (
            "What does the presidential oath require?",
            "constitution-1999:oath-president",
        ),
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
    assert topic_sections("can police search my phone") == [
        ("constitution-1999:37", 2.5)
    ]
    assert topic_sections("privacy") == [("constitution-1999:37", 1.5)]
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
    assert sections[:2] == ["constitution-1999:37", "constitution-1999:46"]
    assert "constitution-1999:46" not in [
        number for number, _ in topic_sections("can police search my phone")
    ]


def test_companions_bring_restrictions_into_context() -> None:
    assert companion_sections("constitution-1999:37")[:2] == (
        "constitution-1999:45",
        "constitution-1999:46",
    )
    assert companion_sections("constitution-1999:35")[0] == "constitution-1999:46"
    assert companion_sections("constitution-1999:131") == ("constitution-1999:137",)
    assert companion_sections("constitution-1999:46") == ()


def test_rights_questions_push_down_police_and_legislature_sections() -> None:
    demoted = demoted_sections("Can police search my phone?")
    assert {
        "constitution-1999:214",
        "constitution-1999:215",
        "constitution-1999:216",
        "constitution-1999:89",
        "constitution-1999:129",
    } <= demoted
    assert "constitution-1999:37" not in demoted
    # A question about the police force itself keeps those sections.
    assert demoted_sections("can a state have its own police") == frozenset()
    assert "constitution-1999:215" not in demoted_sections(
        "who controls police and can they arrest me"
    )


def test_refusing_a_phone_search_is_a_privacy_question() -> None:
    for question in (
        "Can I refuse a phone search without a warrant?",
        "Do I have to unlock my phone for police?",
    ):
        assert match_topics(question)[0].slug == "privacy"


def test_related_laws_are_curated_per_topic() -> None:
    laws = related_laws("Can police search my phone?")
    assert any(law.startswith("Police Act 2020") for law in laws)
    assert any(law.startswith("Administration of Criminal Justice Act") for law in laws)
    assert related_laws("is Nigeria a secular state") == []


def test_keyword_query_ors_content_words_with_prefixes() -> None:
    assert lexical_tsquery("Can the police search my phone?") == (
        "police:* | search:* | phone:*"
    )
    assert lexical_tsquery("what is the Constitution?") is None
    # Only alphanumeric words reach to_tsquery.
    assert lexical_tsquery("bail & (detention) | !x") == "bail:* | detention:*"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "Can the police arrest my brother because they cannot find me?",
            ["acja-2015:7", "police-act-2020:36"],
        ),
        (
            "Can the police arrest a family member in place of a suspect?",
            ["acja-2015:7", "police-act-2020:36"],
        ),
        ("How is the Nigeria Police funded?", ["police-act-2020:26"]),
        (
            "What is the police reward fund?",
            ["police-act-2020:26", "police-act-2020:91"],
        ),
        ("Can police arrest me for my debt?", []),
    ],
)
def test_statute_topics_for_arrest_in_place_and_police_funding(
    question: str, expected: list[str]
) -> None:
    sections = topic_sections(
        question, instrument_slugs=("acja-2015", "police-act-2020")
    )
    assert sorted(number for number, _weight in sections) == expected


def test_questions_in_the_constitutions_own_words_match_section_titles() -> None:
    assert title_sections("appeal from the code of conduct tribunal") == [
        "constitution-1999:246"
    ]
    assert title_sections("appointment of the auditor-general") == [
        "constitution-1999:86",
        "constitution-1999:126",
    ]
    # A title outranks the broad topic the same words also match.
    assert topic_sections("grand kadi of the sharia court of appeal")[:2] == [
        ("constitution-1999:261", 3.5),
        ("constitution-1999:276", 3.5),
    ]


def test_title_matching_needs_specific_wording() -> None:
    assert title_sections("privacy") == []
    assert title_sections("can police search my phone") == []
    # Shared by every court's section, so it says nothing about which one.
    assert title_sections("practice and procedure") == []


def test_sections_named_by_several_topics_collect_each_boost() -> None:
    ranked = topic_sections(
        "can a foreign woman married to a nigerian become a citizen"
    )
    assert ranked[0] == ("constitution-1999:26", 5.0)


def test_statute_hints_require_release_membership() -> None:
    question = "search after arrest"
    assert not any(
        target.startswith("acja-2015:") for target, _ in topic_sections(question)
    )
    targets = {
        target
        for target, _ in topic_sections(
            question,
            instrument_slugs={"constitution-1999", "acja-2015", "police-act-2020"},
        )
    }
    assert {"acja-2015:9", "police-act-2020:52"} <= targets
    assert "acja-2015:9" in companion_sections("constitution-1999:37")
    assert "constitution-1999:35" in companion_sections("acja-2015:18")


def test_related_laws_follow_the_selected_release() -> None:
    question = "can police search my phone"
    before = related_laws(question)
    assert any(law.startswith("Police Act") for law in before)
    assert not any(
        law.startswith("Police Act")
        for law in related_laws(question, instrument_slugs={"police-act-2020"})
    )
    after = related_laws(
        question, instrument_slugs={"constitution-1999", "acja-2015", "police-act-2020"}
    )
    assert not any(
        law.startswith(("Police Act", "Administration of Criminal Justice Act"))
        for law in after
    )


def test_phone_search_wording_has_published_act_topic_hints() -> None:
    question = "Police took my phone and want to search it"
    slugs = {"constitution-1999", "acja-2015", "police-act-2020"}
    targets = {target for target, _ in topic_sections(question, instrument_slugs=slugs)}
    assert {"constitution-1999:37", "acja-2015:9", "police-act-2020:49"} <= targets
    assert all(
        target.startswith("constitution-1999:")
        for target, _ in topic_sections(question)
    )


@pytest.mark.parametrize(
    "query",
    [
        "What are the qualifications to become a Governor?",
        "qualifications for becoming governor",
        "Who is eligible to run for governor?",
    ],
)
def test_governor_eligibility_prioritises_qualification_and_keeps_limits_as_context(
    query: str,
) -> None:
    hints = topic_sections(query)
    assert hints[0][0] == "constitution-1999:177"
    assert "constitution-1999:182" in companion_sections("constitution-1999:177")


def test_governor_disqualification_is_not_positive_eligibility() -> None:
    assert (
        topic_sections("What disqualifies a governor?")[0][0] == "constitution-1999:182"
    )


@pytest.mark.parametrize("query", ["sirri", "nzuzo", "ìpamọ́", "asiri"])
def test_native_privacy_keywords_have_a_provider_independent_navigation_hint(
    query: str,
) -> None:
    assert topic_sections(query)[0][0] == "constitution-1999:37"
