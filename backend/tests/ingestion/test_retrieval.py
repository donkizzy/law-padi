import uuid
from datetime import date

from app.ingestion.retrieval import build_retrieval_documents, citation_for_provision
from app.legal.enums import InstrumentType, LegalStatus, ProvisionKind
from app.legal.models import (
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
)
from app.legal.parser import legal_text_sha256


def test_retrieval_citations_qualify_acts_and_preserve_constitution_labels() -> None:
    act = LegalInstrument(
        slug="acja-2015",
        title="Administration of Criminal Justice Act 2015",
        short_title="ACJA 2015",
        instrument_type=InstrumentType.ACT,
    )
    provision = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.PARAGRAPH,
        number="a",
        canonical_path="acja-2015.part2.section9.subsection1.paragrapha",
    )
    assert citation_for_provision(provision, act) == "Section 9(1)(a), ACJA 2015"
    constitution = LegalInstrument(
        slug="constitution-1999",
        title="Constitution",
        instrument_type=InstrumentType.CONSTITUTION,
    )
    assert citation_for_provision(provision, constitution) == "Paragraph a"


def test_retrieval_documents_include_citation_context_and_deterministic_segments() -> (
    None
):
    instrument_id = uuid.uuid4()
    source_id = uuid.uuid4()
    release_id = uuid.uuid4()
    chapter = Provision(
        id=uuid.uuid4(),
        instrument_id=instrument_id,
        kind=ProvisionKind.CHAPTER,
        number="4",
        heading="Fundamental Rights",
        canonical_path="constitution.1999.chapter4",
        sort_key="004",
    )
    section = Provision(
        id=uuid.uuid4(),
        instrument_id=instrument_id,
        parent_id=chapter.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path="constitution.1999.chapter4.section37",
        sort_key="004.037",
    )
    text = (
        "(1) First privacy clause protects citizens. "
        "(2) Second privacy clause protects homes. "
        "(3) Third privacy clause protects correspondence."
    )
    version = ProvisionVersion(
        id=uuid.uuid4(),
        provision_id=section.id,
        text=text,
        normalized_text=text.lower(),
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source_id,
        source_page_start=12,
        source_page_end=13,
        text_sha256=legal_text_sha256(text),
    )
    entry = CorpusReleaseEntry(
        id=uuid.uuid4(),
        release_id=release_id,
        provision_version_id=version.id,
        source_document_id=source_id,
    )

    first_result = build_retrieval_documents(
        release_version="draft-test",
        entries=[entry],
        versions_by_id={version.id: version},
        provisions_by_id={chapter.id: chapter, section.id: section},
        max_chars=70,
    )
    second_result = build_retrieval_documents(
        release_version="draft-test",
        entries=[entry],
        versions_by_id={version.id: version},
        provisions_by_id={chapter.id: chapter, section.id: section},
        max_chars=70,
    )

    assert [document.document_id for document in first_result] == [
        document.document_id for document in second_result
    ]
    assert [document.segment_id for document in first_result] == [
        "constitution.1999.chapter4.section37:v1:s1",
        "constitution.1999.chapter4.section37:v1:s2",
        "constitution.1999.chapter4.section37:v1:s3",
    ]
    assert first_result[0].citation == "Section 37"
    assert first_result[0].ancestor_headings == ["Fundamental Rights"]
    assert first_result[0].heading == "Right to private and family life"
    assert first_result[0].retrieval_text.startswith(
        "Section 37\nFundamental Rights\nRight to private and family life\n"
    )
    assert " ".join(document.authoritative_text for document in first_result) == text
    assert first_result[0].payload["canonical_path"] == (
        "constitution.1999.chapter4.section37"
    )
    assert first_result[0].payload["segment_count"] == 3
