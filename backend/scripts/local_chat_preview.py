"""Run a capped, loopback-only chat preview against an existing isolated corpus."""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from sqlalchemy.engine import make_url

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent


def preview_environment(database: str) -> dict[str, str]:
    if not database.startswith("app_live_validation_"):
        raise ValueError("Use an existing app_live_validation_ database")
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is required in the local .env")
    if urlparse(settings.DEEPSEEK_BASE_URL).hostname != "api.deepseek.com":
        raise ValueError("The preview requires the official DeepSeek endpoint")

    url = make_url(str(settings.DATABASE_URL)).set(database=database)
    dsn = url.render_as_string(hide_password=False)
    with psycopg.connect(
        dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    ) as connection:
        published = connection.execute(
            "SELECT 1 FROM corpus_release WHERE status = 'production' LIMIT 1"
        ).fetchone()
    if not published:
        raise ValueError("The isolated database has no published corpus")

    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=dsn,
        CHAT_ENABLED="true",
        CHAT_GENERATION_ENABLED="true",
        CHAT_GENERATION_KILL_SWITCH="false",
        CHAT_MAX_ACTIVE_GENERATIONS="1",
        CHAT_WORKER_CONCURRENCY="1",
        CHAT_DAILY_BUDGET_USD="2",
        CHAT_GUEST_DAILY_LIMIT="10",
        CHAT_ACCOUNT_DAILY_LIMIT="10",
        FRONTEND_HOST="http://127.0.0.1:5173",
        FASTAPI_ENV="development",
    )
    return environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    environment = preview_environment(args.database)
    frontend_environment = {
        **os.environ,
        "VITE_API_URL": "http://127.0.0.1:18000",
        "VITE_CHAT_PREVIEW": "true",
    }
    services = [
        (
            "API",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18000",
            ],
            BACKEND_DIR,
            environment,
        ),
        ("worker", [sys.executable, "-m", "app.chat.worker"], BACKEND_DIR, environment),
        (
            "frontend",
            ["bun", "run", "dev", "--", "--host", "127.0.0.1"],
            ROOT_DIR,
            frontend_environment,
        ),
    ]
    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    try:
        for name, command, directory, env in services:
            process = subprocess.Popen(
                command, cwd=directory, env=env, start_new_session=True
            )
            processes.append((name, process))
        sys.stdout.write(
            "Local explanation preview: http://127.0.0.1:5173/\n"
            "Press Ctrl+C to stop all preview services.\n"
        )
        sys.stdout.flush()
        while True:
            for name, process in processes:
                code = process.poll()
                if code is not None:
                    raise RuntimeError(f"Preview {name} exited with status {code}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for _, process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    main()
