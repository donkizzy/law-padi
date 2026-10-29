"""Run 62 bounded local search probes against the application's provider budget.

Usage: python3 backend/scripts/production_qa_probe.py
Raw evidence is written under ignored output/playwright/production-qa/.
This diagnostic sample is not a multilingual release evaluation gate.
"""

import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output/playwright/production-qa/search-results-expanded.json"
LANGUAGES = ("en", "pcm", "yo", "ha", "ig")
SAMPLE_INDICES = (0, 4, 8, 12, 16, 20, 26, 30, 35, 45)


def cases() -> list[dict[str, Any]]:
    selected = []
    for language in LANGUAGES:
        suffix = "" if language == "en" else f"-{language}"
        dataset = ROOT / f"docs/plain-language-retrieval-benchmark{suffix}-v1.json"
        source = json.loads(dataset.read_text())["cases"]
        selected.extend(
            {**source[index], "language": language} for index in SAMPLE_INDICES
        )
    selected.extend(
        {"query": query, "language": "edge"}
        for query in (
            "Section 37",
            "Section 35(4)",
            "Sections 37-39",
            "Section 168",
            "Section 9999",
            "ACJA s.9",
            "Police Act s.38",
            "",
            "   ",
            "x" * 2001,
            "zxqvplm nonsense xyz",
            "Who won the World Cup?",
        )
    )
    return selected


def probe(case: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    request = urllib.request.Request(
        "http://localhost:8000/api/v1/legal/search",
        data=json.dumps({"query": case["query"], "top_k": 5}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status, body = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        status, body = error.code, json.load(error)
    except Exception as error:
        status, body = 0, {"error": str(error)}
    ranked = [
        f"{row['instrument_slug']}:{match.group(1)}"
        for row in body.get("data", [])
        if (match := re.search(r"\.section(\d+)", row["canonical_path"]))
    ]
    result = {
        **case,
        "status": status,
        "seconds": round(time.perf_counter() - start, 3),
        "ranked_sections": ranked,
        "response": body,
    }
    if case.get("expected_sections"):
        expected = set(case["expected_sections"])
        # Infrastructure errors must not masquerade as retrieval misses.
        result["hit_at_1"] = (
            bool(ranked and ranked[0] in expected) if status == 200 else None
        )
        result["hit_at_5"] = bool(set(ranked) & expected) if status == 200 else None
    return result


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(probe, cases()))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for language in LANGUAGES:
        rows = [row for row in results if row["language"] == language]
        successful = [row for row in rows if row["status"] == 200]
        sys.stdout.write(
            json.dumps(
                {
                    "language": language,
                    "successful_requests": len(successful),
                    "total_requests": len(rows),
                    "hit_at_1": sum(bool(row["hit_at_1"]) for row in successful),
                    "hit_at_5": sum(bool(row["hit_at_5"]) for row in successful),
                }
            )
            + "\n"
        )
    sys.stdout.write(f"Evidence: {OUTPUT}\n")


if __name__ == "__main__":
    main()
