"""Reviewed plain-language search phrasing for individual provisions."""

import json
from functools import cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "retrieval-phrasing.json"


@cache
def _phrasing() -> dict[str, str]:
    if not DATA_FILE.is_file():
        return {}
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {item["canonical_path"]: item["text"] for item in data.get("phrasing", [])}


def retrieval_phrasing(canonical_path: str) -> str | None:
    """Phrasing for exactly this provision; it never applies to its children."""
    return _phrasing().get(canonical_path)
