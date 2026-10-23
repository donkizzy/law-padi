"""Reader notices attached to individual provisions, from a reviewed data file."""

import json
from functools import cache
from pathlib import Path

from app.legal.schemas import ProvisionNotice

DATA_FILE = Path(__file__).parent / "data" / "provision-notices.json"


@cache
def _notices() -> tuple[tuple[str, ProvisionNotice], ...]:
    if not DATA_FILE.is_file():
        return ()
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return tuple(
        (
            item["canonical_path"],
            ProvisionNotice(
                code=item["code"],
                text=item["text"],
                params={str(k): str(v) for k, v in item.get("params", {}).items()},
            ),
        )
        for item in data.get("notices", [])
    )


def provision_notices(canonical_path: str) -> list[ProvisionNotice]:
    """Notices for a provision and for any provision it sits beneath."""
    return [
        notice
        for path, notice in _notices()
        if canonical_path == path or canonical_path.startswith(f"{path}.")
    ]
