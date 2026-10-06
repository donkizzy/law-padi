import uuid
from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.ingestion.blob_store import BlobStoreError
from app.ingestion.embedding import (
    DenseEmbeddingProvider,
    EmbeddingProviderError,
    HuggingFaceTeiEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
    RankedSegment,
    active_target,
    hybrid_search,
    lexical_search,
)
from app.ingestion.r2_blob_store import R2BlobStore
from app.ingestion.service import get_blob_store
from app.legal.enums import EmbeddingProviderKind
from app.legal.models import CorpusRelease, EmbeddingProfile
from app.legal.public_corpus import (
    PUBLIC_RELEASE_STATUSES,
    PublicCorpus,
    load_public_corpus,
    published_release,
)
from app.legal.references import parse_section_reference
from app.legal.schemas import (
    LegalReleasePublic,
    LegalSearchRequest,
    LegalSearchResponse,
    LegalSearchResult,
    ProvisionTreePublic,
)

router = APIRouter(prefix="/legal", tags=["legal"])
IndexKind = Annotated[str, Query(pattern="^(enacted|proposals)$")]
ReleaseVersion = Annotated[str | None, Query(min_length=1, max_length=128)]


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
    return load_public_corpus(
        session,
        published_release(
            session, index_kind=index_kind, release_version=release_version
        ),
        index_kind=index_kind,
    )


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
    corpus = _corpus(session, body.index_kind)
    parsed = parse_section_reference(body.query) if body.mode == "auto" else None
    if parsed and parsed.error:
        return _response(
            corpus, [], outcome="unsupported_reference", message=parsed.error
        )
    if parsed and parsed.reference:
        matches = sorted(
            (
                p
                for p in corpus.provisions.values()
                if p.id in corpus.versions
                and p.canonical_path.endswith(parsed.reference.suffix)
            ),
            key=lambda p: (p.sort_key, p.canonical_path),
        )
        data = [corpus.result(p) for p in matches]
        return _response(
            corpus,
            data,
            outcome="exact" if len(data) == 1 else "ambiguous" if data else "not_found",
            message="This reference has multiple identities in the source edition. Choose by chapter, part, and page."
            if len(data) > 1
            else "This reference is not present in the published source edition."
            if not data
            else None,
        )
    target = active_target(session, index_kind=body.index_kind)
    profile = session.get(EmbeddingProfile, target.profile_id)
    if profile is None:
        raise PgVectorRetrievalError(
            "Active target references a missing embedding profile"
        )
    retrieval_mode = "hybrid"
    message = None
    try:
        batch = _query_embedding_provider(profile).embed([body.query])
        if len(batch.vectors) != 1:
            raise EmbeddingProviderError("Query embedding response is incomplete")
        ranked = hybrid_search(
            session,
            release_id=target.release_id,
            embedding_run_id=target.embedding_run_id,
            query_vector=batch.vectors[0],
            query=body.query,
            top_k=body.top_k,
            index_kind=body.index_kind,
        )
    except EmbeddingProviderError, httpx.HTTPError:
        retrieval_mode = "lexical"
        message = "Semantic search is temporarily unavailable. Showing keyword matches."
        lexical = lexical_search(
            session,
            release_id=target.release_id,
            query=body.query,
            index_kind=body.index_kind,
        )
        ranked = [
            RankedSegment(segment=segment, score=score, lexical_rank=rank)
            for rank, (segment, score) in enumerate(lexical, start=1)
        ]
    seen: set[uuid.UUID] = set()
    data = []
    for item in ranked:
        if item.segment.provision_version_id in seen:
            continue
        seen.add(item.segment.provision_version_id)
        provision = corpus.provisions.get(item.segment.provision_id)
        if (
            provision is None
            or provision.id not in corpus.versions
            or corpus.versions[provision.id].id != item.segment.provision_version_id
        ):
            raise PgVectorRetrievalError(
                "Search result does not belong to the published corpus"
            )
        data.append(
            corpus.result(
                provision,
                score=item.score,
                dense_rank=item.dense_rank,
                lexical_rank=item.lexical_rank,
            )
        )
        if len(data) == body.top_k:
            break
    return _response(
        corpus,
        data,
        outcome="matches" if data else "not_found",
        retrieval_mode=retrieval_mode,
        message=message,
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


@router.get("/provisions/tree", response_model=ProvisionTreePublic)
def read_provision_tree(
    session: LegalSessionDep,
    parent_path: Annotated[str | None, Query(max_length=512)] = None,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
) -> ProvisionTreePublic:
    corpus = _corpus(session, index_kind, release_version)
    parent = (
        next(
            (p for p in corpus.provisions.values() if p.canonical_path == parent_path),
            None,
        )
        if parent_path
        else None
    )
    if parent_path and not parent:
        raise HTTPException(status_code=404, detail="Provision was not found")
    data = [corpus.reference(p) for p in corpus.children(parent.id if parent else None)]
    return ProvisionTreePublic(
        data=data,
        count=len(data),
        release_version=corpus.release.version,
        edition_label=corpus.edition_label,
    )


@router.get("/provision-history", response_model=LegalSearchResponse)
def read_provision_history(
    canonical_path: Annotated[str, Query(min_length=1, max_length=512)],
    session: LegalSessionDep,
    release_version: ReleaseVersion = None,
    index_kind: IndexKind = "enacted",
) -> LegalSearchResponse:
    corpus = _corpus(session, index_kind, release_version)
    if not any(
        p.canonical_path == canonical_path and p.id in corpus.versions
        for p in corpus.provisions.values()
    ):
        raise HTTPException(status_code=404, detail="Provision was not found")
    releases = session.exec(
        select(CorpusRelease)
        .where(col(CorpusRelease.status).in_(PUBLIC_RELEASE_STATUSES))
        .order_by(col(CorpusRelease.created_at).desc())
    ).all()
    data: list[LegalSearchResult] = []
    seen: set[uuid.UUID] = set()
    for release in releases:
        historical = load_public_corpus(session, release, index_kind=index_kind)
        for p in historical.provisions.values():
            if p.canonical_path == canonical_path and p.id in historical.versions:
                result = historical.result(p)
                if result.provision_version_id not in seen:
                    data.append(result)
                    seen.add(result.provision_version_id)
    return _response(
        corpus,
        data,
        message="No additional published versions are stored."
        if len(data) <= 1
        else None,
    )


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
    provision = next(
        (
            p
            for p in corpus.provisions.values()
            if p.canonical_path == canonical_path and p.id in corpus.versions
        ),
        None,
    )
    if provision is None:
        raise HTTPException(status_code=404, detail="Provision was not found")
    return _response(corpus, [corpus.result(provision, context=True)])


def _query_embedding_provider(profile: EmbeddingProfile) -> DenseEmbeddingProvider:
    if profile.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        raise PgVectorRetrievalError(
            "Active embedding profile has the wrong dimensions"
        )
    if profile.provider == EmbeddingProviderKind.OPENAI:
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model_name=profile.model_name,
            model_revision=profile.model_revision,
        )
    endpoint_url = profile.configuration.get("endpoint_url")
    return HuggingFaceTeiEmbeddingProvider(
        endpoint_url=(
            endpoint_url
            if isinstance(endpoint_url, str)
            else settings.HUGGINGFACE_TEI_ENDPOINT_URL
        ),
        api_token=settings.HUGGINGFACE_API_TOKEN,
        model_name=profile.model_name,
        model_revision=profile.model_revision,
    )
