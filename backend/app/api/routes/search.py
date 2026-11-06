import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.chat.search_language import search_query
from app.core.config import settings
from app.ingestion.blob_store import BlobStoreError
from app.ingestion.embedding import DenseEmbeddingProvider
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
    active_target,
)
from app.ingestion.r2_blob_store import R2BlobStore
from app.ingestion.service import get_blob_store
from app.legal.enums import (
    InstrumentType,
    LegalStatus,
    ProvisionKind,
    VectorIndexStatus,
)
from app.legal.evidence import (
    default_embedding_provider,
    exact_lookup,
    message_code,
    semantic_lookup,
)
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
)
from app.legal.public_corpus import (
    PUBLIC_RELEASE_STATUSES,
    PublicCorpus,
    cached_public_corpus,
    load_ranked_corpus,
    load_reference_corpus,
    published_release,
)
from app.legal.references import (
    CONSTITUTION_SLUG,
    SectionReference,
    parse_section_reference,
)
from app.legal.release_scope import release_instruments
from app.legal.schemas import (
    LegalInstrumentPublic,
    LegalInstrumentsPublic,
    LegalReleasePublic,
    LegalSearchRequest,
    LegalSearchResponse,
    LegalSearchResult,
    ProvisionTreePublic,
)

router = APIRouter(prefix="/legal", tags=["legal"])
IndexKind = Annotated[str, Query(pattern="^(enacted|proposals)$")]
ReleaseVersion = Annotated[str | None, Query(min_length=1, max_length=128)]
InstrumentSlug = Annotated[
    str | None, Query(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)
]


def legal_session(session: SessionDep) -> Iterator[Session]:
    try:
        yield session
    except PgVectorRetrievalError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="Legal corpus database is unavailable"
        ) from exc


LegalSessionDep = Annotated[Session, Depends(legal_session)]


def _corpus(
    session: Session, index_kind: str, release_version: str | None = None
) -> PublicCorpus:
    return cached_public_corpus(
        session,
        published_release(
            session, index_kind=index_kind, release_version=release_version
        ),
        index_kind=index_kind,
    )


def _reference_corpus(
    session: Session,
    index_kind: str,
    release_version: str | None,
    references: list[SectionReference],
) -> PublicCorpus:
    release = published_release(
        session, index_kind=index_kind, release_version=release_version
    )
    return load_reference_corpus(session, release, references, index_kind=index_kind)


def _response(
    corpus: PublicCorpus,
    data: list[LegalSearchResult],
    *,
    outcome: str = "exact",
    retrieval_mode: str = "exact",
    message: str | None = None,
) -> LegalSearchResponse:
    return LegalSearchResponse.model_validate(
        {
            "data": data,
            "count": len(data),
            "outcome": outcome,
            "retrieval_mode": retrieval_mode,
            "message": message,
            "release_version": corpus.release.version,
            "edition_label": corpus.edition_label,
        }
    )


@router.post("/search", response_model=LegalSearchResponse)
def search_legal(
    body: LegalSearchRequest, session: LegalSessionDep
) -> LegalSearchResponse:
    if settings.RETRIEVAL_INDEX_BACKEND != "pgvector":
        raise HTTPException(
            status_code=503,
            detail="Production legal search is not configured for pgvector",
        )
    reader_query = search_query(body.query)
    response = _search(body, session, reader_query.text)
    response.message_code = message_code(response.message)
    response.query_language = (
        reader_query.language.value if reader_query.language else None
    )
    response.searched_query = reader_query.text if reader_query.translated else None
    return _without_evidence(response)


def _without_evidence(response: LegalSearchResponse) -> LegalSearchResponse:
    """Evidence repeats each result's text for answer generation, not for readers."""
    response.evidence = []
    return response


def _search(
    body: LegalSearchRequest, session: Session, query: str
) -> LegalSearchResponse:
    parsed = (
        parse_section_reference(
            query, default_instrument_slug=body.instrument or CONSTITUTION_SLUG
        )
        if body.mode == "auto"
        else None
    )
    if parsed and (parsed.references or parsed.error):
        corpus = _reference_corpus(
            session,
            body.index_kind,
            body.release_version,
            list(parsed.references),
        )
        if body.instrument and body.instrument not in {
            item.slug for item in corpus.instruments.values()
        }:
            raise HTTPException(
                status_code=404,
                detail="This law isn't included in the selected published edition",
            )
        return exact_lookup(corpus, parsed, query).response
    release = published_release(
        session, index_kind=body.index_kind, release_version=body.release_version
    )
    if body.instrument and body.instrument not in {
        item.slug
        for item in release_instruments(
            session, release.id, index_kind=body.index_kind
        ).values()
    }:
        raise HTTPException(
            status_code=404,
            detail="This law isn't included in the selected published edition",
        )
    if body.release_version:
        build = session.exec(
            select(RetrievalIndexBuild)
            .where(
                RetrievalIndexBuild.release_id == release.id,
                RetrievalIndexBuild.index_kind == body.index_kind,
                col(RetrievalIndexBuild.status).in_(
                    [VectorIndexStatus.READY, VectorIndexStatus.PROMOTED]
                ),
            )
            .order_by(col(RetrievalIndexBuild.created_at).desc())
        ).first()
        if build is None:
            raise PgVectorRetrievalError(
                "This published edition has no ready retrieval index"
            )
        embedding_run_id = build.embedding_run_id
        profile_id = build.profile_id
    else:
        target = active_target(session, index_kind=body.index_kind)
        if target.release_id != release.id:
            raise PgVectorRetrievalError(
                "Active retrieval target changed during search"
            )
        embedding_run_id = target.embedding_run_id
        profile_id = target.profile_id
    profile = session.get(EmbeddingProfile, profile_id)
    if profile is None:
        raise PgVectorRetrievalError(
            "Active target references a missing embedding profile"
        )
    return semantic_lookup(
        session,
        release,
        profile=profile,
        embedding_run_id=embedding_run_id,
        query=query,
        top_k=body.top_k,
        index_kind=body.index_kind,
        embedding_provider=_query_embedding_provider,
        instrument_slug=body.instrument,
    )


@router.get("/releases/current", response_model=LegalReleasePublic)
def read_current_release(
    session: LegalSessionDep, index_kind: IndexKind = "enacted"
) -> LegalReleasePublic:
    corpus = _corpus(session, index_kind)
    target = active_target(session, index_kind=index_kind)
    return LegalReleasePublic(
        release_id=corpus.release.id,
        release_version=corpus.release.version,
        index_kind=index_kind,
        embedding_run_id=target.embedding_run_id,
        retrieval_index_build_id=target.retrieval_index_build_id,
        edition_label=corpus.edition_label,
        legal_statuses=sorted({str(v.legal_status) for v in corpus.versions.values()}),
    )


@router.get("/instruments")
def read_legal_instruments(
    session: LegalSessionDep,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
) -> LegalInstrumentsPublic:
    corpus = _corpus(session, index_kind, release_version)
    data: list[LegalInstrumentPublic] = []
    by_instrument: dict[uuid.UUID, list[Provision]] = {}
    for item in corpus.provisions.values():
        by_instrument.setdefault(item.instrument_id, []).append(item)
    for instrument in sorted(
        corpus.instruments.values(),
        key=lambda item: (item.slug != CONSTITUTION_SLUG, item.slug),
    ):
        provisions = by_instrument.get(instrument.id, [])
        representative = next(
            (item for item in provisions if item.id in corpus.versions), None
        )
        if representative is None:
            continue
        edition = corpus.provision_edition_label(representative)
        data.append(
            LegalInstrumentPublic(
                slug=instrument.slug,
                title=instrument.title,
                short_title=instrument.short_title,
                instrument_type=instrument.instrument_type,
                edition_label=edition,
                edition_note="As enacted, may have been amended."
                if instrument.instrument_type == InstrumentType.ACT
                else "Historical source edition. Later amendments may differ.",
                section_count=sum(
                    item.kind == ProvisionKind.SECTION for item in provisions
                ),
                legal_statuses=sorted(
                    {
                        str(corpus.versions[item.id].legal_status)
                        for item in provisions
                        if item.id in corpus.versions
                    }
                ),
            )
        )
    return LegalInstrumentsPublic(
        data=data, count=len(data), release_version=corpus.release.version
    )


@router.get("/provisions/tree", response_model=ProvisionTreePublic)
def read_provision_tree(
    session: LegalSessionDep,
    parent_path: Annotated[str | None, Query(max_length=512)] = None,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
    all_nodes: bool = False,
    instrument: InstrumentSlug = None,
) -> ProvisionTreePublic:
    if all_nodes and parent_path:
        raise HTTPException(status_code=422, detail="Choose a parent or the full index")
    corpus = _corpus(session, index_kind, release_version)
    slug = instrument or (
        parent_path.partition(".")[0] if parent_path else CONSTITUTION_SLUG
    )
    selected_instrument = next(
        (item for item in corpus.instruments.values() if item.slug == slug), None
    )
    if selected_instrument is None:
        raise HTTPException(
            status_code=404,
            detail="This law isn't included in the selected published edition",
        )
    parent = corpus.provision_at(parent_path) if parent_path else None
    if parent_path and (
        parent is None or parent.instrument_id != selected_instrument.id
    ):
        raise HTTPException(status_code=404, detail="Provision was not found")
    nodes = (
        sorted(
            (
                p
                for p in corpus.provisions.values()
                if p.instrument_id == selected_instrument.id
            ),
            key=lambda p: (p.sort_key, p.canonical_path),
        )
        if all_nodes
        else [
            p
            for p in corpus.children(parent.id if parent else None)
            if p.instrument_id == selected_instrument.id
        ]
    )
    data = [corpus.reference(p) for p in nodes]
    return ProvisionTreePublic(
        data=data,
        count=len(data),
        release_version=corpus.release.version,
        edition_label=corpus.provision_edition_label(nodes[0])
        if nodes
        else corpus.edition_label,
        parent=corpus.reference(parent) if parent else None,
        scope="all" if all_nodes else "children",
        instrument_slug=slug,
    )


@router.get("/provision-history", response_model=LegalSearchResponse)
def read_provision_history(
    canonical_path: Annotated[str, Query(min_length=1, max_length=512)],
    session: LegalSessionDep,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
) -> LegalSearchResponse:
    corpus = _corpus(session, index_kind, release_version)
    current = corpus.provision_at(canonical_path)
    if current is None or current.id not in corpus.versions:
        raise HTTPException(status_code=404, detail="Provision was not found")
    status = col(ProvisionVersion.legal_status)
    published = session.exec(
        select(CorpusRelease, col(ProvisionVersion.id))
        .join(
            CorpusReleaseEntry,
            col(CorpusReleaseEntry.release_id) == col(CorpusRelease.id),
        )
        .join(
            ProvisionVersion,
            col(ProvisionVersion.id) == col(CorpusReleaseEntry.provision_version_id),
        )
        .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
        .where(
            col(CorpusRelease.status).in_(PUBLIC_RELEASE_STATUSES),
            Provision.canonical_path == canonical_path,
            status == LegalStatus.PROPOSED
            if index_kind == "proposals"
            else status != LegalStatus.PROPOSED,
        )
        .order_by(col(CorpusRelease.created_at).desc())
    ).all()
    data: list[LegalSearchResult] = []
    seen: set[uuid.UUID] = set()
    for release, version_id in published:
        if version_id in seen:
            continue
        seen.add(version_id)
        historical = load_ranked_corpus(
            session, release, [version_id], index_kind=index_kind
        )
        data.extend(
            historical.result(p)
            for p in historical.provisions.values()
            if p.canonical_path == canonical_path
            and historical.versions[p.id].id == version_id
        )
    return _response(
        corpus,
        data,
        message="This is the only version of this section available so far."
        if len(data) <= 1
        else None,
    )


@router.get("/provisions/by-citation", response_model=LegalSearchResponse)
def read_provisions_by_citation(
    citation: Annotated[str, Query(min_length=1, max_length=2000)],
    session: LegalSessionDep,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
) -> LegalSearchResponse:
    if not settings.CITATION_LOOKUP_ENABLED:
        raise HTTPException(status_code=503, detail="Citation lookup is disabled")
    parsed = parse_section_reference(citation)
    if not parsed.references and not parsed.error:
        parsed = parse_section_reference(f"Section {citation}")
    if not parsed.references and not parsed.error:
        raise HTTPException(status_code=422, detail="Enter a section reference")
    corpus = _reference_corpus(
        session,
        index_kind,
        release_version,
        list(parsed.references),
    )
    return _without_evidence(exact_lookup(corpus, parsed, citation).response)


@router.get("/sources/{source_document_id}/content", response_model=None)
def read_source_content(
    source_document_id: uuid.UUID,
    session: LegalSessionDep,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
) -> Response:
    corpus = _corpus(session, index_kind, release_version)
    source = corpus.sources.get(source_document_id)
    if source is None:
        raise HTTPException(
            status_code=404, detail="Published source document was not found"
        )
    try:
        store = get_blob_store()
        head = store.head(source.storage_key)
        if isinstance(store, R2BlobStore):
            return RedirectResponse(
                store.create_presigned_get_url(
                    key=source.storage_key, expires_in_seconds=300
                ),
                status_code=307,
            )
    except (BlobStoreError, FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="The original source document is temporarily unavailable",
        ) from exc

    def stream() -> Iterator[bytes]:
        with store.open_read(source.storage_key) as handle:
            while chunk := handle.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=source.mime_type,
        headers={
            "Content-Length": str(head.size_bytes),
            "Content-Disposition": f'inline; filename="source-{source.id}.pdf"',
        },
    )


@router.get("/provisions/{canonical_path:path}", response_model=LegalSearchResponse)
def read_current_provision(
    canonical_path: str,
    session: LegalSessionDep,
    index_kind: IndexKind = "enacted",
    release_version: ReleaseVersion = None,
) -> LegalSearchResponse:
    corpus = _corpus(session, index_kind, release_version)
    provision = corpus.provision_at(canonical_path)
    if provision is None or provision.id not in corpus.versions:
        raise HTTPException(status_code=404, detail="Provision was not found")
    return _response(corpus, [corpus.result(provision, context=True)])


def _query_embedding_provider(profile: EmbeddingProfile) -> DenseEmbeddingProvider:
    return default_embedding_provider(profile)
