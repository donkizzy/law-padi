from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.legal.enums import ProvisionKind
from app.legal.models import SourceDocument
from app.legal.parser import (
    PARSER_VERSION,
    ParserError,
    SourcePage,
    extract_source_pages,
    legal_text_sha256,
    normalize_legal_text,
    parse_constitution_pages,
)


def test_parse_constitution_pages_builds_hierarchy_and_text_metadata() -> None:
    parsed = parse_constitution_pages(
        [
            SourcePage(
                page_number=1,
                text="""
CHAPTER IV - Fundamental Rights
PART I Rights
37. Right to private and family life
(1) The privacy of citizens, their homes, correspondence, telephone conversations and telegraphic communications is hereby guaranteed and protected.
(2) This subsection keeps related continuation text with the same provision.
""",
            ),
            SourcePage(
                page_number=2,
                text="""
38. Right to freedom of thought
Every person shall be entitled to freedom of thought, conscience and religion.
(a) This paragraph remains attached to section 38.
(b) This second paragraph has its own canonical child path.
FIRST SCHEDULE - States of the Federation
1. Abia
Abia is listed as a State of the Federation.
""",
            ),
        ],
        "cfrn-1999",
    )

    paths = [node.canonical_path for node in parsed]
    assert paths == [
        "cfrn-1999.chapter4",
        "cfrn-1999.chapter4.part1",
        "cfrn-1999.chapter4.part1.section37",
        "cfrn-1999.chapter4.part1.section37.subsection1",
        "cfrn-1999.chapter4.part1.section37.subsection2",
        "cfrn-1999.chapter4.part1.section38",
        "cfrn-1999.chapter4.part1.section38.paragrapha",
        "cfrn-1999.chapter4.part1.section38.paragraphb",
        "cfrn-1999.schedule1",
        "cfrn-1999.schedule1.item1",
    ]

    chapter = parsed[0]
    assert chapter.kind == ProvisionKind.CHAPTER
    assert chapter.number == "4"
    assert chapter.heading == "Fundamental Rights"
    assert chapter.sort_key == "004"
    assert chapter.parser_metadata == {"parser_version": PARSER_VERSION}

    section = parsed[2]
    assert section.kind == ProvisionKind.SECTION
    assert section.parent_path == "cfrn-1999.chapter4.part1"
    assert section.page_start == 1
    assert section.page_end == 1
    assert section.heading == "Right to private and family life"
    assert section.parser_confidence == 0.94
    assert section.parser_metadata["subsection_count"] == 2
    assert section.parser_metadata["paragraph_count"] == 0

    subsection = parsed[3]
    assert subsection.kind == ProvisionKind.SUBSECTION
    assert subsection.number == "1"
    assert subsection.parent_path == section.canonical_path
    assert subsection.canonical_path == (
        "cfrn-1999.chapter4.part1.section37.subsection1"
    )
    assert subsection.text == (
        "(1) The privacy of citizens, their homes, correspondence, "
        "telephone conversations and telegraphic communications is hereby "
        "guaranteed and protected."
    )

    section_with_paragraphs = parsed[5]
    assert section_with_paragraphs.kind == ProvisionKind.SECTION
    assert section_with_paragraphs.parser_metadata["subsection_count"] == 0
    assert section_with_paragraphs.parser_metadata["paragraph_count"] == 2

    paragraph = parsed[6]
    assert paragraph.kind == ProvisionKind.PARAGRAPH
    assert paragraph.number == "a"
    assert paragraph.parent_path == "cfrn-1999.chapter4.part1.section38"
    assert paragraph.text == "(a) This paragraph remains attached to section 38."

    schedule_item = parsed[-1]
    assert schedule_item.kind == ProvisionKind.SCHEDULE_ITEM
    assert schedule_item.parent_path == "cfrn-1999.schedule1"
    assert schedule_item.sort_key == "900.001.0001"
    assert schedule_item.page_start == 2
    assert schedule_item.text == ("Abia\nAbia is listed as a State of the Federation.")


def test_parse_constitution_pages_rejects_duplicate_paths() -> None:
    with pytest.raises(ParserError, match="Duplicate provision path"):
        parse_constitution_pages(
            [
                SourcePage(
                    page_number=1,
                    text="""
CHAPTER I General Provisions
1. First section text
This is enough section text to be parsed.
1. Duplicate section text
This duplicate should fail before persistence.
""",
                )
            ],
            "cfrn-1999",
        )


def test_parse_constitution_pages_requires_text_nodes() -> None:
    with pytest.raises(
        ParserError, match="No Constitution sections or schedule items were detected"
    ):
        parse_constitution_pages(
            [SourcePage(page_number=1, text="CHAPTER I General Provisions")],
            "cfrn-1999",
        )


def test_legal_text_hash_uses_normalized_authoritative_text() -> None:
    first = " The Privacy of Citizens\nis protected. "
    second = "the privacy   of citizens is protected."

    assert normalize_legal_text(first) == normalize_legal_text(second)
    assert legal_text_sha256(first) == legal_text_sha256(second)


def test_extract_source_pages_reads_pdf_sources_from_blob_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    store = LocalBlobStore(tmp_path)
    pdf = _pdf_with_text("37. Right to private life")
    quarantine = store.put_quarantine(
        upload_id="extract-source-pages",
        filename="constitution.pdf",
        content=pdf,
        content_type="application/pdf",
    )
    original = store.promote_quarantine_to_original(
        quarantine_key=quarantine.key,
        expected_sha256=quarantine.sha256,
        content_type="application/pdf",
        extension=".pdf",
    )
    source = SourceDocument(
        legal_instrument_id=uuid4(),
        authority="Official Gazette",
        title="Stored PDF source",
        source_url="https://example.test/constitution.pdf",
        storage_key=original.key,
        storage_backend="local",
        sha256=original.sha256,
        mime_type="application/pdf",
        original_filename="constitution.pdf",
        file_size=original.size_bytes,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
    )

    pages = extract_source_pages(source)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Right to private life" in pages[0].text


def test_extract_source_pages_rejects_missing_or_unsupported_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    missing = SourceDocument(
        legal_instrument_id=uuid4(),
        authority="Official Gazette",
        title="Missing source",
        source_url="https://example.test/missing.pdf",
        storage_key="",
        storage_backend="local",
        sha256="a" * 64,
        mime_type="application/pdf",
        original_filename="missing.pdf",
        file_size=128,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
    )
    unsupported = SourceDocument(
        legal_instrument_id=uuid4(),
        authority="Official Gazette",
        title="Unsupported source",
        source_url="https://example.test/constitution.docx",
        storage_key="constitution.docx",
        storage_backend="local",
        sha256="b" * 64,
        mime_type="text/plain",
        original_filename="constitution.docx",
        file_size=128,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
    )

    with pytest.raises(ParserError, match="does not have a stored file"):
        extract_source_pages(missing)
    with pytest.raises(ParserError, match="Constitution PDF"):
        extract_source_pages(unsupported)


def _pdf_with_text(text: str) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=144)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )
    content = StreamObject()
    content._data = f"BT /F1 12 Tf 72 72 Td ({_escape_pdf_text(text)}) Tj ET".encode()
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
