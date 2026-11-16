"""Evaluate all paired reader-language retrieval datasets through the real API.

Runs 525 queries with two concurrent clients on one pinned public release.
Uses the app's provider budgets; no raw/oracle mode bypasses production translation.
Exit 0 means retrieval parity only, not native review or answer-translation approval.
"""

import argparse
import concurrent.futures
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.chat.translation import UNDERSTANDING_PROMPT_VERSION
from app.legal.topics import section_target

ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = ("en", "pcm", "yo", "ha", "ig")
SPLITS = ("benchmark", "heldout")


def load_cases() -> list[dict[str, Any]]:
    rows = []
    for language in LANGUAGES:
        suffix = "" if language == "en" else f"-{language}"
        for split in SPLITS:
            path = ROOT / f"eval/datasets/plain-language-retrieval-{split}{suffix}-v1.json"
            dataset = json.loads(path.read_text())
            rows.extend(
                {
                    **case,
                    "language": language,
                    "split": split,
                    "dataset": dataset["version"],
                }
                for case in dataset["cases"]
            )
    return rows


def probe(case: dict[str, Any], base: str, release: str) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(
        f"{base}/api/v1/legal/search",
        data=json.dumps(
            {"query": case["query"], "top_k": 5, "release_version": release}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status, body = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        status, body = error.code, json.load(error)
    except (OSError, ValueError) as error:
        status, body = 0, {"detail": str(error)}
    ranked = [
        target
        for result in body.get("data", [])
        if (target := section_target(result["canonical_path"]))
    ]
    expected = set(case["expected_sections"])
    valid = status == 200 and body.get("release_version") == release
    return {
        **case,
        "status": status,
        "seconds": round(time.perf_counter() - started, 3),
        "valid_response": valid,
        "release_version": body.get("release_version"),
        "query_language": body.get("query_language"),
        "searched_query": body.get("searched_query"),
        "retrieval_mode": body.get("retrieval_mode"),
        "message_code": body.get("message_code"),
        "ranked_sections": ranked,
        "hit_at_1": bool(ranked and ranked[0] in expected) if valid else None,
        "hit_at_5": bool(set(ranked) & expected) if valid else None,
        "reciprocal_rank": next(
            (1 / rank for rank, target in enumerate(ranked, 1) if target in expected), 0
        )
        if valid
        else None,
        "error": None
        if valid
        else body.get("detail", "Release changed or response was invalid"),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for language in LANGUAGES:
        result[language] = {}
        for split in SPLITS:
            cases = [
                row
                for row in rows
                if row["language"] == language and row["split"] == split
            ]
            valid = [row for row in cases if row["valid_response"]]
            result[language][split] = {
                "cases": len(cases),
                "completed": len(valid),
                "hit_at_1": sum(bool(row["hit_at_1"]) for row in valid) / len(cases),
                "hit_at_5": sum(bool(row["hit_at_5"]) for row in valid) / len(cases),
                "mrr_at_5": sum(row["reciprocal_rank"] for row in valid) / len(cases),
                "translated": sum(bool(row["searched_query"]) for row in valid),
                "nearby_warning": sum(
                    row["message_code"] == "not_covered" for row in valid
                ),
                "retrieval_modes": sorted({row["retrieval_mode"] for row in valid}),
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output/playwright/production-qa/fix-reader-retrieval.json",
    )
    args = parser.parse_args()
    with urllib.request.urlopen(
        f"{args.base_url}/api/v1/legal/releases/current", timeout=15
    ) as response:
        release = json.load(response)["release_version"]
    cases = load_cases()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for index, row in enumerate(
            pool.map(lambda case: probe(case, args.base_url, release), cases), 1
        ):
            rows.append(row)
            if index % 25 == 0:
                sys.stdout.write(
                    f"Reader retrieval: {index}/{len(cases)} responses captured\n"
                )
                sys.stdout.flush()
    summary = summarize(rows)
    gates = {
        language: {
            split: summary[language][split]["completed"]
            == summary[language][split]["cases"]
            and summary["en"][split]["completed"] == summary["en"][split]["cases"]
            and summary[language][split]["hit_at_5"] + 1e-9
            >= summary["en"][split]["hit_at_5"] - 0.05
            for split in SPLITS
        }
        for language in LANGUAGES
        if language != "en"
    }
    files = (
        "app/languages/detect.py",
        "app/legal/topics.py",
        "app/legal/evidence.py",
        "app/chat/search_language.py",
        "app/chat/translation.py",
    )
    report = {
        "release_version": release,
        "understanding_prompt_version": UNDERSTANDING_PROMPT_VERSION,
        "client_source_sha256": {
            file: hashlib.sha256((ROOT / "backend" / file).read_bytes()).hexdigest()
            for file in files
        },
        "datasets": summary,
        "retrieval_parity_gates": gates,
        "retrieval_parity_passed": all(
            passed
            for gates_for_language in gates.values()
            for passed in gates_for_language.values()
        ),
        "native_review": "not_performed",
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    sys.stdout.write(
        json.dumps({"datasets": summary, "gates": gates}, ensure_ascii=False, indent=2)
        + "\n"
    )
    return 0 if report["retrieval_parity_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
