#!/usr/bin/env python3
# ruff: noqa: T201 -- Reports only non-secret completion status.
"""Combine private API/worker bundles into one generation-disabled Render file."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision")
    args = parser.parse_args()
    values = {}
    for name in ("api.env", "worker.env"):
        path = ROOT / "deployment" / name
        if path.stat().st_mode & 0o077:
            raise ValueError("Source secret bundles must have mode 600")
        for key, value in dotenv_values(path).items():
            if key in values and values[key] != value:
                raise ValueError(f"Runtime secret bundles disagree for {key}")
            values[key] = value
    revision = (
        args.revision
        or subprocess.check_output(
            [sys.executable, str(ROOT / "scripts/build_revision.py")],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    if not re.fullmatch(r"source-[a-f0-9]{16}", revision):
        raise ValueError("Supply a measured source revision")
    values.update(
        BUILD_REVISION=revision,
        APP_RUNTIME_ROLE="api",
        SERVE_FRONTEND="false",
        FRONTEND_HOST="https://constitition-ng.amosgodwin500.workers.dev",
        CHAT_ENABLED="true",
        CHAT_GENERATION_ENABLED="false",
        CHAT_GENERATION_KILL_SWITCH="true",
        CHAT_PROVIDER_CAPACITY_APPROVED="false",
        CHAT_DISPATCH_MODE="poll",
        CHAT_MAX_ACTIVE_GENERATIONS="1",
        CHAT_WORKER_CONCURRENCY="1",
        CHAT_DAILY_BUDGET_USD="0.12",
        CHAT_MONTHLY_BUDGET_USD="4",
        AI_MONTHLY_BUDGET_USD="5",
        EMBEDDING_QUERY_ENABLED="false",
        CHAT_GUEST_DAILY_LIMIT="3",
        CHAT_ACCOUNT_DAILY_LIMIT="10",
        CHAT_GUEST_BURST_LIMIT="1",
        CHAT_ACCOUNT_BURST_LIMIT="2",
        DATABASE_POOL_SIZE="5",
        DATABASE_CONNECT_TIMEOUT_SECONDS="15",
        DATABASE_STATEMENT_TIMEOUT_MS="30000",
        DATABASE_LOCK_TIMEOUT_MS="5000",
    )
    for key in list(values):
        if (
            key.startswith("GCP_")
            or key.startswith("GCS_")
            or key
            in {
                "CHAT_TASK_HANDLER_URL",
                "CHAT_TASK_SERVICE_ACCOUNT",
                "CHAT_TASK_AUDIENCE",
            }
        ):
            del values[key]
    required = {
        "SECRET_KEY",
        "DATABASE_URL",
        "DATABASE_LISTENER_URL",
        "FIRST_SUPERUSER",
        "FIRST_SUPERUSER_PASSWORD",
        "ORIGIN_PROXY_SECRET",
        "DEEPSEEK_API_KEY",
        "R2_ENDPOINT_URL",
        "R2_BUCKET_NAME",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    }
    if any(not values.get(key) for key in required):
        raise ValueError("Private bundles are incomplete")
    path = ROOT / "deployment/render.env"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("# PRIVATE Render runtime bundle. Never commit or print.\n")
        for key, value in sorted(values.items()):
            handle.write(f"{key}={json.dumps(value)}\n")
    print(
        f"Prepared ignored chmod-600 deployment/render.env for {revision}; generation remains disabled."
    )


if __name__ == "__main__":
    main()
