"""Run repeatable browser QA on a disposable, isolated database and local app.

uv run python scripts/browser_test_runner.py [Playwright arguments]
Requires local PostgreSQL and Mailpit, Bun, and installed Playwright browsers.
Never changes shared app rate limits or reuses the application/test database.
"""

import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_ready(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "QA server exited before becoming ready; inspect its log"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError, urllib.error.URLError:
            pass
        time.sleep(0.2)
    raise RuntimeError("QA server did not become ready within 45 seconds")


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def main() -> int:
    token = uuid4().hex[:12]
    # The name is generated here, never taken from an environment/CLI argument.
    database = f"law_padi_qa_{token}_e2e_test"
    source = make_url(str(settings.DATABASE_URL))
    target = source.set(database=database)
    if (
        target == source
        or not database.startswith("law_padi_qa_")
        or not database.endswith("_e2e_test")
    ):
        raise RuntimeError("Refusing to run browser QA against a shared database")
    admin_dsn = (
        source.set(database="postgres")
        .render_as_string(hide_password=False)
        .replace("postgresql+psycopg://", "postgresql://", 1)
    )
    output = ROOT / "output/playwright" / f"isolated-{token}"
    output.mkdir(parents=True)
    env_file = output / "runtime.env"
    env_file.write_text("")
    api_port, frontend_port = free_port(), free_port()
    while api_port == frontend_port:
        frontend_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    env = {
        **os.environ,
        "APP_RUNTIME_ENV_FILE": str(env_file),
        "PROJECT_NAME": "constitution.ng isolated QA",
        "DATABASE_URL": target.render_as_string(hide_password=False),
        "DATABASE_LISTENER_URL": target.render_as_string(hide_password=False),
        "FASTAPI_ENV": "development",
        "SECRET_KEY": secrets.token_urlsafe(32),
        "FIRST_SUPERUSER": f"qa-{token}@example.com",
        "FIRST_SUPERUSER_PASSWORD": f"Qa-{secrets.token_hex(12)}9!",
        "FRONTEND_HOST": frontend_url,
        "VITE_API_URL": api_url,
        "PLAYWRIGHT_BASE_URL": frontend_url,
        "PLAYWRIGHT_AUTH_FILE": str(output / "auth.json"),
        "MAILPIT_HOST": "http://127.0.0.1:8025",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": "1025",
        "SMTP_TLS": "false",
        "SMTP_SSL": "false",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
        "EMAILS_FROM_EMAIL": "qa@example.com",
        "ORIGIN_PROXY_SECRET": "",
        "DEEPSEEK_API_KEY": "",
        "OPENAI_API_KEY": "",
        "RATE_LIMIT_ENABLED": "true",
        "CHAT_ENABLED": "false",
        "CHAT_GENERATION_ENABLED": "false",
        "EMBEDDING_QUERY_ENABLED": "false",
        "SENTRY_DSN": "",
    }
    processes: list[subprocess.Popen[bytes]] = []
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
        )
    try:
        with (
            (output / "api.log").open("wb") as api_log,
            (output / "frontend.log").open("wb") as frontend_log,
        ):
            for command in (
                ["alembic", "upgrade", "head"],
                [sys.executable, "-m", "app.initial_data"],
            ):
                subprocess.run(
                    command,
                    cwd=ROOT / "backend",
                    env=env,
                    stdout=api_log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            api = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                cwd=ROOT / "backend",
                env=env,
                stdout=api_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            processes.append(api)
            wait_ready(f"{api_url}/api/v1/utils/health-check/", api)
            frontend = subprocess.Popen(
                [
                    "bun",
                    "run",
                    "dev",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env=env,
                stdout=frontend_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            processes.append(frontend)
            wait_ready(frontend_url, frontend)
            sys.stdout.write(
                f"Isolated browser QA ready; rate limits enabled. Artifacts: {output}\n"
            )
            return subprocess.run(
                [
                    "bunx",
                    "playwright",
                    "test",
                    "--workers=2",
                    "--reporter=list",
                    f"--output={output / 'results'}",
                    *sys.argv[1:],
                ],
                cwd=ROOT / "frontend",
                env=env,
                check=False,
            ).returncode
    finally:
        for process in reversed(processes):
            stop(process)
        # Drop only this invocation's generated database, even on test failure.
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )
        sys.stdout.write("Isolated QA services stopped; disposable database removed.\n")


if __name__ == "__main__":
    sys.exit(main())
