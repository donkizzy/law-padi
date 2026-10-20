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
from app.legal.instruments import CONSTITUTION_SLUG, instrument_label
from app.legal.models import CorpusRelease, EmbeddingProfile
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import PublicCorpus, load_ranked_corpus
from app.legal.references import (
    REFERENCE_FORMAT_MESSAGE,
    UNKNOWN_LAW_MESSAGE,
    ReferenceParse,
    SectionReference,
    matches_reference,
)
from app.legal.release_scope import release_instruments
from app.legal.schemas import (
    CitationOutcome,
    EvidenceItem,
    LegalSearchResponse,
    LegalSearchResult,
)
from app.legal.topics import demoted_sections, rights_question

AMBIGUOUS_MESSAGE = "This section number appears more than once in this edition. Choose the one you mean."
NOT_IN_CONSTITUTION_MESSAGE = (
    "We couldn't find this section in this edition of the Constitution."
)
PARTIAL_MESSAGE = "We found some of these sections, but not all of them."
SIMPLER_SEARCH_MESSAGE = "Search is running in a simpler mode right now, so these keyword matches may be less precise."
# Stable keys for the fixed messages, so clients can show them in any language.
_MESSAGE_CODES = {
    AMBIGUOUS_MESSAGE: "ambiguous_section",
    NOT_IN_CONSTITUTION_MESSAGE: "section_not_found",
    PARTIAL_MESSAGE: "partial_sections",
    SIMPLER_SEARCH_MESSAGE: "simpler_search",
    REFERENCE_FORMAT_MESSAGE: "reference_format",
    UNKNOWN_LAW_MESSAGE: "unknown_law",
}


def message_code(message: str | None) -> str | None:
    return _MESSAGE_CODES.get(message) if message else None


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
        instrument_slug=result.instrument_slug,
        instrument_title=result.instrument_title,
        instrument_short_title=result.instrument_short_title,
        instrument_type=result.instrument_type,
        short_citation=result.short_citation,
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


def _missing_reference_message(
    corpus: PublicCorpus, reference: SectionReference
) -> str:
    if reference.instrument_slug not in {
        instrument.slug for instrument in corpus.instruments.values()
    }:
        return f"{instrument_label(reference.instrument_slug)} isn't included in this published edition."
    label = (
        "the Constitution"
        if reference.instrument_slug == CONSTITUTION_SLUG
        else instrument_label(reference.instrument_slug)
    )
    return f"This section isn't in this edition of {label}."


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
                    and matches_reference(provision.canonical_path, reference)
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
                    message=AMBIGUOUS_MESSAGE
                    if status == "ambiguous"
                    else _missing_reference_message(corpus, reference)
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
        message = AMBIGUOUS_MESSAGE
    elif statuses == {"missing"}:
        outcome = "not_found"
        message = (
            NOT_IN_CONSTITUTION_MESSAGE
            if all(
                ref.instrument_slug == CONSTITUTION_SLUG for ref in parsed.references
            )
            else " ".join(dict.fromkeys(row.message for row in outcomes if row.message))
        )
    elif statuses == {"unsupported"}:
        outcome = "unsupported_reference"
        message = parsed.error
    else:
        outcome = "partial"
        message = PARTIAL_MESSAGE
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
    instrument_slug: str | None = None,
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
            instrument_slug=instrument_slug,
        )
    except EmbeddingProviderError, httpx.HTTPError:
        retrieval_mode = "lexical"
        message = SIMPLER_SEARCH_MESSAGE
        ranked = fuse_rankings(
            lexical=lexical_search(
                session,
                release_id=release.id,
                query=query,
                index_kind=index_kind,
                instrument_slug=instrument_slug,
            ),
            topics=topic_search(
                session,
                release_id=release.id,
                query=query,
                index_kind=index_kind,
                instrument_slug=instrument_slug,
            ),
            top_k=top_k,
            lexical_weight=settings.RETRIEVAL_LEXICAL_WEIGHT,
            demoted=demoted_sections(query),
            prefer_constitution=rights_question(query),
            balance_instruments=not instrument_slug
            and len(release_instruments(session, release.id, index_kind=index_kind))
            > 1,
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
