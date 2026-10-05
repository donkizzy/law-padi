import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.ingestion.embedding import (
    DenseEmbeddingProvider,
    HuggingFaceTeiEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.ingestion.pgvector_repository import (
    CanonicalRetrievalResult,
    PgVectorRetrievalError,
    RankedSegment,
    active_target,
    canonical_results,
    hybrid_search,
    lexical_search,
)
from app.legal.enums import EmbeddingProviderKind
from app.legal.models import (
    CorpusRelease,
    EmbeddingProfile,
    RetrievalSegment,
)
from app.legal.schemas import (
    LegalSearchRequest,
    LegalSearchResponse,
    LegalSearchResult,
)

router = APIRouter(prefix="/legal", tags=["legal"])
_EXACT_CITATION_RE = re.compile(
    r"^(?:section|s\.?|chapter|part)\s+[0-9a-z().-]+$", re.I
)


@router.post("/search", response_model=LegalSearchResponse)
def search_legal(
    body: LegalSearchRequest,
    session: SessionDep,
) -> LegalSearchResponse:
    if settings.RETRIEVAL_INDEX_BACKEND != "pgvector":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Production legal search is not configured for pgvector",
        )
    try:
        target = active_target(session, index_kind=body.index_kind)
        release = session.get(CorpusRelease, target.release_id)
        if release is None:
            raise PgVectorRetrievalError("Active target references a missing release")

        # Exact citation requests must remain available when an embedding
        # provider is down; lexical search is enough for this path.
        if _EXACT_CITATION_RE.match(body.query.strip()):
            lexical = lexical_search(
                session,
                release_id=target.release_id,
                query=body.query,
                limit=body.top_k,
                index_kind=body.index_kind,
            )
            ranked = [
                _ranked_from_lexical(segment, rank)
                for rank, (segment, _score) in enumerate(lexical, start=1)
            ]
        else:
            profile = session.get(EmbeddingProfile, target.profile_id)
            if profile is None:
                raise PgVectorRetrievalError(
                    "Active target references a missing profile"
                )
            provider = _query_embedding_provider(profile)
            batch = provider.embed([body.query])
            ranked = hybrid_search(
                session,
                release_id=target.release_id,
                embedding_run_id=target.embedding_run_id,
                query_vector=batch.vectors[0],
                query=body.query,
                top_k=body.top_k,
                index_kind=body.index_kind,
            )
        results = canonical_results(session, ranked, release_version=release.version)
        return LegalSearchResponse(
            data=[_public_result(result) for result in results], count=len(results)
        )
    except PgVectorRetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/provisions/{canonical_path:path}", response_model=LegalSearchResponse)
def read_current_provision(
    canonical_path: str,
    session: SessionDep,
    index_kind: Annotated[str, Query(pattern="^(enacted|proposals)$")] = "enacted",
) -> LegalSearchResponse:
    try:
        target = active_target(session, index_kind=index_kind)
        release = session.get(CorpusRelease, target.release_id)
        if release is None:
            raise PgVectorRetrievalError("Active target references a missing release")
        segments = session.exec(
            select(RetrievalSegment)
            .where(
                RetrievalSegment.release_id == target.release_id,
                RetrievalSegment.index_kind == index_kind,
                RetrievalSegment.canonical_path == canonical_path,
            )
            .order_by(col(RetrievalSegment.segment_index))
        ).all()
        if not segments:
            raise HTTPException(status_code=404, detail="Provision was not found")
        from app.ingestion.pgvector_repository import RankedSegment

        ranked = [
            RankedSegment(segment=segment, score=1.0, lexical_rank=index)
            for index, segment in enumerate(segments, start=1)
        ]
        results = canonical_results(session, ranked, release_version=release.version)
        return LegalSearchResponse(
            data=[_public_result(result) for result in results], count=len(results)
        )
    except PgVectorRetrievalError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/releases/current")
def read_current_release(
    session: SessionDep,
    index_kind: Annotated[str, Query(pattern="^(enacted|proposals)$")] = "enacted",
) -> dict[str, object]:
    try:
        target = active_target(session, index_kind=index_kind)
    except PgVectorRetrievalError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    release = session.get(CorpusRelease, target.release_id)
    if release is None:
        raise HTTPException(status_code=503, detail="Active release is missing")
    return {
        "release_id": str(release.id),
        "release_version": release.version,
        "index_kind": index_kind,
        "embedding_run_id": str(target.embedding_run_id),
        "retrieval_index_build_id": str(target.retrieval_index_build_id),
    }


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


def _ranked_from_lexical(segment: RetrievalSegment, rank: int) -> RankedSegment:
    return RankedSegment(
        segment=segment,
        score=1.0 / (settings.RETRIEVAL_RRF_K + rank),
        lexical_rank=rank,
    )


def _public_result(result: CanonicalRetrievalResult) -> LegalSearchResult:
    return LegalSearchResult(
        canonical_path=result.canonical_path,
        citation=result.citation,
        heading=result.heading,
        ancestor_headings=result.ancestor_headings,
        authoritative_text=result.authoritative_text,
        source_document_id=result.source_document_id,
        source_page_start=result.source_page_start,
        source_page_end=result.source_page_end,
        legal_status=result.legal_status,
        release_version=result.release_version,
        dense_rank=result.dense_rank,
        lexical_rank=result.lexical_rank,
        hybrid_score=result.hybrid_score,
    )
