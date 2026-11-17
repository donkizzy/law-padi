"""Published legal text and hierarchy, independent of derived retrieval segments."""

import logging
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.pgvector_repository import PgVectorRetrievalError, active_target
from app.legal.citations import qualify_citation, rules_citation, short_citation
from app.legal.enums import (
    CorpusReleaseStatus,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
)
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

logger = logging.getLogger(__name__)

PUBLIC_RELEASE_STATUSES = (CorpusReleaseStatus.PRODUCTION, CorpusReleaseStatus.RETIRED)
# A loaded corpus holds every provision of a release, which is large. The
# production release of each index stays cached until another release replaces
# it. Other public releases, read through saved links, are built from the rows
# they share with production, so each adds little memory; the least recently
# used beyond this many are dropped.
RETIRED_CORPUS_CACHE_SIZE = 4
# Released text cannot change, but source titles can be corrected and
# provisions are shared between releases, so a corpus older than this is
# reloaded in the background while the loaded copy is still served.
PUBLIC_CORPUS_REFRESH_SECONDS = 15 * 60
PUBLIC_CORPUS_RETRY_SECONDS = 60
# Bounds the bind parameters of one query when loading versions by id.
_VERSION_BATCH = 5000


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
    _by_path: dict[str, Provision] | None = field(default=None, repr=False)
    _by_parent: dict[uuid.UUID | None, list[Provision]] | None = field(
        default=None, repr=False
    )

    def index(self) -> None:
        """Build the path and parent lookups, carried over by dataclasses.replace."""
        by_parent: dict[uuid.UUID | None, list[Provision]] = {}
        for provision in sorted(
            self.provisions.values(), key=lambda p: (p.sort_key, p.canonical_path)
        ):
            by_parent.setdefault(provision.parent_id, []).append(provision)
        self._by_parent = by_parent
        self._by_path = {p.canonical_path: p for p in self.provisions.values()}

    def provision_at(self, canonical_path: str) -> Provision | None:
        if self._by_path is None:
            self.index()
        return (self._by_path or {}).get(canonical_path)

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
        if rule := rules_citation(provision.canonical_path):
            return rule
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
        if self._by_parent is None:
            self.index()
        return (self._by_parent or {}).get(parent_id, [])

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
    _attach_ancestry(provisions, all_nodes.get)
    return _assemble_corpus(session, release, provisions, versions, sources, index_kind)


def _attach_ancestry(
    provisions: dict[uuid.UUID, Provision],
    node: Callable[[uuid.UUID], Provision | None],
) -> None:
    """Add every ancestor of the published provisions, checking the structure."""
    for provision in list(provisions.values()):
        seen = {provision.id}
        child = provision
        while child.parent_id:
            parent = node(child.parent_id)
            if not parent or parent.id in seen:
                raise PgVectorRetrievalError(
                    "Published provision hierarchy is incomplete"
                )
            if (
                child.kind == ProvisionKind.SUBSECTION
                and parent.kind != ProvisionKind.SECTION
            ):
                raise PgVectorRetrievalError("Subsection is not attached to a section")
            # Acts nest sub-paragraphs, as in section 123(b)(i), and schedule
            # items hold lettered paragraphs, as in NDPA Schedule 1 item 16.
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
                ProvisionKind.PARAGRAPH,
                ProvisionKind.SCHEDULE_ITEM,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section, subsection, paragraph or schedule item"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent


def _status_filter(index_kind: str) -> ColumnElement[bool]:
    status = col(ProvisionVersion.legal_status)
    if index_kind == "proposals":
        return status == LegalStatus.PROPOSED
    return status != LegalStatus.PROPOSED


def derive_public_corpus(
    session: Session,
    release: CorpusRelease,
    base: PublicCorpus,
    *,
    index_kind: str = "enacted",
) -> PublicCorpus | None:
    """Build a release's corpus from the rows it shares with a loaded corpus.

    Releases are composed from mostly the same provision versions, so only the
    versions and ancestors the base lacks are read. The result is the same as
    load_public_corpus, and shares the base's row objects. Returns None when a
    release holds two versions of one provision, which only a full load
    resolves.
    """
    version_ids = set(
        session.exec(
            select(CorpusReleaseEntry.provision_version_id)
            .join(
                ProvisionVersion,
                col(ProvisionVersion.id)
                == col(CorpusReleaseEntry.provision_version_id),
            )
            .where(
                CorpusReleaseEntry.release_id == release.id,
                _status_filter(index_kind),
            )
        ).all()
    )
    shared = {version.id: version for version in base.versions.values()}
    rows: list[tuple[ProvisionVersion, Provision, SourceDocument]] = []
    for version_id in version_ids & shared.keys():
        version = shared[version_id]
        source = (
            base.sources.get(version.source_document_id)
            if version.source_document_id
            else None
        )
        if source is None:
            return None
        rows.append((version, base.provisions[version.provision_id], source))
    missing = sorted(version_ids - shared.keys())
    for start in range(0, len(missing), _VERSION_BATCH):
        rows.extend(
            session.exec(
                select(ProvisionVersion, Provision, SourceDocument)
                .join(
                    Provision, col(Provision.id) == col(ProvisionVersion.provision_id)
                )
                .join(
                    SourceDocument,
                    col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
                )
                .where(
                    col(ProvisionVersion.id).in_(
                        missing[start : start + _VERSION_BATCH]
                    )
                )
            ).all()
        )
    versions = {provision.id: version for version, provision, _ in rows}
    if len(versions) != len(rows):
        return None
    provisions = {provision.id: provision for _, provision, _ in rows}
    sources = {source.id: source for _, _, source in rows}
    instrument_ids = {provision.instrument_id for provision in provisions.values()}
    nodes = dict(base.provisions)
    pending = {
        provision.parent_id
        for provision in provisions.values()
        if provision.parent_id and provision.parent_id not in nodes
    }
    while pending:
        fetched = session.exec(
            select(Provision).where(col(Provision.id).in_(pending))
        ).all()
        nodes.update((provision.id, provision) for provision in fetched)
        pending = {
            provision.parent_id
            for provision in fetched
            if provision.parent_id and provision.parent_id not in nodes
        }

    # A full load only finds ancestors within the release's own instruments.
    def node(provision_id: uuid.UUID) -> Provision | None:
        found = nodes.get(provision_id)
        return found if found and found.instrument_id in instrument_ids else None

    _attach_ancestry(provisions, node)
    return _assemble_corpus(session, release, provisions, versions, sources, index_kind)


_CacheKey = tuple[uuid.UUID, str]


@dataclass(frozen=True)
class _CachedCorpus:
    corpus: PublicCorpus
    refresh_at: float


# The lock guards these maps only and is never held while a corpus loads, so a
# slow load delays only the requests waiting for that same release.
_cache_lock = threading.Lock()
_corpus_cache: OrderedDict[_CacheKey, _CachedCorpus] = OrderedDict()
_production: dict[str, uuid.UUID] = {}
_loads: dict[_CacheKey, Future[PublicCorpus]] = {}
_refreshes: dict[_CacheKey, tuple[int, Future[None]]] = {}
_generation = 0
_refresher: ThreadPoolExecutor | None = None


def clear_public_corpus_cache() -> None:
    """Drop every cached corpus, after any background refresh has finished."""
    global _generation
    with _cache_lock:
        _generation += 1
        pending = [future for _, future in _refreshes.values()]
        _corpus_cache.clear()
        _production.clear()
        _loads.clear()
        _refreshes.clear()
    for future in pending:
        future.result()


def wait_for_corpus_refreshes() -> None:
    """Block until the background refreshes scheduled so far have finished."""
    with _cache_lock:
        pending = [future for _, future in _refreshes.values()]
    for future in pending:
        future.result()


def _detach(session: Session, corpus: PublicCorpus) -> PublicCorpus:
    # The entities outlive this session and are read by other threads. A
    # derived corpus also holds rows that an earlier load already detached.
    for rows in (
        corpus.provisions,
        corpus.versions,
        corpus.sources,
        corpus.instruments,
    ):
        for row in rows.values():
            if row in session:
                session.expunge(row)
    corpus.index()
    return corpus


def _production_corpus(session: Session, index_kind: str) -> PublicCorpus | None:
    try:
        production = published_release(session, index_kind=index_kind)
    except PgVectorRetrievalError:
        return None
    return cached_public_corpus(session, production, index_kind=index_kind)


def _load_corpus(
    session: Session, release: CorpusRelease, index_kind: str
) -> PublicCorpus:
    if release.status != CorpusReleaseStatus.PRODUCTION:
        base = _production_corpus(session, index_kind)
        if base is not None and base.release.id != release.id:
            derived = derive_public_corpus(
                session, release, base, index_kind=index_kind
            )
            if derived is not None:
                return _detach(session, derived)
    return _detach(session, load_public_corpus(session, release, index_kind=index_kind))


def _track_status_locked(key: _CacheKey, status: CorpusReleaseStatus) -> None:
    release_id, index_kind = key
    if status == CorpusReleaseStatus.PRODUCTION:
        _production[index_kind] = release_id
    elif _production.get(index_kind) == release_id:
        del _production[index_kind]
    others = [
        cached for cached in _corpus_cache if _production.get(cached[1]) != cached[0]
    ]
    while len(others) > RETIRED_CORPUS_CACHE_SIZE:
        del _corpus_cache[others.pop(0)]


def _store_locked(
    key: _CacheKey,
    corpus: PublicCorpus,
    status: CorpusReleaseStatus,
    generation: int,
) -> None:
    if generation != _generation:
        return
    _corpus_cache[key] = _CachedCorpus(
        corpus, time.monotonic() + PUBLIC_CORPUS_REFRESH_SECONDS
    )
    _corpus_cache.move_to_end(key)
    _track_status_locked(key, status)


def _refresh(key: _CacheKey, generation: int) -> None:
    from app.core.db import engine

    release_id, index_kind = key
    try:
        with Session(engine) as session:
            release = session.get(CorpusRelease, release_id)
            if release is None or release.status not in PUBLIC_RELEASE_STATUSES:
                with _cache_lock:
                    if generation == _generation:
                        _corpus_cache.pop(key, None)
                return
            corpus = _load_corpus(session, release, index_kind)
            with _cache_lock:
                _store_locked(key, corpus, release.status, generation)
    except Exception:
        logger.exception("Public corpus refresh failed; the loaded copy is kept")
        with _cache_lock:
            entry = _corpus_cache.get(key)
            if entry is not None and generation == _generation:
                _corpus_cache[key] = replace(
                    entry, refresh_at=time.monotonic() + PUBLIC_CORPUS_RETRY_SECONDS
                )
    finally:
        with _cache_lock:
            current = _refreshes.get(key)
            if current is not None and current[0] == generation:
                del _refreshes[key]


def _schedule_refresh_locked(key: _CacheKey) -> None:
    global _refresher
    if key in _refreshes:
        return
    if _refresher is None:
        _refresher = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="public-corpus-refresh"
        )
    _refreshes[key] = (_generation, _refresher.submit(_refresh, key, _generation))


def cached_public_corpus(
    session: Session, release: CorpusRelease, *, index_kind: str = "enacted"
) -> PublicCorpus:
    """Share one read-only corpus per release and index between requests.

    Callers resolve the release themselves, so publication status is never
    cached. Each caller gets its own PublicCorpus carrying that release, but
    the provision, version, source and instrument mappings and their rows are
    shared with other threads and must not be modified.

    Concurrent requests for a release that is not cached wait for one load;
    requests for other releases are not held up by it. A corpus due for
    refresh is still served while a background thread reloads it.
    """
    key = (release.id, index_kind)
    with _cache_lock:
        _track_status_locked(key, release.status)
        entry = _corpus_cache.get(key)
        if entry is not None:
            _corpus_cache.move_to_end(key)
            if time.monotonic() >= entry.refresh_at:
                _schedule_refresh_locked(key)
            return replace(entry.corpus, release=release)
        load = _loads.get(key)
        owner = load is None
        if load is None:
            load = Future()
            _loads[key] = load
        generation = _generation
    if not owner:
        return replace(load.result(), release=release)
    try:
        corpus = _load_corpus(session, release, index_kind)
    except BaseException as exc:
        with _cache_lock:
            if _loads.get(key) is load:
                del _loads[key]
        load.set_exception(exc)
        raise
    with _cache_lock:
        _store_locked(key, corpus, release.status, generation)
        if _loads.get(key) is load:
            del _loads[key]
    load.set_result(corpus)
    return replace(corpus, release=release)


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
            # Acts nest sub-paragraphs, as in section 123(b)(i), and schedule
            # items hold lettered paragraphs, as in NDPA Schedule 1 item 16.
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
                ProvisionKind.PARAGRAPH,
                ProvisionKind.SCHEDULE_ITEM,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section, subsection, paragraph or schedule item"
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
            # Acts nest sub-paragraphs, as in section 123(b)(i), and schedule
            # items hold lettered paragraphs, as in NDPA Schedule 1 item 16.
            if child.kind == ProvisionKind.PARAGRAPH and parent.kind not in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
                ProvisionKind.PARAGRAPH,
                ProvisionKind.SCHEDULE_ITEM,
            ):
                raise PgVectorRetrievalError(
                    "Paragraph is not attached to a section, subsection, paragraph or schedule item"
                )
            seen.add(parent.id)
            provisions[parent.id] = parent
            child = parent
    return _assemble_corpus(session, release, provisions, versions, sources, index_kind)
