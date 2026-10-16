"""Prepare Cloudflare's Render-backed config without exposing a pending launch.

This reads no credentials. Public routing stays disabled until an operator
explicitly supplies --public after the matching AI evaluation and human review.
The generated config is ignored; credentials remain Cloudflare Worker secrets.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
API_ORIGIN = "https://constitution-ng-api.onrender.com"


def configuration(api_origin: str, *, public: bool) -> dict:
    origin = urlsplit(api_origin)
    if (
        origin.scheme != "https"
        or origin.hostname != "constitution-ng-api.onrender.com"
        or origin.username
        or origin.password
        or origin.port
        or origin.path not in {"", "/"}
        or origin.query
        or origin.fragment
    ):
        raise ValueError("Use the verified constitution-ng-api HTTPS origin")
    config = json.loads((ROOT / "deployment/cloudflare/wrangler.json").read_text())
    config["main"] = "cloudflare/worker.ts"
    config["assets"]["directory"] = "../backend/app/frontend"
    config["vars"]["API_ORIGIN"] = API_ORIGIN
    config["workers_dev"] = public
    # Version URLs otherwise permit access before the main hostname is enabled.
    config["preview_urls"] = False
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-origin", default=API_ORIGIN)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    actual = subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/build_revision.py")], text=True
    ).strip()
    if (
        not re.fullmatch(r"source-[0-9a-f]{16}", args.revision)
        or actual != args.revision
    ):
        parser.error("Revision must match the current packaged sources")
    if not (ROOT / "backend/app/frontend/index.html").is_file():
        parser.error("Build the frontend before preparing the Worker")
    config = configuration(args.api_origin, public=args.public)
    output = ROOT / "deployment/wrangler.generated.json"
    output.write_text(json.dumps(config, indent=2) + "\n")
    print(  # noqa: T201
        json.dumps(
            {"config": str(output), "revision": actual, "public_routing": args.public}
        )
    )


if __name__ == "__main__":
    main()
