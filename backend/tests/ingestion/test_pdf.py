from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.ingestion.pdf import (
    MalwareScanError,
    PdfInspectionError,
    inspect_pdf_bytes,
    profile_pdf_pages,
    scan_pdf_bytes,
)
from app.legal.enums import PageInclusionStatus, PageRole


def test_inspect_pdf_bytes_verifies_magic_hash_size_and_page_limit() -> None:
    pdf = _pdf_with_pages(["Cover", "1. Supremacy of the Constitution"])
    inspection = inspect_pdf_bytes(
        pdf,
        expected_size=len(pdf),
        max_pages=10,
    )

    assert inspection.size_bytes == len(pdf)
    assert inspection.page_count == 2
    assert len(inspection.sha256) == 64

    with pytest.raises(PdfInspectionError, match="not a valid PDF"):
        inspect_pdf_bytes(b"not a pdf", max_pages=10)
    with pytest.raises(PdfInspectionError, match="size"):
        inspect_pdf_bytes(pdf, expected_size=len(pdf) + 1, max_pages=10)
    with pytest.raises(PdfInspectionError, match="1,000 pages or fewer"):
        inspect_pdf_bytes(pdf, max_pages=1)


def test_inspect_pdf_bytes_rejects_corrupt_and_password_protected_pdfs() -> None:
    with pytest.raises(PdfInspectionError, match="corrupt or unreadable"):
        inspect_pdf_bytes(b"%PDF-1.4\nnot a complete document", max_pages=10)

    encrypted_pdf = _encrypted_pdf(["37. Right to private and family life"])

    with pytest.raises(PdfInspectionError, match="Password-protected"):
        inspect_pdf_bytes(encrypted_pdf, max_pages=10)


def test_static_pdf_scan_rejects_active_content_markers() -> None:
    pdf = _pdf_with_pages(["1. Safe page"])

    assert scan_pdf_bytes(pdf)["active_content_markers"] == []
    with pytest.raises(MalwareScanError, match="active or embedded content"):
        scan_pdf_bytes(pdf + b"\n/JavaScript")


def test_profile_pdf_pages_classifies_roles_and_keeps_schedules_included() -> None:
    pdf = _pdf_with_pages(
        [
            "Official copy\nConstitution of the Federal Republic of Nigeria",
            "TABLE OF CONTENTS\nChapter I ...... 1\nChapter II ...... 3\nSection 37 ...... 20",
            "CHAPTER IV Fundamental Rights\n37. Right to private and family life",
            "FIRST SCHEDULE - States of the Federation\n1. Abia",
        ]
    )

    profiles = profile_pdf_pages(pdf, max_pages=10)

    assert [profile.role for profile in profiles] == [
        PageRole.FRONT_MATTER,
        PageRole.TABLE_OF_CONTENTS,
        PageRole.LEGAL_BODY,
        PageRole.SCHEDULE,
    ]
    assert profiles[0].inclusion_status == PageInclusionStatus.SUGGESTED_EXCLUDE
    assert profiles[1].inclusion_status == PageInclusionStatus.SUGGESTED_EXCLUDE
    assert profiles[2].inclusion_status == PageInclusionStatus.SUGGESTED_INCLUDE
    assert profiles[3].inclusion_status == PageInclusionStatus.SUGGESTED_INCLUDE
    assert profiles[3].inclusion_reason == (
        "Suggested inclusion: schedules are part of the Constitution"
    )
    assert all(profile.orientation == "portrait" for profile in profiles)
    assert profiles[2].quality_signals["has_extractable_text"] is True


def test_profile_pdf_pages_flags_mixed_scanned_and_born_digital_pages() -> None:
    pdf = _pdf_with_pages(
        [
            "Official copy",
            "",
            "CHAPTER IV Fundamental Rights\n37. Right to private and family life",
        ]
    )

    profiles = profile_pdf_pages(pdf, max_pages=10)

    assert profiles[1].role == PageRole.LEGAL_BODY
    assert profiles[1].inclusion_status == PageInclusionStatus.SUGGESTED_INCLUDE
    assert profiles[1].quality_signals["has_extractable_text"] is False
    assert profiles[1].quality_signals["requires_ocr"] is True
    assert profiles[2].quality_signals["has_extractable_text"] is True
    assert profiles[2].quality_signals["requires_ocr"] is False


def test_profile_pdf_pages_detects_repeated_edges_and_multicolumn_landscape() -> None:
    long_line = (
        "37. This line is intentionally long enough to look like a two column "
        "legal body page in the profiler."
    )
    pdf = _pdf_with_pages(
        [
            "\n".join(
                [
                    "Official Gazette Header",
                    long_line,
                    long_line,
                    long_line,
                    long_line,
                    "Page 1",
                ]
            ),
            "\n".join(
                [
                    "Official Gazette Header",
                    long_line,
                    long_line,
                    long_line,
                    long_line,
                    "Page 1",
                ]
            ),
        ],
        width=800,
        height=500,
    )

    profiles = profile_pdf_pages(pdf, max_pages=10)

    assert all(profile.orientation == "landscape" for profile in profiles)
    assert all(profile.column_count == 2 for profile in profiles)
    assert all(
        profile.quality_signals["repeated_header_detected"] for profile in profiles
    )
    assert all(
        profile.quality_signals["repeated_footer_detected"] for profile in profiles
    )


def test_profile_pdf_pages_records_rotated_page_orientation() -> None:
    pdf = _pdf_with_pages(
        ["CHAPTER I\n1. Supremacy of the Constitution"],
        rotate=90,
    )

    profile = profile_pdf_pages(pdf, max_pages=10)[0]

    assert profile.orientation == "portrait_rotated_90"
    assert profile.quality_signals["rotation_degrees"] == 90


def _pdf_with_pages(
    texts: list[str],
    *,
    width: float = 300,
    height: float = 500,
    rotate: int | None = None,
) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=width, height=height)
        if rotate is not None:
            page.rotate(rotate)
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
        content._data = (
            f"BT /F1 12 Tf 36 450 Td ({_escape_pdf_text(text)}) Tj ET".encode()
        )
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf(texts: list[str]) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=500)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        content = StreamObject()
        content._data = (
            f"BT /F1 12 Tf 36 450 Td ({_escape_pdf_text(text)}) Tj ET".encode()
        )
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.encrypt("secret")
    writer.write(output)
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
