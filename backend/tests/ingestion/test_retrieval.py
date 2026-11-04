import uuid
from datetime import date

from app.ingestion.retrieval import (
    build_retrieval_documents,
    citation_for_provision,
    split_legal_text,
)
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
    nested = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.PARAGRAPH,
        number="iv",
        canonical_path="acja-2015.part15.section123.paragraphb.paragraphiv",
    )
    assert citation_for_provision(nested, act) == "Section 123(b)(iv), ACJA 2015"
    deep = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.PARAGRAPH,
        number="ii",
        canonical_path="acja-2015.part2.section15.subsection1.paragraphd.paragraphii",
    )
    assert citation_for_provision(deep, act) == "Section 15(1)(d)(ii), ACJA 2015"
    first_schedule_form = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SCHEDULE_ITEM,
        number="1",
        canonical_path="acja-2015.schedule1.item1",
    )
    third_schedule_item = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.SCHEDULE_ITEM,
        number="1",
        canonical_path="acja-2015.schedule3.item1",
    )
    assert citation_for_provision(first_schedule_form, act) == (
        "Schedule 1, Item 1, ACJA 2015"
    )
    assert citation_for_provision(third_schedule_item, act) == (
        "Schedule 3, Item 1, ACJA 2015"
    )
    constitution = LegalInstrument(
        slug="constitution-1999",
        title="Constitution",
        instrument_type=InstrumentType.CONSTITUTION,
    )
    assert citation_for_provision(provision, constitution) == "Paragraph a"
    heading = Provision(
        instrument_id=act.id,
        kind=ProvisionKind.CROSS_HEADING,
        number="B",
        heading="Search",
        canonical_path="acja-2015.part2.headingB",
    )
    assert citation_for_provision(heading, act) == "Heading B, ACJA 2015"


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


def test_reviewed_phrasing_is_search_text_only_and_applies_to_one_provision() -> None:
    act = LegalInstrument(
        slug="police-act-2020",
        title="Nigeria Police Act 2020",
        short_title="Police Act 2020",
        instrument_type=InstrumentType.ACT,
    )
    source_id = uuid.uuid4()
    section = Provision(
        id=uuid.uuid4(),
        instrument_id=act.id,
        kind=ProvisionKind.SECTION,
        number="36",
        heading="Arrest in lieu prohibited.",
        canonical_path="police-act-2020.part7.section36",
        sort_key="036",
    )
    neighbour = Provision(
        id=uuid.uuid4(),
        instrument_id=act.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Humane treatment of arrested suspect.",
        canonical_path="police-act-2020.part7.section37",
        sort_key="037",
    )
    versions = {}
    entries = []
    for provision, text in (
        (section, "A person shall not be arrested in place of a suspect."),
        (neighbour, "A suspect shall be accorded humane treatment."),
    ):
        version = ProvisionVersion(
            id=uuid.uuid4(),
            provision_id=provision.id,
            text=text,
            normalized_text=text.lower(),
            valid_from=date(2020, 9, 16),
            legal_status=LegalStatus.HISTORICAL,
            source_document_id=source_id,
            text_sha256=legal_text_sha256(text),
        )
        versions[version.id] = version
        entries.append(
            CorpusReleaseEntry(
                id=uuid.uuid4(),
                release_id=uuid.uuid4(),
                provision_version_id=version.id,
                source_document_id=source_id,
            )
        )

    documents = build_retrieval_documents(
        release_version="draft-test",
        entries=entries,
        versions_by_id=versions,
        provisions_by_id={section.id: section, neighbour.id: neighbour},
        instruments_by_id={act.id: act},
    )

    by_path = {document.payload["canonical_path"]: document for document in documents}
    arrest = by_path[section.canonical_path]
    assert "In plain words:" in arrest.retrieval_text
    assert "relative" in arrest.retrieval_text
    # Readers only ever see the statutory wording.
    assert arrest.authoritative_text == (
        "A person shall not be arrested in place of a suspect."
    )
    assert "In plain words:" not in by_path[neighbour.canonical_path].retrieval_text


def test_long_interpretation_section_splits_one_segment_per_definition() -> None:
    text = (
        "In this Act —\n"
        "“applicable law” means any law enacted by the National Assembly;\n"
        "“court ” means any court of competent jurisdiction;\n"
        "“personal data” means any information relating to an individual,\n"
        "including a name or an identification number; and\n"
        "“sensitive personal data” includes data relating to —\n"
        "(a) health status, or\n"
        "(b) political opinions."
    )

    segments = split_legal_text(text, max_chars=120)

    assert segments == [
        "In this Act —\n“applicable law” means any law enacted by the National "
        "Assembly;",
        "“court ” means any court of competent jurisdiction;",
        "“personal data” means any information relating to an individual,\n"
        "including a name or an identification number; and",
        "“sensitive personal data” includes data relating to —\n"
        "(a) health status, or\n(b) political opinions.",
    ]


def test_definition_split_only_applies_to_long_lists_of_definitions() -> None:
    short = "In this Act —\n“court” means a court;\n“Minister” means the Minister."
    assert split_legal_text(short, max_chars=2800) == [short]

    # One quoted term in a long provision is not a definitions list.
    prose = (
        "The Commission may issue an order. "
        + "It shall state the reasons for the order. " * 4
        + "\n“Order” means an order under this section."
    )
    segments = split_legal_text(prose, max_chars=100)
    assert not segments[0].startswith("“")
    assert all(len(segment) <= 100 for segment in segments)
