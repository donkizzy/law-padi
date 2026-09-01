from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.legal.enums import (
    AmendmentOperationType,
    AmendmentStatus,
    BillStatus,
    EvidenceRole,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    LegislativeChamber,
    LegislativeEventType,
    MessageRole,
    ProvisionKind,
    SourceTier,
    VerificationStatus,
)
from app.legal.models import (
    Amendment,
    AmendmentOperation,
    ConstitutionalBill,
    Conversation,
    ConversationMessage,
    LegalInstrument,
    LegislativeEvent,
    MessageEvidence,
    Provision,
    ProvisionVersion,
    SourceDocument,
)


def create_source_corpus(db: Session) -> tuple[LegalInstrument, SourceDocument, Provision]:
    suffix = uuid4().hex
    instrument = LegalInstrument(
        slug=f"cfrn-1999-test-{suffix}",
        title="Constitution of the Federal Republic of Nigeria 1999",
        short_title="CFRN 1999",
        instrument_type=InstrumentType.CONSTITUTION,
        jurisdiction="NG",
        year=1999,
        status=InstrumentStatus.ENACTED,
        enacted_at=date(1999, 5, 29),
        effective_at=date(1999, 5, 29),
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)

    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Official Gazette",
        title="CFRN 1999 test source",
        source_tier=SourceTier.OFFICIAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.chapter4.section37",
        sort_key="004.037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)

    return instrument, source, provision


def test_legal_schema_supports_anonymous_conversation_and_evidence(
    db: Session,
) -> None:
    _, source, provision = create_source_corpus(db)
    suffix = uuid4().hex
    amendment_instrument = LegalInstrument(
        slug=f"fifth-alteration-test-{suffix}",
        title="Fifth Alteration Test Act",
        instrument_type=InstrumentType.ALTERATION_ACT,
        jurisdiction="NG",
        year=2023,
        status=InstrumentStatus.ENACTED,
    )
    db.add(amendment_instrument)
    db.commit()
    db.refresh(amendment_instrument)

    amendment = Amendment(
        instrument_id=amendment_instrument.id,
        title="Fifth Alteration Test Act",
        year=2023,
        status=AmendmentStatus.ENACTED,
        source_document_id=source.id,
    )
    db.add(amendment)
    db.commit()
    db.refresh(amendment)

    version = ProvisionVersion(
        provision_id=provision.id,
        text="The privacy of citizens is protected.",
        normalized_text="the privacy of citizens is protected",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        text_sha256="a" * 64,
        created_by_amendment_id=amendment.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    operation = AmendmentOperation(
        amendment_id=amendment.id,
        target_provision_id=provision.id,
        target_version_id=version.id,
        operation_type=AmendmentOperationType.SUBSTITUTE,
        old_text="old text",
        new_text="new text",
        old_text_hash="b" * 64,
    )
    db.add(operation)

    bill_instrument = LegalInstrument(
        slug=f"state-police-bill-test-{suffix}",
        title="State Police Constitutional Bill Test",
        instrument_type=InstrumentType.BILL,
        jurisdiction="NG",
        year=2026,
        status=InstrumentStatus.PROPOSED,
    )
    db.add(bill_instrument)
    db.commit()
    db.refresh(bill_instrument)

    bill = ConstitutionalBill(
        instrument_id=bill_instrument.id,
        bill_number="HB-TEST-001",
        title="State Police Constitutional Bill Test",
        originating_chamber=LegislativeChamber.HOUSE,
        status=BillStatus.INTRODUCED,
        current_stage=BillStatus.INTRODUCED.value,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)

    event = LegislativeEvent(
        bill_id=bill.id,
        event_type=LegislativeEventType.INTRODUCED,
        event_date=date(2026, 1, 1),
        chamber=LegislativeChamber.HOUSE,
        description="Bill introduced for test purposes.",
    )
    db.add(event)

    conversation = Conversation(
        anonymous_session_id="anon-test-session",
        title="Privacy question",
        preferred_language="en",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Privacy is protected under Section 37.",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    evidence = MessageEvidence(
        message_id=message.id,
        provision_version_id=version.id,
        evidence_role=EvidenceRole.PRIMARY,
        retrieval_rank=1,
        retrieval_score=0.98,
        citation_label="CFRN 1999, s. 37",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    assert evidence.id is not None
    assert conversation.user_id is None
    assert bill.status == BillStatus.INTRODUCED
    assert bill.status != BillStatus.ENACTED


def test_conversation_requires_user_or_anonymous_session(db: Session) -> None:
    db.add(Conversation(title="Missing owner"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_provision_versions_cannot_overlap(db: Session) -> None:
    _, source, provision = create_source_corpus(db)
    first_version = ProvisionVersion(
        provision_id=provision.id,
        text="Version one",
        normalized_text="version one",
        valid_from=date(1999, 5, 29),
        valid_until=date(2026, 1, 1),
        legal_status=LegalStatus.SUPERSEDED,
        revision_number=1,
        source_document_id=source.id,
        text_sha256="c" * 64,
    )
    overlapping_version = ProvisionVersion(
        provision_id=provision.id,
        text="Version two",
        normalized_text="version two",
        valid_from=date(2025, 1, 1),
        legal_status=LegalStatus.CURRENT,
        revision_number=2,
        source_document_id=source.id,
        text_sha256="d" * 64,
    )
    db.add(first_version)
    db.commit()
    db.add(overlapping_version)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
