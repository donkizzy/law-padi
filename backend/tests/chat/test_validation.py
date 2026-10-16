from uuid import UUID, uuid4

import pytest

from app.chat.schemas import ExplanationBlock, ExplanationDraft
from app.chat.validation import (
    EvidenceValidationError,
    validate_draft,
    validate_verifier,
)
from app.chat.worker import _prompt_items, _source_crossrefs
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
    assert [reference.section for reference in _source_crossrefs(source)] == [
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
        citation="Section 33(2)(b)",
        ancestor_citations=["Chapter 4", "Section 33", "Section 33(2)"],
        legal_status="historical",
        edition_label="1999 source edition",
        authoritative_text="A person shall not be regarded as deprived of life.",
    )
    assert _prompt_items([evidence])[0]["ancestor_citations"] == [
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
            {"index": 0, "supported": True, "qualifications_preserved": True},
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
