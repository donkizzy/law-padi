#!/usr/bin/env python3
# ruff: noqa: T201 -- Operator report contains paths and object IDs only.
"""Review or create a private deployment snapshot without touching checkout/index.

Default `plan` only reads repository state and writes an ignored path report.
`prepare` writes blobs/tree through a temporary GIT_INDEX_FILE, without a commit
or branch. `commit` must be invoked only after the release operator's GO. It
creates a commit-tree and advances only codex/render-free-beta; it never pushes.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
BRANCH = "refs/heads/codex/render-free-beta"
PATHS = (
    "backend/app",
    "backend/tests",
    "backend/scripts",
    "backend/pyproject.toml",
    "backend/alembic.ini",
    "backend/Dockerfile",
    "backend/.dockerignore",
    "frontend/src",
    "frontend/public",
    "frontend/tests",
    "frontend/package.json",
    "frontend/index.html",
    "frontend/vite.config.ts",
    "frontend/biome.json",
    "frontend/tsconfig.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.node.json",
    "frontend/tsconfig.build.json",
    "frontend/playwright.config.ts",
    "frontend/.gitignore",
    "deployment/render",
    "deployment/cloudflare",
    "deployment/.gitignore",
    "deployment/tests",
    "render.yaml",
    "scripts/build_revision.py",
    "scripts/generate-client.sh",
    "eval/datasets/constitution-explanation-evaluation-v1.json",
    "docs/evidence-chat-rollout.md",
    "package.json",
    "bun.lock",
    "pyproject.toml",
    "uv.lock",
    ".dockerignore",
    ".gitignore",
    ".python-version",
)
BLOCKED_PARTS = {
    "node_modules",
    "__pycache__",
    ".venv",
    ".wrangler",
    ".gcloud",
    "storage",
    "htmlcov",
    "test-results",
    "playwright-report",
    "blob-report",
}
BLOCKED_SUFFIXES = (
    ".sql.gz",
    ".dump",
    ".tar",
    ".env",
    ".report.json",
    ".pyc",
    ".key",
    ".pem",
    ".p12",
)


def git(*arguments, environment=None, check=True):
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        env=environment,
        check=check,
        capture_output=True,
    )
    return result.stdout


def state():
    index = Path(git("rev-parse", "--git-path", "index").decode().strip())
    if not index.is_absolute():
        index = ROOT / index
    return {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "checkout": git("symbolic-ref", "-q", "HEAD", check=False).decode().strip(),
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest()
        if index.exists()
        else None,
    }


def selected_paths():
    names = git(
        "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *PATHS
    ).split(b"\0")
    selected = []
    for raw in names:
        if not raw:
            continue
        name = raw.decode()
        path = Path(name)
        if set(path.parts) & BLOCKED_PARTS or name.endswith(BLOCKED_SUFFIXES):
            continue
        if path.name in {"project.json", "wrangler.generated.json", ".env"}:
            continue
        if "backend/app/frontend" in name or ".env." in path.name:
            continue
        if (ROOT / path).is_symlink():
            raise ValueError(f"Review symlink before snapshot: {name}")
        selected.append(name)
    return sorted(set(selected))


def scan_secrets(paths):
    protected = {}
    for source in [ROOT / ".env", *sorted((ROOT / "deployment").glob("*.env"))]:
        if not source.is_file():
            continue
        for key, value in dotenv_values(source).items():
            if value and key in {"DATABASE_URL", "DATABASE_LISTENER_URL"}:
                protected[value.encode()] = key
                password = urlparse(value).password
                if password and len(password) >= 12:
                    protected[password.encode()] = f"{key} password"
                    protected[unquote(password).encode()] = f"{key} password"
            if (
                value
                and len(value) >= 16
                and any(word in key for word in ("KEY", "SECRET", "TOKEN", "PASSWORD"))
            ):
                protected[value.encode()] = key
    for name in paths:
        path = ROOT / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if re.search(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----", data):
            raise ValueError(f"Private-key material detected in {name}")
        for value, key in protected.items():
            if value in data:
                raise ValueError(f"Actual configured {key} value detected in {name}")


def revision():
    return subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/build_revision.py")], cwd=ROOT, text=True
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("plan", "prepare", "commit"), nargs="?", default="plan"
    )
    parser.add_argument("--expected-revision")
    args = parser.parse_args()
    before = state()
    if before["checkout"] == BRANCH:
        raise ValueError(
            "Keep the user checkout on its original branch while snapshotting"
        )
    paths = selected_paths()
    scan_secrets(paths)
    current_revision = revision()
    if args.command != "plan" and args.expected_revision != current_revision:
        raise ValueError(
            "Expected revision must match the final verified working sources"
        )
    report = {
        "mode": args.command,
        "source_revision": current_revision,
        "base_head": before["head"],
        "deployment_branch": BRANCH,
        "selected_path_count": len(paths),
        "selected_paths": paths,
        "working_checkout_and_index_preserved": True,
        "pushed": False,
    }
    if args.command in {"prepare", "commit"}:
        with tempfile.TemporaryDirectory(prefix="law-padi-deploy-index-") as directory:
            environment = {
                **os.environ,
                "GIT_INDEX_FILE": str(Path(directory) / "index"),
            }
            git("read-tree", before["head"], environment=environment)
            git("add", "--all", "--", *paths, environment=environment)
            tree = git("write-tree", environment=environment).decode().strip()
            changed = (
                git("diff", "--name-only", before["head"], tree, "--")
                .decode()
                .splitlines()
            )
            if not set(changed).issubset(paths):
                raise ValueError(
                    "Snapshot includes changes outside the reviewed allowlist"
                )
            report["tree"] = tree
            report["changed_paths"] = changed
            report["diff_stat"] = (
                git("diff", "--stat", before["head"], tree, "--").decode().strip()
            )
            if revision() != current_revision or state() != before:
                raise ValueError(
                    "Sources, checkout, or user index changed while preparing snapshot"
                )
            if args.command == "commit":
                old_tip = (
                    git("rev-parse", "--verify", BRANCH, check=False).decode().strip()
                )
                parent = old_tip or before["head"]
                commit = (
                    git(
                        "commit-tree",
                        tree,
                        "-p",
                        parent,
                        "-m",
                        "deploy: prepare Render Free beta [skip ci]",
                        "-m",
                        f"Verified source revision: {current_revision}",
                        environment=environment,
                    )
                    .decode()
                    .strip()
                )
                if state() != before or revision() != current_revision:
                    raise ValueError(
                        "User state changed; deployment branch was not advanced"
                    )
                git("update-ref", BRANCH, commit, old_tip or "0" * 40)
                report["commit"] = commit
    if state() != before:
        raise ValueError(
            "User checkout/index changed unexpectedly; investigate before publishing"
        )
    output = ROOT / "deployment/render/snapshot.report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"selected_paths", "changed_paths", "diff_stat"}
            },
            indent=2,
        )
    )
    print("Full path/diff report: deployment/render/snapshot.report.json")


if __name__ == "__main__":
    main()
