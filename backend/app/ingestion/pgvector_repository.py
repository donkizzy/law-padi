"""PostgreSQL + pgvector retrieval primitives.

The repository deliberately keeps retrieval rows separate from canonical legal
rows. Search may rank derived segments, but public results are reloaded from
ProvisionVersion before they leave this boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.retrieval import RetrievalDocument, deterministic_segment_id
from app.languages.normalize import fold
from app.legal.models import (
    ActiveRetrievalTarget,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    Provision,
    ProvisionVersion,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
    SourceDocument,
)
from app.legal.references import CONSTITUTION_SLUG, SectionReference, matches_reference
from app.legal.release_scope import release_instruments
from app.legal.topics import (
    STOPWORDS,
    demoted_sections,
    rights_question,
    section_target,
    topic_sections,
)

_LEXICAL_WORD = re.compile(r"[a-z0-9]+")
_DEMOTION = 0.25
_SECTION_PREFIX = re.compile(r"^(.*?\.section\d+[a-z]?)(?=\.|$)")
# Words present in most of the corpus add noise to keyword ranking.
_LEXICAL_NOISE = frozenset(
    {"constitution", "section", "sections", "provision", "provisions", "nigeria"}
)


class PgVectorRetrievalError(RuntimeError):
    """Raised when retrieval data cannot satisfy a release gate."""


@dataclass(frozen=True)
class RankedSegment:
    segment: RetrievalSegment
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None


@dataclass(frozen=True)
class CanonicalRetrievalResult:
    canonical_path: str
    citation: str
    heading: str | None
    ancestor_headings: list[str]
    authoritative_text: str
    source_document_id: uuid.UUID
    source_page_start: int | None
    source_page_end: int | None
    legal_status: str
    release_version: str
    dense_rank: int | None
    lexical_rank: int | None
    hybrid_score: float


def validate_vector(
    vector: Sequence[float], *, dimensions: int = 1024, reject_zero: bool = True
) -> list[float]:
    values = [float(value) for value in vector]
    if dimensions != 1024:
        raise PgVectorRetrievalError("V1 pgvector embeddings must use 1,024 dimensions")
    if len(values) != dimensions:
        raise PgVectorRetrievalError(
            f"Embedding has {len(values)} dimensions; expected {dimensions}"
        )
    if any(not math.isfinite(value) for value in values):
        raise PgVectorRetrievalError("Embedding contains a non-finite value")
    if reject_zero and not any(value != 0 for value in values):
        raise PgVectorRetrievalError("Cosine retrieval does not accept a zero vector")
    return values


def embedding_sha256(vector: Sequence[float]) -> str:
    return _sha256_json([float(value) for value in vector])


def aggregate_checksum(values: Sequence[str]) -> str:
    return _sha256_json(sorted(values))


def write_segments(
    session: Session,
    *,
    release_id: uuid.UUID,
    documents: Sequence[RetrievalDocument],
    index_kind: str = "enacted",
) -> list[RetrievalSegment]:
    """Idempotently materialize deterministic release-scoped segment rows."""
    if index_kind not in {"enacted", "proposals"}:
        raise PgVectorRetrievalError(f"Unknown index kind: {index_kind}")
    entry_ids = {
        uuid.UUID(str(document.payload["corpus_release_entry_id"]))
        for document in documents
    }
    entries = session.exec(
        select(CorpusReleaseEntry).where(col(CorpusReleaseEntry.id).in_(entry_ids))
    ).all()
    entries_by_version = {entry.provision_version_id: entry for entry in entries}
    provision_ids = {
        uuid.UUID(str(document.payload["provision_id"])) for document in documents
    }
    provisions = {
        provision.id: provision
        for provision in session.exec(
            select(Provision).where(col(Provision.id).in_(provision_ids))
        ).all()
    }
    segments: list[RetrievalSegment] = []
    seen_segment_ids: set[uuid.UUID] = set()
    for document in documents:
        payload = document.payload
        version_id = uuid.UUID(str(payload["provision_version_id"]))
        entry = entries_by_version.get(version_id)
        if entry is None or entry.release_id != release_id:
            raise PgVectorRetrievalError(
                "Retrieval document does not reference an entry in the release"
            )
        provision_id = uuid.UUID(str(payload["provision_id"]))
        provision = provisions.get(provision_id)
        if provision is None or (
            payload.get("instrument_id") is not None
            and str(payload["instrument_id"]) != str(provision.instrument_id)
        ):
            raise PgVectorRetrievalError(
                "Retrieval document instrument does not match its provision"
            )
        source_document_id = uuid.UUID(str(payload["source_document_id"]))
        segment_index_value = int(str(payload["segment_index"]))
        segment_count_value = int(str(payload["segment_count"]))
        retrieval_hash = _sha256(document.retrieval_text)
        segment_id = deterministic_segment_id(
            release_id=release_id,
            provision_version_id=version_id,
            segment_index=segment_index_value,
            retrieval_text_sha256=retrieval_hash,
        )
        if segment_id in seen_segment_ids:
            raise PgVectorRetrievalError(
                f"Retrieval document batch contains duplicate segment {segment_id}"
            )
        seen_segment_ids.add(segment_id)
        existing = session.get(RetrievalSegment, segment_id)
        if existing is not None:
            if (
                existing.retrieval_text_sha256 != retrieval_hash
                or existing.instrument_id != provision.instrument_id
                or existing.release_id != release_id
                or existing.authoritative_text_sha256
                != _sha256(document.authoritative_text)
            ):
                raise PgVectorRetrievalError(
                    f"Deterministic segment {segment_id} conflicts with existing data"
                )
            segments.append(existing)
            continue
        raw_ancestors = payload.get("ancestor_headings", [])
        if not isinstance(raw_ancestors, list):
            raise PgVectorRetrievalError(
                "Retrieval document ancestor headings were invalid"
            )
        ancestors = [str(value) for value in raw_ancestors]
        segment = RetrievalSegment(
            id=segment_id,
            release_id=release_id,
            release_entry_id=entry.id,
            provision_id=provision_id,
            instrument_id=provision.instrument_id,
            provision_version_id=version_id,
            source_document_id=source_document_id,
            index_kind=index_kind,
            segment_index=segment_index_value,
            segment_count=segment_count_value,
            language="en",
            citation=document.citation,
            canonical_path=str(payload["canonical_path"]),
            ancestor_headings=ancestors,
            ancestor_text="\n".join(ancestors),
            heading=document.heading,
            retrieval_text=document.retrieval_text,
            retrieval_text_sha256=retrieval_hash,
            authoritative_text_sha256=_sha256(document.authoritative_text),
            lexical_profile_version=settings.RETRIEVAL_LEXICAL_PROFILE_VERSION,
        )
        session.add(segment)
        segments.append(segment)
    session.flush()
    return segments


def write_embeddings(
    session: Session,
    *,
    release_id: uuid.UUID,
    embedding_run: EmbeddingRun,
    profile: EmbeddingProfile,
    segments: Sequence[RetrievalSegment],
    vectors: Sequence[Sequence[float]],
) -> list[RetrievalEmbedding]:
    if profile.vector_dimensions != 1024:
        raise PgVectorRetrievalError(
            f"Embedding profile {profile.name} must be configured for 1,024 dimensions"
        )
    if len(segments) != len(vectors):
        raise PgVectorRetrievalError("Segment and embedding counts do not match")
    rows: list[RetrievalEmbedding] = []
    for segment, vector in zip(segments, vectors, strict=True):
        values = validate_vector(vector, dimensions=profile.vector_dimensions)
        checksum = embedding_sha256(values)
        existing = session.exec(
            select(RetrievalEmbedding).where(
                RetrievalEmbedding.embedding_run_id == embedding_run.id,
                RetrievalEmbedding.segment_id == segment.id,
            )
        ).first()
        if existing is not None:
            if existing.embedding_sha256 != checksum:
                raise PgVectorRetrievalError(
                    f"Embedding retry changed vector for segment {segment.id}"
                )
            rows.append(existing)
            continue
        row = RetrievalEmbedding(
            id=uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{embedding_run.id}:{segment.id}:{checksum}",
            ),
            segment_id=segment.id,
            release_id=release_id,
            embedding_run_id=embedding_run.id,
            profile_id=profile.id,
            vector_dimensions=profile.vector_dimensions,
            embedding=values,
            embedding_sha256=checksum,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def lexical_tsquery(query: str) -> str | None:
    """OR together a question's content words, with prefixes for plurals.

    websearch_to_tsquery requires every word, so a natural question such as
    "can police search my phone" matched nothing. Ranking by cover density
    still favours segments that contain more of the words.
    """
    words: list[str] = []
    # Folding keeps "haƙƙi" one word instead of the fragments "ha" and "i".
    for word in _LEXICAL_WORD.findall(fold(query).lower()):
        if (
            len(word) < 2
            or word in STOPWORDS
            or word in _LEXICAL_NOISE
            or word in words
        ):
            continue
        words.append(word)
    if not words:
        return None
    return " | ".join(f"{word}:*" if len(word) >= 4 else word for word in words[:24])


def lexical_search(
    session: Session,
    *,
    release_id: uuid.UUID,
    query: str,
    limit: int | None = None,
    index_kind: str = "enacted",
    instrument_slug: str | None = None,
) -> list[tuple[RetrievalSegment, float]]:
    candidate_limit = limit or settings.RETRIEVAL_LEXICAL_CANDIDATE_LIMIT
    expression = lexical_tsquery(query)
    if expression is None:
        return []
    ts_query = func.to_tsquery("simple", expression)
    rank = func.ts_rank_cd(RetrievalSegment.search_vector, ts_query).label("rank")
    statement = (
        select(RetrievalSegment, rank)
        .where(
            RetrievalSegment.release_id == release_id,
            RetrievalSegment.index_kind == index_kind,
            RetrievalSegment.search_vector.op("@@")(ts_query),
        )
        .order_by(rank.desc(), col(RetrievalSegment.id))
        .limit(candidate_limit)
    )
    if instrument_slug:
        statement = statement.where(
            col(RetrievalSegment.canonical_path).startswith(
                f"{instrument_slug}.", autoescape=True
            )
        )
    return [(segment, float(score)) for segment, score in session.exec(statement).all()]


def topic_search(
    session: Session,
    *,
    release_id: uuid.UUID,
    query: str,
    index_kind: str = "enacted",
    instrument_slug: str | None = None,
) -> list[tuple[RetrievalSegment, float]]:
    """Whole-provision segments for curated plain-language topics, in topic order."""
    slugs = {
        instrument.slug
        for instrument in release_instruments(
            session, release_id, index_kind=index_kind
        ).values()
    }
    if instrument_slug:
        slugs &= {instrument_slug}
    targets = topic_sections(query, instrument_slugs=slugs)
    if not targets:
        return []
    rows = session.exec(
        select(RetrievalSegment).where(
            RetrievalSegment.release_id == release_id,
            RetrievalSegment.index_kind == index_kind,
            RetrievalSegment.segment_index == 1,
            or_(
                *(
                    matches_reference(
                        col(RetrievalSegment.canonical_path),
                        SectionReference(
                            entry.partition(":")[2],
                            instrument_slug=entry.partition(":")[0],
                        ),
                    )
                    if entry.partition(":")[2][0].isdigit()
                    else (
                        col(RetrievalSegment.canonical_path).startswith(
                            f"{entry.partition(':')[0]}.", autoescape=True
                        )
                        & col(RetrievalSegment.canonical_path).endswith(
                            f".{entry.partition(':')[2]}", autoescape=True
                        )
                    )
                    for entry, _weight in targets
                )
            ),
        )
    ).all()
    ordered: list[tuple[RetrievalSegment, float]] = []
    for entry, weight in targets:
        for segment in sorted(rows, key=lambda row: row.canonical_path):
            if (
                matches_reference(
                    segment.canonical_path,
                    SectionReference(
                        entry.partition(":")[2], instrument_slug=entry.partition(":")[0]
                    ),
                )
                if entry.partition(":")[2][0].isdigit()
                else (
                    segment.canonical_path.startswith(f"{entry.partition(':')[0]}.")
                    and segment.canonical_path.endswith(f".{entry.partition(':')[2]}")
                )
            ):
                ordered.append((segment, weight))
    return ordered


def dense_search(
    session: Session,
    *,
    release_id: uuid.UUID,
    embedding_run_id: uuid.UUID,
    query_vector: Sequence[float],
    limit: int | None = None,
    index_kind: str = "enacted",
    instrument_slug: str | None = None,
) -> list[tuple[RetrievalSegment, float]]:
    vector = validate_vector(query_vector)
    candidate_limit = limit or settings.RETRIEVAL_DENSE_CANDIDATE_LIMIT
    distance = (
        cast(Any, RetrievalEmbedding.embedding)
        .cosine_distance(vector)
        .label("distance")
    )
    statement = (
        select(RetrievalSegment, distance)
        .join(
            RetrievalEmbedding,
            col(RetrievalEmbedding.segment_id) == col(RetrievalSegment.id),
        )
        .where(
            RetrievalEmbedding.release_id == release_id,
            RetrievalSegment.index_kind == index_kind,
            RetrievalEmbedding.embedding_run_id == embedding_run_id,
        )
        .order_by(distance, col(RetrievalSegment.id))
        .limit(candidate_limit)
    )
    if instrument_slug:
        statement = statement.where(
            col(RetrievalSegment.canonical_path).startswith(
                f"{instrument_slug}.", autoescape=True
            )
        )
    return [(segment, float(score)) for segment, score in session.exec(statement).all()]


def section_key(canonical_path: str) -> str:
    """The section a provision belongs to, or the provision itself outside sections."""
    match = _SECTION_PREFIX.match(canonical_path)
    return match.group(1) if match else canonical_path


def fuse_rankings(
    *,
    dense: Sequence[tuple[RetrievalSegment, float]] = (),
    lexical: Sequence[tuple[RetrievalSegment, float]] = (),
    topics: Sequence[tuple[RetrievalSegment, float]] = (),
    top_k: int,
    rrf_k: int | None = None,
    lexical_weight: float = 1.0,
    demoted: Collection[str] = (),
    prefer_constitution: bool = False,
    balance_instruments: bool = False,
) -> list[RankedSegment]:
    """Weighted reciprocal-rank fusion; topic matches add a flat boost.

    Demoted sections keep a fraction of their score, so they still appear
    when nothing better matches.
    """
    constant = rrf_k or settings.RETRIEVAL_RRF_K
    merged: dict[uuid.UUID, dict[str, Any]] = {}
    for rank, (segment, _distance) in enumerate(dense, start=1):
        merged.setdefault(segment.id, {"segment": segment, "score": 0.0})
        merged[segment.id]["score"] += 1.0 / (constant + rank)
        merged[segment.id]["dense_rank"] = rank
    for rank, (segment, _lexical_score) in enumerate(lexical, start=1):
        merged.setdefault(segment.id, {"segment": segment, "score": 0.0})
        merged[segment.id]["score"] += lexical_weight / (constant + rank)
        merged[segment.id]["lexical_rank"] = rank
    # With dense ranking, a topic names candidate sections, not an order
    # among them: each gets its boost at first rank on every row of the
    # section, because dense search often matches a subsection rather than
    # the whole-section row, and dense ranking breaks the tie. Without it,
    # keyword hits on any row of a long section would decide, so the boost
    # stays on the topic's own row in the curated order.
    boosts: dict[str, float] = {}
    for rank, (segment, weight) in enumerate(topics, start=1):
        merged.setdefault(segment.id, {"segment": segment, "score": 0.0})
        if dense:
            key = section_key(segment.canonical_path)
            boosts[key] = boosts.get(key, 0.0) + weight / (constant + 1)
        else:
            merged[segment.id]["score"] += weight / (constant + rank)
    ranked = [
        RankedSegment(
            segment=item["segment"],
            score=(
                float(item["score"])
                + boosts.get(section_key(item["segment"].canonical_path), 0.0)
            )
            * (
                _DEMOTION
                if section_target(item["segment"].canonical_path) in demoted
                else 1.0
            ),
            dense_rank=item.get("dense_rank"),
            lexical_rank=item.get("lexical_rank"),
        )
        for item in merged.values()
    ]
    ranked.sort(key=lambda item: (-item.score, str(item.segment.id)))
    # A section, its subsections and its paragraphs are all indexed. Keep the
    # best-scoring row per section so the public limit returns distinct
    # sections, rather than one section filling every slot.
    seen: set[str] = set()
    unique: list[RankedSegment] = []
    for item in ranked:
        key = section_key(item.segment.canonical_path)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    # A diversity quota must not truncate a single-law pool or reduce the
    # Constitution's established results merely because Acts are published.
    slugs = {item.segment.canonical_path.partition(".")[0] for item in unique}
    if len(slugs) <= 1 or not balance_instruments:
        return unique[:top_k]
    if (
        prefer_constitution
        and unique[0].segment.canonical_path.partition(".")[0] != CONSTITUTION_SLUG
    ):
        # Promote only a Constitution candidate already inside the requested
        # result window with a real topic/title hint for this question.
        # Being numbered 33–46 does not by itself establish relevance.
        topic_keys = {
            section_key(segment.canonical_path)
            for segment, weight in topics
            if weight >= 1.5
        }
        first = next(
            (
                item
                for item in unique[:top_k]
                if item.segment.canonical_path.startswith(f"{CONSTITUTION_SLUG}.")
                and section_key(item.segment.canonical_path) in topic_keys
            ),
            None,
        )
        if first:
            unique.remove(first)
            unique.insert(0, first)
    counts: dict[str, int] = {}
    balanced: list[RankedSegment] = []
    deferred: list[RankedSegment] = []
    for item in unique:
        slug = item.segment.canonical_path.partition(".")[0]
        if slug != CONSTITUTION_SLUG and counts.get(slug, 0) >= 3:
            deferred.append(item)
            continue
        balanced.append(item)
        counts[slug] = counts.get(slug, 0) + 1
        if len(balanced) == top_k:
            return balanced
    # Diversity is a preference, not a reason to return fewer available
    # results. Do not invent other-law evidence to satisfy the quota.
    return (balanced + deferred)[:top_k]


def hybrid_search(
    session: Session,
    *,
    release_id: uuid.UUID,
    embedding_run_id: uuid.UUID,
    query_vector: Sequence[float],
    query: str,
    top_k: int,
    index_kind: str = "enacted",
    rrf_k: int | None = None,
    instrument_slug: str | None = None,
) -> list[RankedSegment]:
    dense = dense_search(
        session,
        release_id=release_id,
        embedding_run_id=embedding_run_id,
        query_vector=query_vector,
        index_kind=index_kind,
        instrument_slug=instrument_slug,
    )
    lexical = lexical_search(
        session,
        release_id=release_id,
        query=query,
        index_kind=index_kind,
        instrument_slug=instrument_slug,
    )
    topics = topic_search(
        session,
        release_id=release_id,
        query=query,
        index_kind=index_kind,
        instrument_slug=instrument_slug,
    )
    return fuse_rankings(
        dense=dense,
        lexical=lexical,
        topics=topics,
        top_k=top_k,
        rrf_k=rrf_k,
        lexical_weight=settings.RETRIEVAL_LEXICAL_WEIGHT,
        demoted=demoted_sections(query),
        prefer_constitution=rights_question(query),
        balance_instruments=not instrument_slug
        and len(release_instruments(session, release_id, index_kind=index_kind)) > 1,
    )


def canonical_results(
    session: Session, ranked: Sequence[RankedSegment], *, release_version: str
) -> list[CanonicalRetrievalResult]:
    """Reload authoritative text and provenance for ranked derived segments."""
    results: list[CanonicalRetrievalResult] = []
    for item in ranked:
        segment = item.segment
        version = session.get(ProvisionVersion, segment.provision_version_id)
        provision = session.get(Provision, segment.provision_id)
        source = session.get(SourceDocument, segment.source_document_id)
        if not version or not provision or not source:
            raise PgVectorRetrievalError(
                f"Segment {segment.id} does not join to canonical legal provenance"
            )
        results.append(
            CanonicalRetrievalResult(
                canonical_path=provision.canonical_path,
                citation=segment.citation,
                heading=provision.heading,
                ancestor_headings=list(segment.ancestor_headings),
                authoritative_text=version.text,
                source_document_id=source.id,
                source_page_start=version.source_page_start,
                source_page_end=version.source_page_end,
                legal_status=str(version.legal_status),
                release_version=release_version,
                dense_rank=item.dense_rank,
                lexical_rank=item.lexical_rank,
                hybrid_score=item.score,
            )
        )
    return results


def active_target(
    session: Session, *, index_kind: str = "enacted"
) -> ActiveRetrievalTarget:
    target = session.get(ActiveRetrievalTarget, index_kind)
    if target is None:
        raise PgVectorRetrievalError(
            f"No active pgvector retrieval target for {index_kind}"
        )
    return target


def validate_index_build(
    session: Session,
    *,
    build: RetrievalIndexBuild,
    expected_segment_count: int,
) -> dict[str, Any]:
    segments = session.exec(
        select(RetrievalSegment).where(
            RetrievalSegment.release_id == build.release_id,
            RetrievalSegment.index_kind == build.index_kind,
        )
    ).all()
    embeddings = session.exec(
        select(RetrievalEmbedding).where(
            RetrievalEmbedding.release_id == build.release_id,
            RetrievalEmbedding.embedding_run_id == build.embedding_run_id,
        )
    ).all()
    errors: list[str] = []
    segment_ids = {segment.id for segment in segments}
    embedding_segment_ids = {embedding.segment_id for embedding in embeddings}
    if len(segments) != expected_segment_count:
        errors.append("segment_count_mismatch")
    if len(embeddings) != len(segments):
        errors.append("embedding_count_mismatch")
    if embedding_segment_ids != segment_ids:
        errors.append("embedding_segment_set_mismatch")
    if build.vector_dimensions != settings.RETRIEVAL_VECTOR_DIMENSIONS:
        errors.append("build_vector_dimensions_mismatch")
    for embedding in embeddings:
        try:
            validate_vector(
                embedding.embedding,
                dimensions=settings.RETRIEVAL_VECTOR_DIMENSIONS,
            )
        except PgVectorRetrievalError as exc:
            errors.append(f"embedding:{embedding.id}:{exc}")
    for segment in segments:
        entry = session.get(CorpusReleaseEntry, segment.release_entry_id)
        version = session.get(ProvisionVersion, segment.provision_version_id)
        provision = session.get(Provision, segment.provision_id)
        source = session.get(SourceDocument, segment.source_document_id)
        if not entry or entry.release_id != build.release_id:
            errors.append(f"segment:{segment.id}:release_entry_missing")
        if not version or not provision or not source:
            errors.append(f"segment:{segment.id}:canonical_join_missing")
        elif segment.instrument_id != provision.instrument_id:
            errors.append(f"segment:{segment.id}:instrument_mismatch")
    lexical_smoke_result_count = 0
    if segments:
        lexical_smoke_result_count = len(
            lexical_search(
                session,
                release_id=build.release_id,
                # A citation such as "Section 9" contains only a stopword and
                # a one-digit token. Include indexed wording for the smoke test.
                query=f"{segments[0].citation} {segments[0].retrieval_text}",
                index_kind=build.index_kind,
                limit=1,
            )
        )
        if lexical_smoke_result_count == 0:
            errors.append("lexical_smoke_query_empty")
    report: dict[str, Any] = {
        "is_valid": not errors,
        "errors": errors,
        "expected_segment_count": expected_segment_count,
        "stored_segment_count": len(segments),
        "stored_embedding_count": len(embeddings),
        "vector_dimensions": build.vector_dimensions,
        "segment_checksum": aggregate_checksum(
            [segment.retrieval_text_sha256 for segment in segments]
        ),
        "embedding_checksum": aggregate_checksum(
            [embedding.embedding_sha256 for embedding in embeddings]
        ),
        "lexical_smoke_query_supported": lexical_smoke_result_count > 0,
        "lexical_smoke_result_count": lexical_smoke_result_count,
    }
    return report


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")))
