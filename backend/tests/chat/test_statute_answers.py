"""Multi-law answer contracts using synthetic sources and a scripted provider.

These exercise provenance, prompts and fail-closed behavior, not real-law
accuracy or live-model grounding. The actual Acts remain unpublished.
"""

import asyncio
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.chat import EXPLANATION_PROMPT_VERSION, worker
from app.chat.llm.protocol import ProviderResult
from app.chat.schemas import ExplanationBlock, ExplanationDraft
from app.chat.validation import EvidenceValidationError, validate_draft
from app.core.config import settings
from app.legal.enums import (
    CorpusReleaseStatus,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
)
from app.legal.models import (
    ConversationMessage,
    CorpusReleaseEntry,
    GenerationRun,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import load_public_corpus
from app.legal.schemas import EvidenceItem


@pytest.fixture
def statute_texts() -> dict[str, str]:
    return {
        "acja-2015:2": "Synthetic scope: these procedures concern federal criminal proceedings and the FCT. State procedure may differ.",
        "acja-2015:9": "Synthetic search rule: an officer may search a person after arrest, without a search warrant, subject to the stated safeguards.",
        "police-act-2020:49": "Synthetic stop/search rule: an officer may search without a warrant on reasonable suspicion of stolen property. Suspicion is required.",
    }


@pytest.fixture
def answer_corpus(db: Session, statute_corpus):
    release = statute_corpus
    release.status = CorpusReleaseStatus.BUILDING
    db.add(release)
    db.commit()
    constitution = db.exec(
        select(LegalInstrument).where(LegalInstrument.slug == "constitution-1999")
    ).one()
    source = db.exec(
        select(SourceDocument).where(
            SourceDocument.legal_instrument_id == constitution.id
        )
    ).one()
    for number, text in {
        "1": "Synthetic supremacy rule: the Constitution is supreme and all other laws are subject to it.",
        "35": "Synthetic liberty rule: personal liberty is protected, subject to the stated arrest conditions and detention limits.",
        "45": "Synthetic limits rule: restrictions on privacy must meet the Constitution's public safety or public order conditions.",
        "46": "Synthetic remedy rule: a person may ask a High Court to enforce a breached right.",
    }.items():
        provision = Provision(
            instrument_id=constitution.id,
            kind=ProvisionKind.SECTION,
            number=number,
            canonical_path=f"constitution-1999.section{number}",
            sort_key=number.zfill(3),
        )
        db.add(provision)
        db.flush()
        version = ProvisionVersion(
            provision_id=provision.id,
            source_document_id=source.id,
            text=text,
            normalized_text=text.lower(),
            text_sha256=legal_text_sha256(text),
            valid_from=date(2004, 1, 1),
            legal_status=LegalStatus.HISTORICAL,
        )
        db.add(version)
        db.flush()
        db.add(
            CorpusReleaseEntry(
                release_id=release.id,
                provision_version_id=version.id,
                source_document_id=source.id,
            )
        )
    db.flush()
    release.status = CorpusReleaseStatus.PRODUCTION
    db.add(release)
    db.commit()
    return release


def _evidence(
    slug: str,
    number: str,
    release_id: UUID,
    *,
    identifier: str = "E1",
    text: str = "Synthetic provision.",
    status: str = "historical",
) -> EvidenceItem:
    return EvidenceItem.model_construct(
        evidence_id=identifier,
        canonical_path=f"{slug}.section{number}",
        citation=f"Section {number}"
        + (f", {slug}" if slug != "constitution-1999" else ""),
        instrument_slug=slug,
        instrument_title=slug,
        instrument_short_title={
            "acja-2015": "ACJA 2015",
            "police-act-2020": "Police Act 2020",
        }.get(slug),
        instrument_type=InstrumentType.CONSTITUTION
        if slug == "constitution-1999"
        else InstrumentType.ACT,
        release_id=release_id,
        authoritative_text=text,
        ancestor_citations=[],
        legal_status=status,
        edition_label="Historical/source Constitution compilation (LFN 2004)"
        if slug == "constitution-1999"
        else "As enacted, may have been amended.",
    )


@pytest.mark.parametrize(
    "wording,slug,number",
    [
        ("Section 9 of the ACJA permits this search after arrest.", "acja-2015", "9"),
        ("ACJA s.9 permits this search after arrest.", "acja-2015", "9"),
        ("Section 49 of the Police Act requires suspicion.", "police-act-2020", "49"),
    ],
)
def test_statute_citation_requires_the_correct_law(
    wording: str, slug: str, number: str
) -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[ExplanationBlock(text=wording, evidence_ids=["E1"])]
    )
    assert (
        validate_draft(
            draft, [_evidence(slug, number, release_id)], release_id=release_id
        )
        == {}
    )
    other = "police-act-2020" if slug == "acja-2015" else "acja-2015"
    with pytest.raises(EvidenceValidationError):
        validate_draft(
            draft, [_evidence(other, number, release_id)], release_id=release_id
        )
    with pytest.raises(EvidenceValidationError):
        validate_draft(
            draft,
            [_evidence("constitution-1999", number, release_id)],
            release_id=release_id,
        )


def test_citing_a_different_block_does_not_supply_a_law() -> None:
    release_id = uuid4()
    evidence = [
        _evidence("acja-2015", "9", release_id),
        _evidence("police-act-2020", "9", release_id, identifier="E2"),
    ]
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Section 9 of the ACJA permits this.", evidence_ids=["E2"]
            )
        ]
    )
    with pytest.raises(EvidenceValidationError):
        validate_draft(draft, evidence, release_id=release_id)


def test_act_cross_reference_alone_does_not_supply_the_referenced_section() -> None:
    release_id = uuid4()
    item = _evidence("acja-2015", "10", release_id, text="See Section 9, ACJA 2015.")
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(text="Section 9 of ACJA allows this.", evidence_ids=["E1"])
        ]
    )
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [item], release_id=release_id)


def test_constitution_cross_reference_does_not_match_a_number_prefix() -> None:
    release_id = uuid4()
    item = _evidence("constitution-1999", "7", release_id, text="See Section 99.")
    draft = ExplanationDraft(
        blocks=[ExplanationBlock(text="Section 9 allows this.", evidence_ids=["E1"])]
    )
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [item], release_id=release_id)


def test_a_named_law_without_a_section_still_needs_cited_evidence() -> None:
    release_id = uuid4()
    item = _evidence("constitution-1999", "37", release_id)
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="The Police Act permits this search.", evidence_ids=["E1"]
            )
        ]
    )
    with pytest.raises(EvidenceValidationError, match="names a law outside"):
        validate_draft(draft, [item], release_id=release_id)


@pytest.mark.parametrize("claim", ["This Act is in force.", "This is current law."])
def test_mixed_current_and_historical_evidence_cannot_mask_currency_claims(
    claim: str,
) -> None:
    release_id = uuid4()
    evidence = [
        _evidence("acja-2015", "9", release_id),
        _evidence(
            "constitution-1999", "37", release_id, identifier="E2", status="current"
        ),
    ]
    draft = ExplanationDraft(
        blocks=[ExplanationBlock(text=claim, evidence_ids=["E1", "E2"])]
    )
    with pytest.raises(EvidenceValidationError, match="described as current law"):
        validate_draft(draft, evidence, release_id=release_id)


def test_identical_text_in_different_laws_retains_separate_prompt_text() -> None:
    release_id = uuid4()
    rows = worker._prompt_items(
        [
            _evidence("acja-2015", "9", release_id),
            _evidence("police-act-2020", "9", release_id, identifier="E2"),
        ]
    )
    assert all(
        row["text"] == "Synthetic provision." and row["text_in"] is None for row in rows
    )
    assert {row["instrument_slug"] for row in rows} == {"acja-2015", "police-act-2020"}


def test_edition_notices_are_unique_per_cited_law() -> None:
    release_id = uuid4()
    evidence = [
        _evidence("constitution-1999", "37", release_id),
        _evidence("acja-2015", "9", release_id),
        _evidence("acja-2015", "18", release_id),
        _evidence("police-act-2020", "49", release_id),
    ]
    notice = worker._edition_notice(evidence)
    assert notice and "Constitution as published in 2004" in notice
    assert notice.count("ACJA 2015: As enacted, may have been amended.") == 1
    assert "Police Act 2020: As enacted, may have been amended." in notice


class ScriptedProvider:
    def __init__(
        self, *, empty: bool = False, wrong_law: bool = False, phone: bool = False
    ):
        self.empty = empty
        self.wrong_law = wrong_law
        self.phone = phone
        self.payloads: list[dict] = []

    async def complete_json(
        self, *, system: str, payload: dict, **_kwargs
    ) -> ProviderResult:
        self.payloads.append(payload)
        if "verdicts" in system:
            value = {
                "verdicts": [
                    {
                        "index": index,
                        "supported": True,
                        "qualifications_preserved": True,
                        "answers_question": True,
                    }
                    for index, _block in enumerate(payload["blocks"])
                ]
            }
        elif self.phone:

            def identifier(slug: str, number: str) -> str:
                return next(
                    item["id"]
                    for item in payload["evidence"]
                    if item["instrument_slug"] == slug
                    and item["citation"].split(",")[0] == f"Section {number}"
                )

            def constitution(number: str) -> str:
                return identifier("constitution-1999", number)

            value = {
                "direct_answer": "depends",
                "blocks": [
                    {
                        "text": "It depends on whether you were arrested and the grounds for the search. Section 37 protects your privacy.",
                        "evidence_ids": [
                            constitution("37"),
                            identifier("acja-2015", "9"),
                            identifier("police-act-2020", "49"),
                        ],
                    },
                    {
                        "text": "Section 9 of the ACJA permits a search after arrest subject to its safeguards. Section 49 of the Police Act requires reasonable suspicion of stolen property for the search described there.",
                        "evidence_ids": [
                            identifier("acja-2015", "9"),
                            identifier("police-act-2020", "49"),
                        ],
                    },
                    {
                        "text": "The Acts operate subject to the Constitution. Restrictions on privacy must meet Section 45's public safety or public order conditions.",
                        "evidence_ids": [constitution("1"), constitution("45")],
                    },
                    {
                        "text": "What you can do: You may ask a High Court to enforce a breached right under Section 46.",
                        "evidence_ids": [constitution("46")],
                    },
                    {
                        "text": "The ACJA's application depends on whether the proceedings fall within its federal/FCT scope. State procedure may differ.",
                        "evidence_ids": [identifier("acja-2015", "2")],
                    },
                ],
                "missing_facts": [
                    "Whether you had been arrested",
                    "Grounds given for the search",
                    "Which state you are in",
                ],
            }
        elif self.empty:
            value = {"direct_answer": "not_addressed", "blocks": []}
        else:
            item = next(
                row
                for row in payload["evidence"]
                if row["instrument_slug"] == "acja-2015"
                and row["citation"].startswith("Section 9,")
            )
            value = {
                "direct_answer": "explain",
                "blocks": [
                    {
                        "text": "Section 9 of the "
                        + ("Police Act" if self.wrong_law else "ACJA")
                        + " permits a search after arrest, subject to its safeguards.",
                        "evidence_ids": [item["id"]],
                    }
                ],
                "missing_facts": [],
            }
        return ProviderResult(
            value=value,
            prompt_tokens=100,
            completion_tokens=50,
            model="scripted-phase5",
        )


def _run_answer(
    client: TestClient, db: Session, provider: ScriptedProvider, question: str
) -> ConversationMessage:
    conversation = client.post("/api/v1/conversations", json={}).json()
    accepted = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"question": question, "idempotency_key": "phase5"},
    )
    assert accepted.status_code == 202
    run_id = UUID(accepted.json()["run_id"])
    assert worker._claim_run("phase5", run_id=run_id) == run_id
    asyncio.run(worker.process_run(run_id, "phase5", provider))
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None
    message = db.get(ConversationMessage, run.assistant_message_id)
    assert message is not None and message.answer_content is not None
    return message


@pytest.mark.parametrize(
    "empty,wrong_law,outcome",
    [
        (False, False, "completed"),
        (True, False, "insufficient_evidence"),
        (False, True, "validation_failed"),
    ],
)
def test_worker_sends_scoped_context_and_keeps_answers_grounded(
    client: TestClient,
    db: Session,
    answer_corpus,
    monkeypatch: pytest.MonkeyPatch,
    empty: bool,
    wrong_law: bool,
    outcome: str,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    provider = ScriptedProvider(empty=empty, wrong_law=wrong_law)
    message = _run_answer(client, db, provider, "Explain ACJA s.9")
    answer = message.answer_content
    assert answer["outcome"] == outcome
    payload = provider.payloads[0]
    assert {law["slug"] for law in payload["covered_laws"]} == {
        "constitution-1999",
        "acja-2015",
        "police-act-2020",
    }
    paths = {
        (item["instrument_slug"], item["citation"]) for item in payload["evidence"]
    }
    assert ("acja-2015", "Section 2, ACJA 2015") in paths
    assert ("constitution-1999", "Section 1") in paths
    if outcome == "completed":
        assert answer["notice"] == "ACJA 2015: As enacted, may have been amended."
        assert provider.payloads[1]["missing_facts"] == []
        assert EXPLANATION_PROMPT_VERSION == "constitution-english-v11"
    else:
        assert not answer["blocks"]
        assert "Constitution, ACJA 2015 and Police Act 2020" in answer["notice"]
    corpus = load_public_corpus(db, answer_corpus)
    act = next(
        provision
        for provision in corpus.provisions.values()
        if provision.canonical_path == "acja-2015.section9"
    )
    assert corpus.result(act).edition_label == "As enacted, may have been amended."


@pytest.mark.usefixtures("corpus")
def test_constitution_only_missing_law_notice_does_not_claim_act_coverage(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    provider = ScriptedProvider()
    message = _run_answer(client, db, provider, "ACJA s.9")
    assert not provider.payloads
    assert "ACJA 2015 isn't included" in message.answer_content["notice"]
    assert message.answer_content["notice"].endswith(
        "This edition includes Constitution."
    )


def test_phone_search_answer_uses_both_acts_limits_remedy_and_scope(
    client: TestClient, db: Session, answer_corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert answer_corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", False)
    provider = ScriptedProvider(phone=True)
    message = _run_answer(
        client, db, provider, "Can police search my phone without a warrant?"
    )
    answer = message.answer_content
    assert answer["outcome"] == "completed"
    assert len(answer["blocks"]) == 5
    assert "Which state you are in" in answer["missing_facts"]
    assert provider.payloads[1]["missing_facts"] == answer["missing_facts"]
    assert "ACJA 2015: As enacted, may have been amended." in answer["notice"]
    assert "Police Act 2020: As enacted, may have been amended." in answer["notice"]
    assert "Constitution as published in 2004" in answer["notice"]
    assert all(
        item["canonical_path"].startswith(item["instrument_slug"] + ".")
        for item in provider.payloads[0]["evidence"]
    )


def test_composite_results_keep_the_constitution_members_edition(
    db: Session, answer_corpus
) -> None:
    corpus = load_public_corpus(db, answer_corpus)
    corpus.release.validation_report = {
        "source_edition_review": {"edition": "Composite edition 2020"},
        "composition": {
            "members": [
                {
                    "instruments": [{"slug": "constitution-1999"}],
                    "source_edition_review": {
                        "edition": "Historical/source Constitution compilation (LFN 2004)"
                    },
                }
            ]
        },
    }
    constitution = next(
        provision
        for provision in corpus.provisions.values()
        if provision.canonical_path == "constitution-1999.chapter4.section37"
    )
    assert (
        corpus.result(constitution).edition_label
        == "Historical/source Constitution compilation (LFN 2004)"
    )


def test_wrong_enactment_year_without_a_section_is_rejected() -> None:
    release_id = uuid4()
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Police Act 2015 permits this search.", evidence_ids=["E1"]
            )
        ]
    )
    with pytest.raises(EvidenceValidationError):
        validate_draft(
            draft,
            [_evidence("police-act-2020", "49", release_id)],
            release_id=release_id,
        )


def test_bare_reference_after_act_qualifier_uses_constitution_evidence() -> None:
    release_id = uuid4()
    acja = _evidence("acja-2015", "9", release_id)
    constitution = _evidence("constitution-1999", "35", release_id, identifier="E2")
    draft = ExplanationDraft(
        blocks=[
            ExplanationBlock(
                text="Section 9 of the ACJA and Section 35 provide different safeguards.",
                evidence_ids=["E1", "E2"],
            )
        ]
    )
    validate_draft(draft, [acja, constitution], release_id=release_id)
    wrong_law = _evidence("acja-2015", "35", release_id, identifier="E2")
    with pytest.raises(EvidenceValidationError, match="outside its evidence"):
        validate_draft(draft, [acja, wrong_law], release_id=release_id)
