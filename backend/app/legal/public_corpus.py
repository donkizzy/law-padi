"""Published legal text and hierarchy, independent of derived retrieval segments."""

import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.pgvector_repository import PgVectorRetrievalError, active_target
from app.legal.enums import CorpusReleaseStatus, ProvisionKind
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.schemas import LegalSearchResult, ProvisionReference
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

    def citation(self, provision: Provision) -> str:
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

    def reference(
        self, provision: Provision, *, context: bool = False
    ) -> ProvisionReference:
        version = self.versions.get(provision.id)
        return ProvisionReference(
            id=provision.id,
            canonical_path=provision.canonical_path,
            kind=provision.kind,
            number=provision.number,
            heading=provision.heading,
            title=section_title(provision.canonical_path),
            citation=self.citation(provision),
            has_text=version is not None,
            authoritative_text=version.text if context and version else None,
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
            canonical_path=provision.canonical_path,
            citation=self.citation(provision),
            heading=provision.heading,
            title=section_title(provision.canonical_path),
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
            edition_label=self.edition_label,
            source_title=source.title,
            source_authority=source.authority,
            source_url=source.source_url,
            source_content_url=f"{settings.API_V1_STR}/legal/sources/{source.id}/content?{urlencode({'release_version': self.release.version, 'index_kind': self.index_kind})}",
            ancestors=[self.reference(p, context=context) for p in ancestors],
            children=[self.reference(p) for p in self.children(provision.id)],
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
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section or subsection"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    return PublicCorpus(release, provisions, versions, sources, index_kind)


def load_reference_corpus(
    session: Session,
    release: CorpusRelease,
    suffixes: list[str],
    *,
    index_kind: str = "enacted",
) -> PublicCorpus:
    """Load exact matches, their published children, and only needed ancestry."""
    if not suffixes:
        return PublicCorpus(release, {}, {}, {}, index_kind)
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
                *[col(Provision.canonical_path).endswith(suffix) for suffix in suffixes]
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
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section or subsection"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    return PublicCorpus(release, provisions, versions, sources, index_kind)


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
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section or subsection"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    return PublicCorpus(release, provisions, versions, sources, index_kind)
