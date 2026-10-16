"""Shared exact lookup and canonical evidence assembly for search and chat."""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlmodel import Session

from app.core.config import settings
from app.ingestion.embedding import (
    DenseEmbeddingProvider,
    EmbeddingProviderError,
    HuggingFaceTeiEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.ingestion.pgvector_repository import (
    PgVectorRetrievalError,
    fuse_rankings,
    hybrid_search,
    lexical_search,
    topic_search,
)
from app.legal.enums import EmbeddingProviderKind
from app.legal.models import CorpusRelease, EmbeddingProfile
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import PublicCorpus, load_ranked_corpus
from app.legal.references import ReferenceParse
from app.legal.schemas import (
    CitationOutcome,
    EvidenceItem,
    LegalSearchResponse,
    LegalSearchResult,
)


@dataclass(frozen=True)
class ExactLookup:
    response: LegalSearchResponse

    @property
    def has_resolved_evidence(self) -> bool:
        return any(row.status == "resolved" for row in self.response.citation_outcomes)


def default_embedding_provider(profile: EmbeddingProfile) -> DenseEmbeddingProvider:
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
        endpoint_url=endpoint_url
        if isinstance(endpoint_url, str)
        else settings.HUGGINGFACE_TEI_ENDPOINT_URL,
        api_token=settings.HUGGINGFACE_API_TOKEN,
        model_name=profile.model_name,
        model_revision=profile.model_revision,
    )


def evidence_item(
    corpus: PublicCorpus, result: LegalSearchResult, identifier: str
) -> EvidenceItem:
    version = corpus.versions[result.provision_id]
    served_hash = hashlib.sha256(version.text.encode()).hexdigest()
    if version.text_sha256 not in (served_hash, legal_text_sha256(version.text)):
        raise PgVectorRetrievalError("Published legal text hash does not match")
    return EvidenceItem(
        evidence_id=identifier,
        provision_id=result.provision_id,
        provision_version_id=version.id,
        canonical_path=result.canonical_path,
        citation=result.citation,
        title=result.title,
        authoritative_text=version.text,
        text_sha256=served_hash,
        ancestor_citations=[ancestor.citation for ancestor in result.ancestors],
        legal_status=result.legal_status,
        edition_label=result.edition_label,
        release_id=corpus.release.id,
        release_version=corpus.release.version,
        source_document_id=result.source_document_id,
        source_title=result.source_title,
        source_authority=result.source_authority,
        source_url=result.source_url,
        source_content_url=result.source_content_url,
        source_page_start=result.source_page_start,
        source_page_end=result.source_page_end,
    )


def exact_lookup(
    corpus: PublicCorpus, parsed: ReferenceParse, query: str
) -> ExactLookup:
    outcomes: list[CitationOutcome] = []
    results: list[LegalSearchResult] = []
    evidence: list[EvidenceItem] = []
    identifiers: dict[str, str] = {}
    if parsed.error:
        outcomes.append(
            CitationOutcome(
                reference=query,
                status="unsupported",
                message=parsed.error,
            )
        )
    else:
        for reference in parsed.references:
            matches = sorted(
                (
                    provision
                    for provision in corpus.provisions.values()
                    if provision.id in corpus.versions
                    and provision.canonical_path.endswith(reference.suffix)
                ),
                key=lambda provision: (provision.sort_key, provision.canonical_path),
            )
            refs: list[str] = []
            for provision in matches:
                version = corpus.versions[provision.id]
                key = str(version.id)
                if key not in identifiers:
                    identifier = f"E{len(evidence) + 1}"
                    identifiers[key] = identifier
                    result = corpus.result(provision)
                    results.append(result)
                    evidence.append(evidence_item(corpus, result, identifier))
                refs.append(identifiers[key])
            status = (
                "missing"
                if not matches
                else "ambiguous"
                if len(matches) > 1
                else "resolved"
            )
            outcomes.append(
                CitationOutcome(
                    reference=reference.citation,
                    status=status,
                    evidence_ids=refs,
                    message="This section number appears more than once in this edition. Choose the one you mean."
                    if status == "ambiguous"
                    else "This section isn't in this edition of the Constitution."
                    if status == "missing"
                    else None,
                )
            )
    statuses = {row.status for row in outcomes}
    if statuses == {"resolved"}:
        outcome = "exact"
        message = None
    elif statuses == {"ambiguous"}:
        outcome = "ambiguous"
        message = "This section number appears more than once in this edition. Choose the one you mean."
    elif statuses == {"missing"}:
        outcome = "not_found"
        message = "We couldn't find this section in this edition of the Constitution."
    elif statuses == {"unsupported"}:
        outcome = "unsupported_reference"
        message = parsed.error
    else:
        outcome = "partial"
        message = "We found some of these sections, but not all of them."
    return ExactLookup(
        LegalSearchResponse(
            data=results,
            count=len(results),
            outcome=outcome,
            retrieval_mode="exact",
            message=message,
            release_version=corpus.release.version,
            edition_label=corpus.edition_label,
            citation_outcomes=outcomes,
            evidence=evidence,
        )
    )


def semantic_lookup(
    session: Session,
    release: CorpusRelease,
    *,
    profile: EmbeddingProfile,
    embedding_run_id: uuid.UUID,
    query: str,
    top_k: int,
    index_kind: str,
    embedding_provider: Callable[[EmbeddingProfile], DenseEmbeddingProvider],
) -> LegalSearchResponse:
    """Rank release-scoped segments, then reload all wording from canonical versions."""
    retrieval_mode = "hybrid"
    message = None
    try:
        if not settings.EMBEDDING_QUERY_ENABLED:
            raise EmbeddingProviderError("Paid query embeddings are disabled")
        batch = embedding_provider(profile).embed([query])
        if len(batch.vectors) != 1:
            raise EmbeddingProviderError("Query embedding response is incomplete")
        ranked = hybrid_search(
            session,
            release_id=release.id,
            embedding_run_id=embedding_run_id,
            query_vector=batch.vectors[0],
            query=query,
            top_k=top_k,
            index_kind=index_kind,
        )
    except EmbeddingProviderError, httpx.HTTPError:
        retrieval_mode = "lexical"
        message = "Search is running in a simpler mode right now, so these keyword matches may be less precise."
        ranked = fuse_rankings(
            lexical=lexical_search(
                session,
                release_id=release.id,
                query=query,
                index_kind=index_kind,
            ),
            topics=topic_search(
                session, release_id=release.id, query=query, index_kind=index_kind
            ),
            top_k=top_k,
        )
    corpus = load_ranked_corpus(
        session,
        release,
        [item.segment.provision_version_id for item in ranked],
        index_kind=index_kind,
    )
    seen: set[uuid.UUID] = set()
    data: list[LegalSearchResult] = []
    evidence: list[EvidenceItem] = []
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
        result = corpus.result(
            provision,
            score=item.score,
            dense_rank=item.dense_rank,
            lexical_rank=item.lexical_rank,
        )
        data.append(result)
        evidence.append(evidence_item(corpus, result, f"E{len(evidence) + 1}"))
        if len(data) == top_k:
            break
    return LegalSearchResponse(
        data=data,
        count=len(data),
        outcome="matches" if data else "not_found",
        retrieval_mode=retrieval_mode,
        message=message,
        release_version=corpus.release.version,
        edition_label=corpus.edition_label,
        evidence=evidence,
    )
