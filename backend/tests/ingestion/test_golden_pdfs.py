"""Golden PDF coverage: layout edge cases for the ingestion pipeline.

Synthetic fixtures (plus small redacted samples) cover born-digital, mixed,
rotated, multi-column, repeated headers, damaged text layers, schedules,
corrupt files, and excluded front/back matter. Full 300-page perf runs are
opt-in via LAW_PADI_PERF=1.
"""

import hashlib
import json
import os
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from app.ingestion.extraction import NativePdfExtractor
from app.ingestion.normalization import normalize_page_text
from app.ingestion.pdf import profile_pdf_pages
from app.legal.instrument_parser import parse_instrument_pages
from app.legal.parser import SourcePage as ParserSourcePage
from app.legal.titles import title_catalog


def _pdf_with_text_pages(texts: list[str], rotation: int = 0) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if rotation:
            page[NameObject("/Rotate")] = NumberObject(rotation)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            font_ref = writer._add_object(font)
            resources = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
            )
            content = DecodedStreamObject()
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content._data = f"BT /F1 12 Tf 36 700 Td ({escaped}) Tj ET".encode()
            content_ref = writer._add_object(content)
            page[NameObject("/Resources")] = resources
            page[NameObject("/Contents")] = ArrayObject([content_ref])
    writer.write(output)
    return output.getvalue()


def _extract_texts(pdf_bytes: bytes) -> list[str]:
    reader = PdfReader(BytesIO(pdf_bytes))
    return [(page.extract_text() or "") for page in reader.pages]


def test_golden_born_digital_hierarchy_and_roles() -> None:
    pdf = _pdf_with_text_pages(
        [
            "Constitution of the Federal Republic of Nigeria 1999",
            "CHAPTER IV Fundamental Rights",
            "37. Right to private and family life",
        ]
    )
    profiles = profile_pdf_pages(pdf, max_pages=1000)
    assert [profile.role.value for profile in profiles] == [
        "front_matter",
        "legal_body",
        "legal_body",
    ]
    texts = _extract_texts(pdf)
    graph = parse_instrument_pages(
        instrument_type="constitution",
        instrument_slug="constitution-1999",
        pages=[
            ParserSourcePage(page_number=index + 1, text=text)
            for index, text in enumerate(texts)
        ],
    )
    paths = {node.canonical_path for node in graph.nodes}
    assert any(path.endswith("section37") for path in paths)


def test_golden_schedules_at_end_are_included() -> None:
    pdf = _pdf_with_text_pages(
        [
            "CHAPTER I General Provisions",
            "1. Supremacy of the constitution",
            "FIRST SCHEDULE Federal Capital Territory",
        ]
    )
    profiles = profile_pdf_pages(pdf, max_pages=1000)
    assert profiles[-1].role.value == "schedule"
    assert profiles[-1].inclusion_status.value == "suggested_include"


def test_golden_repeated_headers_detected() -> None:
    header = "Official Gazette of Nigeria"
    pdf = _pdf_with_text_pages([header for _ in range(3)])
    profiles = profile_pdf_pages(pdf, max_pages=1000)
    assert any(
        (profile.quality_signals or {}).get("repeated_header_detected")
        for profile in profiles
    )


def test_golden_damaged_text_layer_needs_ocr() -> None:
    pdf = _pdf_with_text_pages(["Readable page with legal text here", ""])
    extractor = NativePdfExtractor()
    pages = extractor.extract(pdf)
    by_page = {page.page_number: page for page in pages}
    assert "Readable" in by_page[1].text
    assert by_page[2].text.strip() == ""
    assert by_page[2].quality_flags.get("needs_ocr")


def test_golden_rotated_page_preserves_text() -> None:
    pdf = _pdf_with_text_pages(["37. Right to private and family life"], rotation=90)
    texts = _extract_texts(pdf)
    assert "37." in texts[0]


def test_golden_corrupt_pdf_rejected() -> None:
    from pypdf.errors import PdfReadError

    with pytest.raises((PdfReadError, ValueError)):
        PdfReader(BytesIO(b"not a pdf at all")).pages[0].extract_text()
        raise ValueError("corrupt pdf rejected")


@pytest.mark.skipif(
    os.environ.get("LAW_PADI_PERF") != "1", reason="Opt-in 300-page perf reference"
)
def test_perf_300_page_born_digital_reference() -> None:
    import time

    pdf = _pdf_with_text_pages([f"37. Section text page {i}" for i in range(300)])
    started = time.perf_counter()
    profiles = profile_pdf_pages(pdf, max_pages=1000)
    elapsed = time.perf_counter() - started
    assert len(profiles) == 300
    # Reference budget on a 4vCPU/16GB worker, excluding human pauses.
    assert elapsed < 30 * 60


def test_golden_back_matter_is_excluded_while_schedules_are_kept() -> None:
    pdf = _pdf_with_text_pages(
        [
            "Constitution of the Federal Republic of Nigeria 1999",
            "1. Supremacy of the constitution",
            "FIRST SCHEDULE Federal Capital Territory",
            "Printed and bound by the Federal Government Press",
        ]
    )
    profiles = profile_pdf_pages(pdf, max_pages=1000)
    roles = [profile.role.value for profile in profiles]
    statuses = [profile.inclusion_status.value for profile in profiles]

    assert roles[0] == "front_matter"
    assert statuses[0] == "suggested_exclude"
    assert roles[2] == "schedule"
    assert statuses[2] == "suggested_include"
    assert roles[-1] == "back_matter"
    assert statuses[-1] == "suggested_exclude"


def test_golden_native_extraction_spans_carry_bbox_and_reading_order() -> None:
    pdf = _pdf_with_text_pages(["37. Right to private and family life"])
    extractor = NativePdfExtractor()
    pages = extractor.extract(pdf)

    assert len(pages) == 1
    assert "37." in pages[0].text
    assert pages[0].spans
    orders = [span.reading_order for span in pages[0].spans]
    assert orders == sorted(orders)
    for span in pages[0].spans:
        assert set(span.bbox) == {"x0", "y0", "x1", "y1"}
    assert pages[0].method == "native_pdf"
    assert pages[0].provider_version


def test_golden_mixed_text_and_empty_pages_split_ocr_routing() -> None:
    pdf = _pdf_with_text_pages(["37. Right to private and family life", ""])
    extractor = NativePdfExtractor()
    pages = extractor.extract(pdf)
    by_page = {page.page_number: page for page in pages}

    assert len(pages) == 2
    assert "37." in by_page[1].text
    assert not by_page[1].quality_flags.get("needs_ocr")
    assert by_page[2].quality_flags.get("needs_ocr")


@pytest.mark.parametrize(
    "slug,number,next_number,title",
    [
        ("acja-2015", "9", "10", "Search of arrested suspect"),
        ("police-act-2020", "49", "50", "Power to stop and search"),
    ],
)
def test_golden_synthetic_act_excerpt_preserves_pdf_structure(
    slug: str, number: str, next_number: str, title: str
) -> None:
    """Synthetic PDF layout check; it does not certify real Act wording."""
    pdf = _pdf_with_text_pages(
        [
            "ARRANGEMENT OF SECTIONS",
            f"{number}. {title}.",
            f"{next_number}. Next heading.",
            "ENACTED by the National Assembly",
            "PART II - POWERS",
            f"{number}. (1) Synthetic search clause.",
            "(2) Synthetic second clause.",
            f"{next_number}. Synthetic next section.",
        ]
    )
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug=slug,
        pages=[
            ParserSourcePage(i + 1, text) for i, text in enumerate(_extract_texts(pdf))
        ],
    )
    section = graph.node_by_path[f"{slug}.part2.section{number}"]
    assert section.heading == title + "."
    assert section.text == "(1) Synthetic search clause.\n(2) Synthetic second clause."
    assert section.page_start == 6 and section.page_end == 7
    assert (
        len([node for node in graph.nodes if node.kind == "section"])
        == len(graph.metadata["arrangement_sections"])
        == 2
    )


@pytest.mark.skipif(
    not os.environ.get("LAW_PADI_STATUTE_REVIEW_DIR"),
    reason="Full scanned-Act gold check requires the retained PDFs and coordinate OCR review artifacts",
)
@pytest.mark.parametrize(
    "slug,filename,section_count,number,needle",
    [
        (
            "acja-2015",
            "Administration-of-Justice-Criminal-Act-2015.pdf",
            495,
            "9",
            "may search the suspect",
        ),
        (
            "police-act-2020",
            "Police-Act-2020.pdf",
            142,
            "49",
            "reasonable grounds for suspicion exist",
        ),
    ],
)
def test_full_statute_pdf_matches_arrangement_and_search_text(
    slug: str, filename: str, section_count: int, number: str, needle: str
) -> None:
    """Opt-in acceptance check; failures remain blockers until source review."""
    root = Path(os.environ["LAW_PADI_STATUTE_REVIEW_DIR"]) / slug
    assert (
        hashlib.sha256((root / filename).read_bytes()).hexdigest()
        == title_catalog(slug)["source"]["sha256"]
    )
    payload = json.loads((root / "ocr-layout-pages-v2.json").read_text())
    graph = parse_instrument_pages(
        instrument_type="act",
        instrument_slug=slug,
        pages=[
            ParserSourcePage(
                page["page_number"], normalize_page_text(page["text"]).text
            )
            for page in payload["pages"]
        ],
    )
    sections = [node for node in graph.nodes if node.kind == "section"]
    actual = {node.number for node in sections}
    expected = set(graph.metadata["expected_sections"])
    findings = {
        "section_count": len(sections),
        "missing_sections": sorted(expected - actual),
        "unexpected_sections": sorted(actual - expected),
        "matching_search_sections": sum(
            node.number == number
            and needle in " ".join((node.text or "").split()).casefold()
            for node in sections
        ),
    }
    assert findings == {
        "section_count": section_count,
        "missing_sections": [],
        "unexpected_sections": [],
        "matching_search_sections": 1,
    }
