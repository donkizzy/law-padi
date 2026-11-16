"""Measure section-level search accuracy against the active retrieval target.

Each case names the sections a non-lawyer expects first. The command scores
every ranking signal on its own and the production fusion, so a change to one
signal (for example the topic guide) cannot hide a regression in another.

    uv run python scripts/retrieval_benchmark.py \
        ../eval/datasets/plain-language-retrieval-benchmark-v1.json \
        ../eval/datasets/plain-language-retrieval-heldout-v1.json

Query embeddings use the configured provider, so the command needs the same
credentials as live search.
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.ingestion.pgvector_repository import (
    RankedSegment,
    active_target,
    dense_search,
    fuse_rankings,
    lexical_search,
    section_key,
    topic_search,
)
from app.legal.evidence import default_embedding_provider
from app.legal.models import EmbeddingProfile, RetrievalSegment
from app.legal.release_scope import release_instruments
from app.legal.topics import demoted_sections, section_target, rights_question

TOP_K = 5
SIGNALS = ("dense", "lexical", "topic", "fallback", "fused")


def _sections(paths: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    for path in paths:
        number = section_target(path)
        if number and number not in ordered:
            ordered.append(number)
    return ordered


def _paths(rows: Sequence[tuple[RetrievalSegment, float]]) -> list[str]:
    return [segment.canonical_path for segment, _score in rows]


def _ranked_paths(rows: Sequence[RankedSegment]) -> list[str]:
    return [item.segment.canonical_path for item in rows]


def _metrics(
    rankings: Sequence[list[str]], expected: Sequence[set[str]]
) -> dict[str, float]:
    total = len(expected)
    hit_1 = sum(
        1
        for ranked, want in zip(rankings, expected, strict=True)
        if ranked[:1] and ranked[0] in want
    )
    hit_5 = sum(
        1
        for ranked, want in zip(rankings, expected, strict=True)
        if set(ranked[:TOP_K]) & want
    )
    mrr = sum(
        next(
            (1 / rank for rank, number in enumerate(ranked[:10], 1) if number in want),
            0.0,
        )
        for ranked, want in zip(rankings, expected, strict=True)
    )
    return {
        "hit_at_1": round(hit_1 / total, 2),
        "hit_at_5": round(hit_5 / total, 2),
        "mrr_at_10": round(mrr / total, 2),
    }


def run_dataset(session: Session, cases: list[dict[str, Any]]) -> dict[str, Any]:
    target = active_target(session)
    available = {
        instrument.slug
        for instrument in release_instruments(session, target.release_id).values()
    }
    required = {
        section.partition(":")[0]
        for case in cases
        for section in case["expected_sections"]
    }
    if not cases or any(
        ":" not in section for case in cases for section in case["expected_sections"]
    ):
        raise ValueError(
            "Benchmark cases require instrument-qualified expected_sections"
        )
    if required - available:
        return {
            "cases": len(cases),
            "status": "blocked",
            "reason": "Required instruments are absent from the active release",
            "missing_instruments": sorted(required - available),
        }
    profile = session.get(EmbeddingProfile, target.profile_id)
    if profile is None:
        raise SystemExit("Active retrieval target has no embedding profile")
    queries = [case["query"] for case in cases]
    vectors = default_embedding_provider(profile).embed(queries).vectors
    expected = [set(case["expected_sections"]) for case in cases]
    rankings: dict[str, list[list[str]]] = {signal: [] for signal in SIGNALS}
    repeated_sections = 0
    misses: list[dict[str, Any]] = []
    for query, vector, want in zip(queries, vectors, expected, strict=True):
        scope = {"release_id": target.release_id, "query": query}
        demoted = demoted_sections(query)
        dense = dense_search(
            session,
            release_id=target.release_id,
            embedding_run_id=target.embedding_run_id,
            query_vector=vector,
        )
        lexical = lexical_search(session, **scope)
        topics = topic_search(session, **scope)
        fused = fuse_rankings(
            dense=dense,
            lexical=lexical,
            topics=topics,
            top_k=10,
            lexical_weight=settings.RETRIEVAL_LEXICAL_WEIGHT,
            demoted=demoted,
            prefer_constitution=rights_question(query),
            balance_instruments=len(available) > 1,
        )
        fallback = fuse_rankings(
            lexical=lexical,
            topics=topics,
            top_k=10,
            lexical_weight=settings.RETRIEVAL_LEXICAL_WEIGHT,
            demoted=demoted,
            prefer_constitution=rights_question(query),
            balance_instruments=len(available) > 1,
        )
        rankings["dense"].append(_sections(_paths(dense)))
        rankings["lexical"].append(_sections(_paths(lexical)))
        rankings["topic"].append(_sections(_paths(topics)))
        rankings["fallback"].append(_sections(_ranked_paths(fallback)))
        rankings["fused"].append(_sections(_ranked_paths(fused)))
        top_keys = [section_key(path) for path in _ranked_paths(fused)[:TOP_K]]
        if len(set(top_keys)) < len(top_keys):
            repeated_sections += 1
        if not (rankings["fused"][-1][:1] and rankings["fused"][-1][0] in want):
            misses.append(
                {
                    "query": query,
                    "expected": sorted(want),
                    "fused": rankings["fused"][-1][:TOP_K],
                    "dense": rankings["dense"][-1][:3],
                }
            )
    return {
        "cases": len(cases),
        "signals": {signal: _metrics(rankings[signal], expected) for signal in SIGNALS},
        "fused_top5_with_repeated_section": repeated_sections,
        "fused_misses": misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()
    report: dict[str, Any] = {
        "lexical_weight": settings.RETRIEVAL_LEXICAL_WEIGHT,
        "rrf_k": settings.RETRIEVAL_RRF_K,
        "datasets": {},
    }
    with Session(engine) as session:
        for path in args.datasets:
            dataset = json.loads(path.read_text(encoding="utf-8"))
            report["datasets"][dataset["version"]] = run_dataset(
                session, dataset["cases"]
            )
    if args.json:
        print(json.dumps(report, indent=2))  # noqa: T201
        return
    lines = [f"lexical weight {report['lexical_weight']}, rrf k {report['rrf_k']}"]
    for version, result in report["datasets"].items():
        lines.append(f"\n{version} ({result['cases']} cases)")
        if result.get("status") == "blocked":
            lines.append(
                f"  blocked: {result['reason']}: {result['missing_instruments']}"
            )
            continue
        for signal, metrics in result["signals"].items():
            lines.append(
                f"  {signal:9} hit@1 {metrics['hit_at_1']:.2f}"
                f"  hit@5 {metrics['hit_at_5']:.2f}"
                f"  mrr@10 {metrics['mrr_at_10']:.2f}"
            )
        lines.append(
            "  fused top 5 repeating a section: "
            f"{result['fused_top5_with_repeated_section']}/{result['cases']}"
        )
        lines.extend(
            f"  miss: {miss['query']!r} expected {miss['expected']}, "
            f"got {miss['fused']} (dense {miss['dense']})"
            for miss in result["fused_misses"]
        )
    print("\n".join(lines))  # noqa: T201


if __name__ == "__main__":
    main()
