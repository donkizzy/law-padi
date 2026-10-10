from uuid import uuid4

import pytest

from app.chat.schemas import ExplanationBlock, ExplanationDraft
from app.chat.validation import EvidenceValidationError, validate_draft
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
