import hashlib
import json
import re
import uuid
from dataclasses import dataclass

from app.legal.citations import qualify_citation, rules_citation
from app.legal.enums import InstrumentType
from app.legal.models import (
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
)
from app.legal.retrieval_phrasing import retrieval_phrasing

DEFAULT_MAX_RETRIEVAL_TEXT_CHARS = 2800
_CLAUSE_BOUNDARY_RE = re.compile(r"(?<=[.;:])\s+(?=\(?[0-9a-zA-Z])")
# A line opening with a quoted term that "means" or "includes" starts a
# definition in an interpretation section.
_DEFINITION_START_RE = re.compile(
    r"^(?=[“\"][^”\"\n]{1,80}[”\"]\s*(?:means|includes|has|refers)\b)",
    re.MULTILINE,
)
_MIN_DEFINITIONS_TO_SPLIT = 3


@dataclass(frozen=True)
class RetrievalDocument:
    document_id: str
    segment_id: str
    release_version: str
    citation: str
    ancestor_headings: list[str]
    heading: str | None
    authoritative_text: str
    retrieval_text: str
    payload: dict[str, object]

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.document_id,
            "segment_id": self.segment_id,
            "release_version": self.release_version,
            "citation": self.citation,
            "ancestor_headings": self.ancestor_headings,
            "heading": self.heading,
            "authoritative_text": self.authoritative_text,
            "retrieval_text": self.retrieval_text,
            "payload": self.payload,
        }


SUPPORTED_RETRIEVAL_LANGUAGE = "en"


def build_retrieval_documents(
    *,
    release_version: str,
    entries: list[CorpusReleaseEntry],
    versions_by_id: dict[uuid.UUID, ProvisionVersion],
    provisions_by_id: dict[uuid.UUID, Provision],
    instruments_by_id: dict[uuid.UUID, LegalInstrument] | None = None,
    max_chars: int = DEFAULT_MAX_RETRIEVAL_TEXT_CHARS,
    language: str = SUPPORTED_RETRIEVAL_LANGUAGE,
) -> list[RetrievalDocument]:
    if language.strip().lower() != SUPPORTED_RETRIEVAL_LANGUAGE:
        raise ValueError(
            f"V1 retrieval input is English-only; received language={language!r}"
        )
    documents: list[RetrievalDocument] = []
    ordered_entries = sorted(
        entries,
        key=lambda entry: _entry_sort_key(entry, versions_by_id, provisions_by_id),
    )
    for entry in ordered_entries:
        version = versions_by_id.get(entry.provision_version_id)
        if not version:
            continue
        provision = provisions_by_id.get(version.provision_id)
        if not provision:
            continue
        instrument = (
            instruments_by_id[provision.instrument_id]
            if instruments_by_id is not None
            else None
        )
        citation = citation_for_provision(provision, instrument)
        ancestor_headings = ancestor_headings_for(provision, provisions_by_id)
        segments = split_legal_text(version.text, max_chars=max_chars)
        for segment_index, segment_text in enumerate(segments, start=1):
            segment_id = (
                f"{provision.canonical_path}:v{version.revision_number}:s"
                f"{segment_index}"
            )
            retrieval_text = retrieval_text_for(
                citation=citation,
                ancestor_headings=ancestor_headings,
                heading=provision.heading,
                text=segment_text,
                phrasing=retrieval_phrasing(provision.canonical_path),
            )
            payload: dict[str, object] = {
                "release_version": release_version,
                "corpus_release_entry_id": str(entry.id),
                "provision_id": str(provision.id),
                "instrument_id": str(provision.instrument_id),
                "provision_version_id": str(version.id),
                "canonical_path": provision.canonical_path,
                "kind": _enum_value(provision.kind),
                "number": provision.number,
                "source_document_id": str(version.source_document_id),
                "source_page_start": version.source_page_start,
                "source_page_end": version.source_page_end,
                "legal_status": _enum_value(version.legal_status),
                "segment_index": segment_index,
                "segment_count": len(segments),
                "text_sha256": version.text_sha256,
                "authoritative_text_sha256": _sha256(segment_text),
                "retrieval_text_sha256": _sha256(retrieval_text),
            }
            documents.append(
                RetrievalDocument(
                    document_id=_document_id(
                        release_version=release_version,
                        provision_version_id=version.id,
                        segment_index=segment_index,
                        retrieval_text=retrieval_text,
                    ),
                    segment_id=segment_id,
                    release_version=release_version,
                    citation=citation,
                    ancestor_headings=ancestor_headings,
                    heading=provision.heading,
                    authoritative_text=segment_text,
                    retrieval_text=retrieval_text,
                    payload=payload,
                )
            )
    return documents


def citation_for_provision(
    provision: Provision, instrument: LegalInstrument | None = None
) -> str:
    label_by_kind = {
        "chapter": "Chapter",
        "part": "Part",
        "cross_heading": "Heading",
        "section": "Section",
        "subsection": "Subsection",
        "paragraph": "Paragraph",
        "schedule": "Schedule",
        "schedule_item": "Schedule Item",
    }
    kind = _enum_value(provision.kind)
    label = label_by_kind.get(kind, kind.title())
    citation = f"{label} {provision.number}" if provision.number else label
    if instrument is not None:
        if instrument.instrument_type != InstrumentType.CONSTITUTION:
            # Nested paragraphs, e.g. 123(b)(iv), each keep their own label.
            match = re.search(
                r"\.section(\d+[a-z]?)((?:\.(?:subsection\d+[a-z]?|paragraph[a-z]+))*)$",
                provision.canonical_path,
            )
            if match:
                citation = f"Section {match.group(1)}" + "".join(
                    f"({number})"
                    for number in re.findall(
                        r"\.(?:subsection|paragraph)([0-9a-z]+)", match.group(2)
                    )
                )
            # Items are numbered within each Schedule, so name the Schedule too.
            schedule = re.search(
                r"\.schedule(\w+)\.item(\w+)$", provision.canonical_path
            )
            if schedule:
                citation = f"Schedule {schedule.group(1)}, Item {schedule.group(2)}"
            citation = rules_citation(provision.canonical_path) or citation
        return qualify_citation(citation, instrument)
    if not provision.canonical_path.startswith(("constitution-1999.", "constitution.")):
        raise ValueError(
            "Instrument metadata is required for non-Constitution retrieval citations"
        )
    return citation


def ancestor_headings_for(
    provision: Provision, provisions_by_id: dict[uuid.UUID, Provision]
) -> list[str]:
    headings: list[str] = []
    seen: set[uuid.UUID] = set()
    parent_id = provision.parent_id
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        parent = provisions_by_id.get(parent_id)
        if not parent:
            break
        if parent.heading:
            headings.append(parent.heading)
        parent_id = parent.parent_id
    return list(reversed(headings))


def retrieval_text_for(
    *,
    citation: str,
    ancestor_headings: list[str],
    heading: str | None,
    text: str,
    phrasing: str | None = None,
) -> str:
    parts = [citation, *ancestor_headings]
    if heading:
        parts.append(heading)
    # Reviewed everyday phrasing helps search find terse provisions; it is
    # search text only and never replaces the authoritative wording.
    if phrasing:
        parts.append(phrasing)
    parts.append(text)
    return "\n".join(part.strip() for part in parts if part and part.strip())


def split_legal_text(text: str, *, max_chars: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    definitions = _split_definitions(cleaned)
    if definitions:
        return [
            segment
            for definition in definitions
            for segment in _split_clauses(definition, max_chars=max_chars)
        ]
    return _split_clauses(cleaned, max_chars=max_chars)


def _split_definitions(text: str) -> list[str]:
    # One segment per defined term, so a question about one term is not
    # diluted by the rest of a long interpretation section. The opening
    # words ("In this Act -") stay with the first definition.
    pieces = [piece.strip() for piece in _DEFINITION_START_RE.split(text)]
    pieces = [piece for piece in pieces if piece]
    if pieces and not _DEFINITION_START_RE.match(pieces[0]):
        pieces[:2] = ["\n".join(pieces[:2])]
    if len(pieces) < _MIN_DEFINITIONS_TO_SPLIT:
        return []
    return pieces


def _split_clauses(cleaned: str, *, max_chars: int) -> list[str]:
    pieces = _CLAUSE_BOUNDARY_RE.split(cleaned)
    segments: list[str] = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = f"{current} {piece}".strip() if current else piece
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            segments.append(current)
        if len(piece) <= max_chars:
            current = piece
        else:
            hard_segments = _split_long_piece(piece, max_chars=max_chars)
            segments.extend(hard_segments[:-1])
            current = hard_segments[-1] if hard_segments else ""
    if current:
        segments.append(current)
    return segments


def _split_long_piece(piece: str, *, max_chars: int) -> list[str]:
    segments: list[str] = []
    remaining = piece
    while len(remaining) > max_chars:
        split_at = remaining.rfind(" ", 0, max_chars + 1)
        if split_at <= 0:
            split_at = max_chars
        segments.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        segments.append(remaining)
    return segments


def _entry_sort_key(
    entry: CorpusReleaseEntry,
    versions_by_id: dict[uuid.UUID, ProvisionVersion],
    provisions_by_id: dict[uuid.UUID, Provision],
) -> tuple[str, str]:
    version = versions_by_id.get(entry.provision_version_id)
    if not version:
        return ("", str(entry.provision_version_id))
    provision = provisions_by_id.get(version.provision_id)
    if not provision:
        return ("", str(version.id))
    return (provision.sort_key, provision.canonical_path)


def _document_id(
    *,
    release_version: str,
    provision_version_id: uuid.UUID,
    segment_index: int,
    retrieval_text: str,
) -> str:
    return _sha256(
        json.dumps(
            {
                "release_version": release_version,
                "provision_version_id": str(provision_version_id),
                "segment_index": segment_index,
                "retrieval_text": retrieval_text,
            },
            sort_keys=True,
        )
    )


def deterministic_segment_id(
    *,
    release_id: uuid.UUID,
    provision_version_id: uuid.UUID,
    segment_index: int,
    retrieval_text_sha256: str,
) -> uuid.UUID:
    """Return the stable database identity for a derived retrieval segment."""
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        ":".join(
            (
                str(release_id),
                str(provision_version_id),
                str(segment_index),
                retrieval_text_sha256,
            )
        ),
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))
