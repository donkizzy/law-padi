"""Source-specific navigation catalogues, independent of the topic guide."""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"


@cache
def title_catalog(instrument_slug: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", instrument_slug):
        return {}
    path = DATA_DIR / f"{instrument_slug}-section-titles.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def catalogue_titles(instrument_slug: str, kind: str) -> dict[str, str]:
    data = title_catalog(instrument_slug).get(kind, {})
    if not isinstance(data, dict):
        return {}
    return {
        key: value
        for key, value in data.items()
        if isinstance(key, str) and isinstance(value, str)
    }
