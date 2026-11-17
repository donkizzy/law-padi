import uuid
from typing import Literal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.legal.enums import InstrumentType, ProvisionKind


class LegalSearchRequest(SQLModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    index_kind: Literal["enacted", "proposals"] = "enacted"
    mode: Literal["auto", "semantic"] = "auto"
    instrument: str | None = Field(
        default=None,
        max_length=255,
        schema_extra={"pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$"},
    )
    release_version: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter a section reference or topic")
        return value


class InstrumentIdentity(SQLModel):
    # Defaults retain compatibility with saved Constitution evidence snapshots.
    instrument_slug: str = "constitution-1999"
    instrument_title: str = "Constitution of the Federal Republic of Nigeria 1999"
    instrument_short_title: str | None = None
    instrument_type: InstrumentType = InstrumentType.CONSTITUTION
    short_citation: str | None = None


class ProvisionNotice(SQLModel):
    # Stable key and params so clients can show the notice in the reader's language.
    code: str
    text: str
    params: dict[str, str] = Field(default_factory=dict)


class ProvisionReference(InstrumentIdentity):
    id: uuid.UUID
    canonical_path: str
    kind: ProvisionKind
    number: str | None = None
    heading: str | None = None
    title: str | None = None
    citation: str
    has_text: bool
    authoritative_text: str | None = None
    notices: list[ProvisionNotice] = Field(default_factory=list)


class LegalSearchResult(InstrumentIdentity):
    canonical_path: str
    citation: str
    heading: str | None = None
    title: str | None = None
    ancestor_headings: list[str]
    authoritative_text: str
    source_document_id: uuid.UUID
    source_page_start: int | None = None
    source_page_end: int | None = None
    legal_status: str
    release_version: str
    dense_rank: int | None = None
    lexical_rank: int | None = None
    hybrid_score: float
    provision_id: uuid.UUID
    provision_version_id: uuid.UUID
    release_id: uuid.UUID
    kind: ProvisionKind
    edition_label: str
    source_title: str
    source_authority: str
    source_url: str
    source_content_url: str
    ancestors: list[ProvisionReference]
    children: list[ProvisionReference]
    notices: list[ProvisionNotice] = Field(default_factory=list)


class CitationOutcome(SQLModel):
    reference: str
    status: Literal["resolved", "ambiguous", "missing", "unsupported"]
    evidence_ids: list[str] = Field(default_factory=list)
    message: str | None = None


class EvidenceItem(InstrumentIdentity):
    evidence_id: str
    provision_id: uuid.UUID
    provision_version_id: uuid.UUID
    canonical_path: str
    citation: str
    title: str | None = None
    authoritative_text: str
    text_sha256: str
    ancestor_citations: list[str]
    legal_status: str
    edition_label: str
    release_id: uuid.UUID
    release_version: str
    source_document_id: uuid.UUID
    source_title: str
    source_authority: str
    source_url: str
    source_content_url: str
    source_page_start: int | None = None
    source_page_end: int | None = None
    notices: list[ProvisionNotice] = Field(default_factory=list)


class LegalSearchResponse(SQLModel):
    data: list[LegalSearchResult]
    count: int
    outcome: Literal[
        "exact", "matches", "ambiguous", "not_found", "unsupported_reference", "partial"
    ] = "matches"
    retrieval_mode: Literal["exact", "hybrid", "lexical"] = "exact"
    message: str | None = None
    # Stable key for message, so clients can show it in the reader's language.
    message_code: str | None = None
    release_version: str
    edition_label: str
    citation_outcomes: list[CitationOutcome] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    # Language detected in the query, and the English text searched when the
    # query was translated.
    query_language: str | None = None
    searched_query: str | None = None


class LegalReleasePublic(SQLModel):
    release_id: uuid.UUID
    release_version: str
    index_kind: str
    embedding_run_id: uuid.UUID
    retrieval_index_build_id: uuid.UUID
    edition_label: str
    available: bool = True
    legal_statuses: list[str]


class LegalInstrumentPublic(SQLModel):
    slug: str
    title: str
    short_title: str | None = None
    instrument_type: InstrumentType
    edition_label: str
    edition_note: str
    section_count: int
    legal_statuses: list[str]


class LegalInstrumentsPublic(SQLModel):
    data: list[LegalInstrumentPublic]
    count: int
    release_version: str


class ProvisionTreePublic(SQLModel):
    data: list[ProvisionReference]
    count: int
    release_version: str
    edition_label: str
    parent: ProvisionReference | None = None
    scope: Literal["children", "all"] = "children"
    instrument_slug: str = "constitution-1999"
