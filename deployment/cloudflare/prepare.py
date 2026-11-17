"""Prepare Cloudflare's Render-backed config without exposing a pending launch.

This reads no credentials: the Render API origin and the public site URL are
supplied by the operator and validated here. Public routing stays disabled until
an operator explicitly supplies --public after the matching AI evaluation and
human review.
The generated config is ignored; credentials remain Cloudflare Worker secrets.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
# Mirrors the hosts that worker.ts accepts for the API origin: a stricter
# value here stops a build that the Worker would only reject at request time.
API_HOST_SUFFIX = ".onrender.com"


def bare_https_origin(value: str, what: str, *, host_suffix: str = "") -> str:
    """Return `value` as a bare HTTPS origin, or raise ValueError.

    Rejects other schemes, credentials, ports, paths, queries and fragments.
    """
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        port = -1
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or not host
        or not host.endswith(host_suffix)
        or parts.username is not None
        or parts.password is not None
        or port is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError(f"{what} must be a bare HTTPS origin{_suffix_note(host_suffix)}")
    return f"https://{parts.netloc}"


def _suffix_note(host_suffix: str) -> str:
    return f" on a {host_suffix} host" if host_suffix else ""


def configuration(
    *,
    public: bool,
    site_url: str,
    api_origin: str,
    worker_name: str = "constitution-ng",
) -> dict:
    api = bare_https_origin(api_origin, "API origin", host_suffix=API_HOST_SUFFIX)
    site = bare_https_origin(site_url, "Public site URL")
    config = json.loads((ROOT / "deployment/cloudflare/wrangler.json").read_text())
    if worker_name not in {"constitution-ng", "constitition-ng"}:
        raise ValueError("Unknown Worker name")
    config["name"] = worker_name
    config["main"] = "cloudflare/worker.ts"
    config["assets"]["directory"] = "../backend/app/frontend"
    config.setdefault("vars", {}).update({"API_ORIGIN": api, "PUBLIC_SITE_URL": site})
    config["workers_dev"] = public
    # Version URLs otherwise permit access before the main hostname is enabled.
    config["preview_urls"] = False
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--site-url", required=True)
    parser.add_argument(
        "--api-origin",
        default=os.environ.get("API_ORIGIN"),
        help="Render API origin; defaults to the API_ORIGIN environment variable",
    )
    parser.add_argument("--worker-name", default=os.environ.get("CLOUDFLARE_WORKER_NAME", "constitition-ng"))
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
    if not args.api_origin:
        parser.error("Set --api-origin or the API_ORIGIN environment variable")
    try:
        config = configuration(
            public=args.public,
            site_url=args.site_url,
            api_origin=args.api_origin,
            worker_name=args.worker_name,
        )
    except ValueError as error:
        parser.error(str(error))
    output = ROOT / "deployment/wrangler.generated.json"
    output.write_text(json.dumps(config, indent=2) + "\n")
    print(  # noqa: T201
        json.dumps(
            {"config": str(output), "revision": actual, "public_routing": args.public}
        )
    )


if __name__ == "__main__":
    main()
