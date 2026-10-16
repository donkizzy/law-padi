"""Check versioned citation cases and optional human grounding judgments.

The live DeepSeek quality gate remains pending until every case has been
reviewed. This command does not infer legal support from a model score.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.chat import EXPLANATION_PROMPT_VERSION
from app.core.config import settings
from app.core.db import engine
from app.legal.evidence import exact_lookup
from app.legal.models import CorpusRelease
from app.legal.public_corpus import load_public_corpus
from app.legal.references import parse_section_reference


def _check_cases(dataset: dict[str, Any]) -> tuple[int, list[str]]:
    cases = dataset["cases"]
    failures: list[str] = []
    checked = 0
    with Session(engine) as session:
        release = session.exec(
            select(CorpusRelease).where(
                CorpusRelease.version == dataset["release_version"]
            )
        ).one()
        corpus = load_public_corpus(session, release)
        available_paths = {
            provision.canonical_path
            for provision in corpus.provisions.values()
            if provision.id in corpus.versions
        }
        for case in cases:
            expected = set(case["expected_paths"])
            if not expected.issubset(available_paths):
                failures.append(f"{case['id']}: expected identity is unavailable")
                continue
            if case["kind"] in {"exact", "exact_list", "exact_range"}:
                parsed = parse_section_reference(case["prompt"])
                outcome = exact_lookup(corpus, parsed, case["prompt"]).response
                actual = {item.canonical_path for item in outcome.data}
                if actual != expected:
                    failures.append(f"{case['id']}: exact identity mismatch")
                checked += 1
            elif case["expected_outcome"] == "missing":
                parsed = parse_section_reference(case["prompt"])
                outcome = exact_lookup(corpus, parsed, case["prompt"]).response
                if outcome.outcome != "not_found":
                    failures.append(f"{case['id']}: missing citation was not reported")
                checked += 1
            elif case["expected_outcome"] == "unsupported_instrument":
                parsed = parse_section_reference(case["prompt"])
                if parsed.error is None:
                    failures.append(f"{case['id']}: other instrument was not rejected")
                checked += 1
    return checked, failures


def _check_captures(
    dataset: dict[str, Any],
    path: Path,
    *,
    expected_prompt_version: str = EXPLANATION_PROMPT_VERSION,
    expected_build_revision: str | None = None,
    expected_retrieval_mode: str | None = None,
) -> list[str]:
    cases = {row["id"]: row for row in dataset["cases"]}
    captures = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    by_id = {row["id"]: row for row in captures}
    failures: list[str] = []
    if len(captures) != len(by_id) or set(by_id) != set(cases):
        return ["Every evaluation case requires one unique captured answer"]
    build_revision = expected_build_revision or settings.BUILD_REVISION
    retrieval_mode = expected_retrieval_mode or (
        "hybrid" if settings.EMBEDDING_QUERY_ENABLED else "lexical"
    )
    if build_revision == "development":
        failures.append("Expected packaged build revision is required for live review")
    if retrieval_mode not in {"lexical", "hybrid"}:
        failures.append("Expected query retrieval policy must be lexical or hybrid")
    for case_id, case in cases.items():
        capture = by_id[case_id]
        if capture.get("prompt_version") != expected_prompt_version:
            failures.append(f"{case_id}: captured prompt differs from current prompt")
        if capture.get("build_revision") != build_revision:
            failures.append(f"{case_id}: captured build differs from expected build")
        source = capture.get("retrieval_mode_source")
        confirmed_policy = source == "inline_worker_settings" or (
            source == "render_worker_settings"
            and capture.get("worker_dispatch") == "request_woken"
        )
        if capture.get("retrieval_mode") != retrieval_mode or not confirmed_policy:
            failures.append(
                f"{case_id}: captured query retrieval policy is not confirmed"
            )
        if "error" in capture or len(capture.get("turns", [])) != len(case["turns"]):
            failures.append(f"{case_id}: live answer capture is incomplete")
            continue
        if [turn.get("question") for turn in capture["turns"]] != case["turns"]:
            failures.append(f"{case_id}: captured questions differ from dataset")
        if capture.get("release_version") != dataset["release_version"]:
            failures.append(f"{case_id}: captured release differs from dataset")
        for turn in capture["turns"]:
            actual_mode = turn.get("retrieval_mode")
            if actual_mode not in {"exact", "lexical", "hybrid"} or (
                retrieval_mode == "lexical" and actual_mode == "hybrid"
            ):
                failures.append(
                    f"{case_id}: actual retrieval mode conflicts with captured policy"
                )
            answer = turn.get("answer") or {}
            evidence = answer.get("evidence") or []
            by_evidence_id = {item.get("evidence_id"): item for item in evidence}
            if len(by_evidence_id) != len(evidence):
                failures.append(f"{case_id}: duplicate evidence ID")
            for item in evidence:
                text = item.get("authoritative_text", "")
                if (
                    item.get("release_version") != dataset["release_version"]
                    or hashlib.sha256(text.encode()).hexdigest()
                    != item.get("text_sha256")
                    or not all(
                        item.get(field)
                        for field in (
                            "provision_version_id",
                            "canonical_path",
                            "citation",
                            "source_document_id",
                            "source_title",
                            "source_content_url",
                        )
                    )
                ):
                    failures.append(f"{case_id}: evidence provenance mismatch")
            for block in answer.get("blocks") or []:
                ids = block.get("evidence_ids") or []
                if not ids or any(
                    evidence_id not in by_evidence_id for evidence_id in ids
                ):
                    failures.append(f"{case_id}: block references unknown evidence")
                quotation = block.get("quotation")
                if quotation and not any(
                    quotation in by_evidence_id[evidence_id]["authoritative_text"]
                    for evidence_id in ids
                    if evidence_id in by_evidence_id
                ):
                    failures.append(
                        f"{case_id}: quotation is absent from cited evidence"
                    )
        if case["kind"] in {"exact", "exact_list", "exact_range"}:
            actual_paths = {
                item["canonical_path"]
                for item in (capture["turns"][-1].get("answer") or {}).get(
                    "evidence", []
                )
            }
            if not set(case["expected_paths"]).issubset(actual_paths):
                failures.append(f"{case_id}: captured exact evidence is incomplete")
    return failures


def _check_judgments(
    dataset: dict[str, Any], path: Path, captures_path: Path | None = None
) -> list[str]:
    cases = {row["id"]: row for row in dataset["cases"]}
    judgments = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    by_id = {row["id"]: row for row in judgments}
    failures: list[str] = []
    if len(judgments) != len(by_id) or set(by_id) != set(cases):
        failures.append("Every evaluation case requires one unique human judgment")
        return failures
    if captures_path is not None:
        captures = {
            row["id"]: row
            for line in captures_path.read_text().splitlines()
            if (row := json.loads(line.strip()))
        }
        for case_id, judgment in by_id.items():
            capture = captures.get(case_id)
            if (
                capture is None
                or judgment.get("answer_digest")
                != hashlib.sha256(
                    json.dumps(capture, sort_keys=True).encode()
                ).hexdigest()
            ):
                failures.append(f"{case_id}: judgment does not match captured answer")
            if (
                capture is not None
                and cases[case_id].get("expected_paths")
                and any(
                    turn.get("answer", {}).get("outcome")
                    not in {"completed", "partial_evidence"}
                    for turn in capture.get("turns", [])
                )
                and judgment.get("supported") is True
            ):
                failures.append(
                    f"{case_id}: a withheld explanation cannot be marked supported"
                )
    if any(row.get("critical_status_error") is not False for row in judgments):
        failures.append("A critical legal-status error was reported")
    if any(not isinstance(row.get("supported"), bool) for row in judgments):
        failures.append("Every case needs an explicit supported-answer judgment")
    supported = sum(row.get("supported") is True for row in judgments)
    if (
        supported / len(judgments)
        < dataset["gates"]["supported_answer_judgment_minimum"]
    ):
        failures.append("Supported-answer judgments are below 95%")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--expected-build-revision")
    parser.add_argument("--expected-retrieval-mode", choices=("lexical", "hybrid"))
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    if len(dataset["cases"]) < 200:
        raise ValueError("Evaluation dataset has fewer than 200 cases")
    checked, failures = _check_cases(dataset)
    if args.judgments and not args.captures:
        parser.error("--judgments requires --captures from live validation")
    if args.captures:
        failures.extend(
            _check_captures(
                dataset,
                args.captures,
                expected_build_revision=args.expected_build_revision,
                expected_retrieval_mode=args.expected_retrieval_mode,
            )
        )
    if args.judgments:
        failures.extend(_check_judgments(dataset, args.judgments, args.captures))
    print(f"Checked {checked} deterministic cases; failures: {len(failures)}")  # noqa: T201
    for failure in failures:
        print(failure)  # noqa: T201
    if failures:
        return 1
    if not args.judgments:
        print("Human supported-answer review is pending; rollout gate is not met.")  # noqa: T201
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
