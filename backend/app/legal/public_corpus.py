"""Published legal text and hierarchy, independent of derived retrieval segments."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.pgvector_repository import PgVectorRetrievalError, active_target
from app.legal.citations import qualify_citation, short_citation
from app.legal.enums import CorpusReleaseStatus, InstrumentType, ProvisionKind
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.notices import provision_notices
from app.legal.references import SectionReference, matches_reference
from app.legal.release_scope import release_instruments
from app.legal.schemas import InstrumentIdentity, LegalSearchResult, ProvisionReference
from app.legal.topics import section_title

PUBLIC_RELEASE_STATUSES = (CorpusReleaseStatus.PRODUCTION, CorpusReleaseStatus.RETIRED)


def published_release(
    session: Session, *, index_kind: str = "enacted", release_version: str | None = None
) -> CorpusRelease:
    if release_version:
        release = session.exec(
            select(CorpusRelease).where(CorpusRelease.version == release_version)
        ).first()
        if not release or release.status not in PUBLIC_RELEASE_STATUSES:
            raise HTTPException(
                status_code=404, detail="Published source edition was not found"
            )
        return release
    target = active_target(session, index_kind=index_kind)
    release = session.get(CorpusRelease, target.release_id)
    if not release or release.status != CorpusReleaseStatus.PRODUCTION:
        raise PgVectorRetrievalError("No published legal corpus is available")
    return release


@dataclass
class PublicCorpus:
    release: CorpusRelease
    provisions: dict[uuid.UUID, Provision]
    versions: dict[uuid.UUID, ProvisionVersion]
    sources: dict[uuid.UUID, SourceDocument]
    index_kind: str = "enacted"
    instruments: dict[uuid.UUID, LegalInstrument] = field(default_factory=dict)

    def instrument_identity(self, provision: Provision) -> InstrumentIdentity:
        instrument = self.instruments[provision.instrument_id]
        return InstrumentIdentity(
            instrument_slug=instrument.slug,
            instrument_title=instrument.title,
            instrument_short_title=instrument.short_title,
            instrument_type=instrument.instrument_type,
            short_citation=short_citation(self._citation(provision), instrument),
        )

    @property
    def edition_label(self) -> str:
        report = self.release.validation_report or {}
        evidence = report.get("source_edition_review", {})
        if isinstance(evidence, dict) and isinstance(evidence.get("edition"), str):
            return str(evidence["edition"])
        if self.versions and all(
            str(v.legal_status) == "historical" for v in self.versions.values()
        ):
            return "Historical source edition"
        return "Published source edition"

    def lineage(self, provision: Provision) -> list[Provision]:
        nodes: list[Provision] = []
        seen = {provision.id}
        parent_id = provision.parent_id
        while parent_id:
            parent = self.provisions.get(parent_id)
            if parent is None or parent_id in seen:
                raise PgVectorRetrievalError(
                    "Published provision hierarchy is incomplete"
                )
            seen.add(parent_id)
            nodes.append(parent)
            parent_id = parent.parent_id
        return list(reversed(nodes))

    def provision_edition_label(self, provision: Provision) -> str:
        """Keep each instrument's edition when a release combines several laws."""
        instrument = self.instruments[provision.instrument_id]
        if instrument.instrument_type == InstrumentType.ACT:
            return "As enacted, may have been amended."
        composition = (self.release.validation_report or {}).get("composition", {})
        members = (
            composition.get("members", []) if isinstance(composition, dict) else []
        )
        for member in members if isinstance(members, list) else []:
            if not isinstance(member, dict):
                continue
            identities = member.get("instruments", [])
            if not isinstance(identities, list) or not any(
                isinstance(item, dict) and item.get("slug") == instrument.slug
                for item in identities
            ):
                continue
            review = member.get("source_edition_review", {})
            if isinstance(review, dict) and isinstance(review.get("edition"), str):
                return str(review["edition"])
        return self.edition_label

    def citation(self, provision: Provision) -> str:
        return qualify_citation(
            self._citation(provision), self.instruments[provision.instrument_id]
        )

    def _citation(self, provision: Provision) -> str:
        nodes = [*self.lineage(provision), provision]
        section = next(
            (node for node in nodes if node.kind == ProvisionKind.SECTION), None
        )
        if section:
            suffix = "".join(
                f"({node.number})"
                for node in nodes
                if node.kind in (ProvisionKind.SUBSECTION, ProvisionKind.PARAGRAPH)
            )
            return f"Section {section.number}{suffix}"
        return " → ".join(
            f"{str(node.kind).replace('_', ' ').title()} {node.number or ''}".strip()
            for node in nodes
        )

    def title(self, provision: Provision) -> str | None:
        title = section_title(provision.canonical_path)
        if (
            title
            or self.instruments[provision.instrument_id].instrument_type
            != InstrumentType.ACT
        ):
            return title
        # Accepted Act headings come from the parsed Arrangement of Sections.
        # Do not make the partial navigation catalogue the only display source.
        for node in reversed([*self.lineage(provision), provision]):
            if node.kind == ProvisionKind.SECTION and node.heading:
                return node.heading
        return provision.heading

    def reference(
        self, provision: Provision, *, context: bool = False
    ) -> ProvisionReference:
        version = self.versions.get(provision.id)
        return ProvisionReference(
            **self.instrument_identity(provision).model_dump(),
            id=provision.id,
            canonical_path=provision.canonical_path,
            kind=provision.kind,
            number=provision.number,
            heading=provision.heading,
            title=self.title(provision),
            citation=self.citation(provision),
            has_text=version is not None,
            authoritative_text=version.text if context and version else None,
            notices=provision_notices(provision.canonical_path),
        )

    def children(self, parent_id: uuid.UUID | None) -> list[Provision]:
        return sorted(
            (p for p in self.provisions.values() if p.parent_id == parent_id),
            key=lambda p: (p.sort_key, p.canonical_path),
        )

    def result(
        self,
        provision: Provision,
        *,
        score: float = 1.0,
        dense_rank: int | None = None,
        lexical_rank: int | None = None,
        context: bool = False,
    ) -> LegalSearchResult:
        version = self.versions[provision.id]
        source = self.sources[version.source_document_id]
        ancestors = self.lineage(provision)
        return LegalSearchResult(
            **self.instrument_identity(provision).model_dump(),
            canonical_path=provision.canonical_path,
            citation=self.citation(provision),
            heading=provision.heading,
            title=self.title(provision),
            ancestor_headings=[p.heading for p in ancestors if p.heading],
            authoritative_text=version.text,
            source_document_id=source.id,
            source_page_start=version.source_page_start,
            source_page_end=version.source_page_end,
            legal_status=str(version.legal_status),
            release_version=self.release.version,
            hybrid_score=score,
            dense_rank=dense_rank,
            lexical_rank=lexical_rank,
            provision_id=provision.id,
            provision_version_id=version.id,
            release_id=self.release.id,
            kind=provision.kind,
            edition_label=self.provision_edition_label(provision),
            source_title=source.title,
            source_authority=source.authority,
            source_url=source.source_url,
            source_content_url=f"{settings.API_V1_STR}/legal/sources/{source.id}/content?{urlencode({'release_version': self.release.version, 'index_kind': self.index_kind})}",
            ancestors=[self.reference(p, context=context) for p in ancestors],
            children=[self.reference(p) for p in self.children(provision.id)],
            notices=provision_notices(provision.canonical_path),
        )


def load_public_corpus(
    session: Session, release: CorpusRelease, *, index_kind: str = "enacted"
) -> PublicCorpus:
    rows = session.exec(
        select(ProvisionVersion, Provision, SourceDocument)
        .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
        .join(
            SourceDocument,
            col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
        )
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.provision_version_id) == col(ProvisionVersion.id),
        )
        .where(CorpusReleaseEntry.release_id == release.id)
    ).all()
    expected_proposed = index_kind == "proposals"
    versions = {
        p.id: v
        for v, p, _source in rows
        if (str(v.legal_status) == "proposed") == expected_proposed
    }
    provisions = {p.id: p for _v, p, _s in rows if p.id in versions}
    sources = {s.id: s for _v, p, s in rows if p.id in versions}
    instrument_ids = {p.instrument_id for p in provisions.values()}
    all_nodes = (
        {
            p.id: p
            for p in session.exec(
                select(Provision).where(
                    col(Provision.instrument_id).in_(instrument_ids)
                )
            ).all()
        }
        if instrument_ids
        else {}
    )
    for provision in list(provisions.values()):
        seen = {provision.id}
        child = provision
        while child.parent_id:
            parent = all_nodes.get(child.parent_id)
            if not parent or parent.id in seen:
                raise PgVectorRetrievalError(
                    "Published provision hierarchy is incomplete"
                )
            if (
                child.kind == ProvisionKind.SUBSECTION
                and parent.kind != ProvisionKind.SECTION
            ):
                raise PgVectorRetrievalError("Subsection is not attached to a section")
            # Acts nest sub-paragraphs, as in section 123(b)(i).
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
                ProvisionKind.PARAGRAPH,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section, subsection or paragraph"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    return _assemble_corpus(session, release, provisions, versions, sources, index_kind)


def _assemble_corpus(
    session: Session,
    release: CorpusRelease,
    provisions: dict[uuid.UUID, Provision],
    versions: dict[uuid.UUID, ProvisionVersion],
    sources: dict[uuid.UUID, SourceDocument],
    index_kind: str,
) -> PublicCorpus:
    instrument_ids = {provision.instrument_id for provision in provisions.values()}
    instruments = (
        {
            instrument.id: instrument
            for instrument in session.exec(
                select(LegalInstrument).where(
                    col(LegalInstrument.id).in_(instrument_ids)
                )
            ).all()
        }
        if instrument_ids
        else {}
    )
    if instrument_ids != instruments.keys():
        raise PgVectorRetrievalError("Published provision instrument is missing")
    return PublicCorpus(release, provisions, versions, sources, index_kind, instruments)


def load_reference_corpus(
    session: Session,
    release: CorpusRelease,
    references: Sequence[SectionReference],
    *,
    index_kind: str = "enacted",
) -> PublicCorpus:
    """Load exact matches, their published children, and only needed ancestry."""
    instruments = release_instruments(session, release.id, index_kind=index_kind)
    if not references:
        return PublicCorpus(release, {}, {}, {}, index_kind, instruments)
    statement = (
        select(ProvisionVersion, Provision, SourceDocument)
        .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
        .join(
            SourceDocument,
            col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
        )
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.provision_version_id) == col(ProvisionVersion.id),
        )
        .where(
            CorpusReleaseEntry.release_id == release.id,
            or_(
                *[
                    matches_reference(col(Provision.canonical_path), reference)
                    for reference in references
                ]
            ),
        )
    )
    expected_proposed = index_kind == "proposals"
    matches = [
        row
        for row in session.exec(statement).all()
        if (str(row[0].legal_status) == "proposed") == expected_proposed
    ]
    selected_ids = [provision.id for _version, provision, _source in matches]
    children = (
        [
            row
            for row in session.exec(
                select(ProvisionVersion, Provision, SourceDocument)
                .join(
                    Provision, col(Provision.id) == col(ProvisionVersion.provision_id)
                )
                .join(
                    SourceDocument,
                    col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
                )
                .join(
                    CorpusReleaseEntry,
                    col(CorpusReleaseEntry.provision_version_id)
                    == col(ProvisionVersion.id),
                )
                .where(
                    CorpusReleaseEntry.release_id == release.id,
                    col(Provision.parent_id).in_(selected_ids),
                )
            ).all()
            if (str(row[0].legal_status) == "proposed") == expected_proposed
        ]
        if selected_ids
        else []
    )
    rows = [*matches, *children]
    versions = {provision.id: version for version, provision, _source in rows}
    provisions = {provision.id: provision for _version, provision, _source in rows}
    sources = {source.id: source for _version, _provision, source in rows}
    for provision in list(provisions.values()):
        seen = {provision.id}
        child = provision
        while child.parent_id:
            parent = provisions.get(child.parent_id) or session.get(
                Provision, child.parent_id
            )
            if parent is None or parent.id in seen:
                raise PgVectorRetrievalError(
                    "Published provision hierarchy is incomplete"
                )
            if (
                child.kind == ProvisionKind.SUBSECTION
                and parent.kind != ProvisionKind.SECTION
            ):
                raise PgVectorRetrievalError("Subsection is not attached to a section")
            # Acts nest sub-paragraphs, as in section 123(b)(i).
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
                ProvisionKind.PARAGRAPH,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section, subsection or paragraph"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    corpus = _assemble_corpus(
        session, release, provisions, versions, sources, index_kind
    )
    corpus.instruments.update(instruments)
    return corpus


def load_ranked_corpus(
    session: Session,
    release: CorpusRelease,
    version_ids: list[uuid.UUID],
    *,
    index_kind: str = "enacted",
) -> PublicCorpus:
    """Reload only ranked canonical versions, their children, and ancestry."""
    if not version_ids:
        return PublicCorpus(release, {}, {}, {}, index_kind)
    rows = session.exec(
        select(ProvisionVersion, Provision, SourceDocument)
        .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
        .join(
            SourceDocument,
            col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
        )
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.provision_version_id) == col(ProvisionVersion.id),
        )
        .where(
            CorpusReleaseEntry.release_id == release.id,
            col(ProvisionVersion.id).in_(version_ids),
        )
    ).all()
    expected_proposed = index_kind == "proposals"
    selected = [
        (version, provision, source)
        for version, provision, source in rows
        if (str(version.legal_status) == "proposed") == expected_proposed
    ]
    if {version.id for version, _provision, _source in selected} != set(version_ids):
        raise PgVectorRetrievalError(
            "Search result does not belong to the published corpus"
        )
    selected_ids = [provision.id for _version, provision, _source in selected]
    children = session.exec(
        select(ProvisionVersion, Provision, SourceDocument)
        .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
        .join(
            SourceDocument,
            col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
        )
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.provision_version_id) == col(ProvisionVersion.id),
        )
        .where(
            CorpusReleaseEntry.release_id == release.id,
            col(Provision.parent_id).in_(selected_ids),
        )
    ).all()
    published_rows = [
        *selected,
        *(
            (version, provision, source)
            for version, provision, source in children
            if (str(version.legal_status) == "proposed") == expected_proposed
        ),
    ]
    versions = {provision.id: version for version, provision, _ in published_rows}
    provisions = {provision.id: provision for _, provision, _ in published_rows}
    sources = {source.id: source for _, _, source in published_rows}
    for provision in list(provisions.values()):
        seen = {provision.id}
        child = provision
        while child.parent_id:
            parent = provisions.get(child.parent_id) or session.get(
                Provision, child.parent_id
            )
            if parent is None or parent.id in seen:
                raise PgVectorRetrievalError(
                    "Published provision hierarchy is incomplete"
                )
            if (
                child.kind == ProvisionKind.SUBSECTION
                and parent.kind != ProvisionKind.SECTION
            ):
                raise PgVectorRetrievalError("Subsection is not attached to a section")
            # Acts nest sub-paragraphs, as in section 123(b)(i).
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
                ProvisionKind.PARAGRAPH,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section, subsection or paragraph"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    return _assemble_corpus(session, release, provisions, versions, sources, index_kind)
