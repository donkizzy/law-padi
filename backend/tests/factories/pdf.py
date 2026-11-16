"""PDF factories with explicit layout and stream options for ingestion fixtures."""

import hashlib
from io import BytesIO
from uuid import uuid4

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    StreamObject,
)


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_with_pages(
    texts: list[str],
    rotation: int = 0,
    *,
    width: float = 300,
    height: float = 500,
    rotate: int | None = None,
    font_size: int = 12,
    x: int = 36,
    y: int = 450,
    operations: str | None = None,
    content_array: bool = False,
    skip_empty: bool = False,
    password: str | None = None,
) -> bytes:
    """Keep blank-page, array-stream and text-layout variants explicit.

    Array streams use decoded streams and direct rotation metadata; ordinary
    streams use page.rotate. Empty text can retain an empty text layer or omit
    the layer entirely, as required by mixed scanned/born-digital fixtures.
    """
    output = BytesIO()
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=width, height=height)
        if content_array:
            if rotation:
                page[NameObject("/Rotate")] = NumberObject(rotation)
        elif rotate is not None or rotation:
            page.rotate(rotate if rotate is not None else rotation)
        if skip_empty and not text:
            continue
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
        content = DecodedStreamObject() if content_array else StreamObject()
        content._data = (
            operations
            or f"BT /F1 {font_size} Tf {x} {y} Td ({escape_pdf_text(text)}) Tj ET"
        ).encode()
        page[NameObject("/Resources")] = resources
        content_ref = writer._add_object(content)
        page[NameObject("/Contents")] = (
            ArrayObject([content_ref]) if content_array else content_ref
        )
    if password is not None:
        writer.encrypt(password)
    writer.write(output)
    return output.getvalue()


def pdf_with_text(text: str, **layout: int) -> bytes:
    return pdf_with_pages([text], **layout)


def pdf_bytes(*, width: int = 72, height: int = 72, title: str | None = None) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    if title is not None:
        writer.add_metadata({"/Title": title})
    writer.write(output)
    return output.getvalue()


def unique_pdf() -> bytes:
    return pdf_bytes(title=f"constitution-{uuid4().hex}")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    return sha256(content.encode())
