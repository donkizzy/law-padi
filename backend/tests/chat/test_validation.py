from uuid import UUID, uuid4

import pytest

from app.chat.evidence_packet import prompt_items, source_crossrefs
from app.chat.schemas import ExplanationBlock, ExplanationDraft
from app.chat.validation import (
    EvidenceValidationError,
    QuestionNotAnsweredError,
    asks_yes_no,
    validate_draft,
    validate_verifier,
)
from app.legal.schemas import EvidenceItem


def test_source_cross_reference_may_be_preserved_without_extra_evidence() -> None:
    release_id = uuid4()
    evidence = EvidenceItem.model_construct(
        evidence_id="E1",
        release_id=release_id,
        canonical_path="constitution-1999.chapter1.part2.section7",
        ancestor_citations=[],
        authoritative_text="The Government shall, subject to section 8 of this Constitution, ensure their existence.",
        legal_status="historical",
    )
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="The state's duty is subject to Section 8.", evidence_ids=["E1"]
            )
        ]
    )
    validate_draft(draft, [evidence], release_id=release_id)

    draft.blocks[0].text = "The state's duty is subject to Section 99."
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [evidence], release_id=release_id)


def test_cross_references_are_found_in_long_provision_text() -> None:
    source = (
        "The council shall exist under a Law, subject to section 8 of this "
        "Constitution. This section also refers to section 162 of this "
        "Constitution and section 8 again."
    )
    assert [reference.section for reference in source_crossrefs(source)] == [
        "8",
        "162",
    ]


def test_ancestor_citation_is_accepted_but_unrelated_section_is_rejected() -> None:
    release_id = uuid4()
    evidence = EvidenceItem.model_construct(
        evidence_id="E1",
        release_id=release_id,
        canonical_path="constitution-1999.chapter4.section33.subsection2.paragraphb",
        ancestor_citations=["Chapter 4", "Section 33", "Section 33(2)"],
        authoritative_text="A person shall not be regarded as deprived of life in contravention of this section.",
        legal_status="historical",
    )
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Section 33 addresses this exception.", evidence_ids=["E1"]
            )
        ]
    )
    validate_draft(draft, [evidence], release_id=release_id)

    draft.blocks[0].text = "Section 99 addresses this exception."
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [evidence], release_id=release_id)


def test_historical_disclaimer_is_not_a_claim_of_current_law() -> None:
    release_id = uuid4()
    evidence = EvidenceItem.model_construct(
        evidence_id="E1",
        release_id=release_id,
        canonical_path="constitution-1999.chapter1.part1.section1",
        ancestor_citations=[],
        authoritative_text="This Constitution is supreme.",
        legal_status="historical",
    )
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="This historical source does not establish current law.",
                evidence_ids=["E1"],
            )
        ]
    )
    validate_draft(draft, [evidence], release_id=release_id)

    draft.blocks[0].text = "This is current law today."
    with pytest.raises(EvidenceValidationError, match="described as current law"):
        validate_draft(draft, [evidence], release_id=release_id)


def test_prompt_evidence_includes_ancestor_citations() -> None:
    evidence = EvidenceItem.model_construct(
        evidence_id="E1",
        canonical_path="constitution-1999.chapter4.section33.subsection2.paragraphb",
        citation="Section 33(2)(b)",
        ancestor_citations=["Chapter 4", "Section 33", "Section 33(2)"],
        legal_status="historical",
        edition_label="1999 source edition",
        authoritative_text="A person shall not be regarded as deprived of life.",
    )
    assert prompt_items([evidence])[0]["ancestor_citations"] == [
        "Chapter 4",
        "Section 33",
        "Section 33(2)",
    ]


def _privacy_evidence(release_id: UUID) -> EvidenceItem:
    return EvidenceItem.model_construct(
        evidence_id="E1",
        release_id=release_id,
        canonical_path="constitution-1999.chapter4.section37",
        ancestor_citations=["Chapter 4"],
        authoritative_text="The privacy of citizens is guaranteed and protected.",
        legal_status="historical",
    )


def test_later_block_failures_are_reported_for_removal() -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Section 37 protects your privacy.", evidence_ids=["E1"]
            ),
            ExplanationBlock(text="Section 99 also applies.", evidence_ids=["E1"]),
            ExplanationBlock(text="It is the law today.", evidence_ids=["E1"]),
        ]
    )
    assert validate_draft(
        draft, [_privacy_evidence(release_id)], release_id=release_id
    ) == {
        1: "Explanation cites a provision outside its evidence",
        2: "Historical wording was described as current law",
    }


def test_opening_block_failure_rejects_the_explanation() -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(text="Section 99 protects privacy.", evidence_ids=["E1"]),
            ExplanationBlock(text="Section 37 protects privacy.", evidence_ids=["E1"]),
        ]
    )
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [_privacy_evidence(release_id)], release_id=release_id)


def test_a_subsection_of_a_cited_section_is_inside_its_evidence() -> None:
    release_id = uuid4()
    evidence = EvidenceItem.model_construct(
        evidence_id="E1",
        release_id=release_id,
        canonical_path="constitution-1999.chapter6.part1.section131",
        ancestor_citations=["Chapter 6", "Part 1"],
        authoritative_text="A person shall be qualified if (a) ... (b) he has attained the age of forty years.",
        legal_status="historical",
    )
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Section 131(b) sets the minimum age.", evidence_ids=["E1"]
            )
        ]
    )
    assert validate_draft(draft, [evidence], release_id=release_id) == {}
    draft.blocks[0].text = "Section 132(b) sets the minimum age."
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [evidence], release_id=release_id)


def test_verifier_rejections_drop_later_blocks_but_not_the_answer() -> None:
    verdicts = {
        "verdicts": [
            {
                "index": 0,
                "supported": True,
                "qualifications_preserved": True,
                "answers_question": True,
            },
            {"index": 1, "supported": False, "qualifications_preserved": True},
            {"index": 2, "supported": True, "qualifications_preserved": False},
        ]
    }
    assert validate_verifier(verdicts, block_count=3) == {1, 2}
    verdicts["verdicts"][0]["supported"] = False
    with pytest.raises(EvidenceValidationError, match="not supported"):
        validate_verifier(verdicts, block_count=3)
    with pytest.raises(EvidenceValidationError, match="incomplete"):
        validate_verifier(verdicts, block_count=4)


@pytest.mark.parametrize(
    "text",
    [
        "No such law is in the provided evidence.",
        "The evidence list does not mention phones.",
        "Section 37 says this, as E1 shows.",
        "The wording of Section 37 is broad.",
        "This answer is based on Section 37.",
    ],
)
def test_blocks_never_describe_how_the_answer_was_produced(text: str) -> None:
    release_id = uuid4()
    opening = ExplanationBlock(
        text="Section 37 protects your privacy.", evidence_ids=["E1"]
    )
    draft = ExplanationDraft(
        blocks=[opening, ExplanationBlock(text=text, evidence_ids=["E1"])]
    )
    assert validate_draft(
        draft, [_privacy_evidence(release_id)], release_id=release_id
    ) == {1: "A block describes how the answer was produced"}
    draft.blocks.reverse()
    with pytest.raises(EvidenceValidationError, match="how the answer was produced"):
        validate_draft(draft, [_privacy_evidence(release_id)], release_id=release_id)


def test_giving_evidence_in_court_is_not_meta_language() -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="You cannot be forced to give evidence against yourself.",
                evidence_ids=["E1"],
            )
        ]
    )
    assert (
        validate_draft(draft, [_privacy_evidence(release_id)], release_id=release_id)
        == {}
    )


def test_a_block_restating_an_earlier_block_is_removed() -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Section 37 protects the privacy of your home, correspondence and telephone conversations.",
                evidence_ids=["E1"],
            ),
            ExplanationBlock(
                text="Section 37 guarantees privacy for your home, correspondence and telephone conversations.",
                evidence_ids=["E1"],
            ),
            ExplanationBlock(
                text="Police would need a lawful reason to read your messages.",
                evidence_ids=["E1"],
            ),
        ]
    )
    assert validate_draft(
        draft, [_privacy_evidence(release_id)], release_id=release_id
    ) == {1: "A block repeats an earlier block"}


def test_an_opening_that_misreads_the_question_rejects_the_explanation() -> None:
    verdicts = {
        "verdicts": [
            {
                "index": 0,
                "supported": True,
                "qualifications_preserved": True,
                "answers_question": False,
            }
        ]
    }
    with pytest.raises(QuestionNotAnsweredError):
        validate_verifier(verdicts, block_count=1)
    verdicts["verdicts"][0]["answers_question"] = True
    assert validate_verifier(verdicts, block_count=1) == set()


@pytest.mark.parametrize(
    ("question", "yes_no"),
    [
        ("Can police search my phone?", True),
        ("Police held me for three days, is that allowed?", True),
        ("What can I do if police already searched my phone?", False),
        ("How long can police hold me?", False),
        ("Section 37", False),
    ],
)
def test_yes_no_questions_are_recognised(question: str, yes_no: bool) -> None:
    assert asks_yes_no(question) is yes_no


def test_an_open_question_cannot_be_answered_with_yes() -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Yes. You can apply to a High Court about your privacy.",
                evidence_ids=["E1"],
            )
        ]
    )
    evidence = [_privacy_evidence(release_id)]
    with pytest.raises(QuestionNotAnsweredError, match="does not ask for one"):
        validate_draft(
            draft,
            evidence,
            release_id=release_id,
            question="What can I do if police already searched my phone?",
        )
    assert (
        validate_draft(
            draft,
            evidence,
            release_id=release_id,
            question="Can I go to court if police searched my phone?",
        )
        == {}
    )
    draft.blocks[0].text = "You can apply to a High Court about your privacy."
    assert (
        validate_draft(
            draft,
            evidence,
            release_id=release_id,
            question="What can I do if police already searched my phone?",
        )
        == {}
    )


def test_section45_keeps_its_source_cross_references() -> None:
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "data" / "constitution-section45.json").read_text()
    )
    references = source_crossrefs(fixture["text"])
    assert {("37", None), ("33", None), ("36", "8"), ("305", None)} <= {
        (reference.section, reference.subsection) for reference in references
    }
    assert len(references) <= 5


def test_source_bad_reference_does_not_hide_independent_valid_references() -> None:
    from app.legal.references import SectionReference

    assert source_crossrefs(
        "Subject to section 9 of the Evidence Act. Section 37 shall invalidate any law. "
        "See section 35 of this Constitution."
    ) == [SectionReference("37"), SectionReference("35")]
    assert source_crossrefs(
        "Subject to section 9 of this Act. Section 35 of the Constitution also applies. "
        "Section 49 of the Police Act is referred to.",
        "acja-2015",
    ) == [
        SectionReference("9", instrument_slug="acja-2015"),
        SectionReference("35"),
        SectionReference("49", instrument_slug="police-act-2020"),
    ]


def test_source_list_before_a_new_paragraph_remains_available() -> None:
    from app.legal.references import SectionReference

    assert set(
        source_crossrefs(
            "See sections 221, 225(3) and 227 of this Constitution; "
            "(b) restrictions on holding office refer to section 225(3) of this Constitution; "
            "(c) another paragraph follows."
        )
    ) == {
        SectionReference("221"),
        SectionReference("225", "3"),
        SectionReference("227"),
    }
