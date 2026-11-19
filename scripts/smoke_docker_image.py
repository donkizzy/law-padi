"""Run inside a built image; no credentials, providers or live database required.

Example:
    docker run --rm -i --entrypoint python IMAGE - compose < scripts/smoke_docker_image.py
"""

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "runtime", choices=("compose", "ingestion", "development")
)
runtime = parser.parse_args().runtime
database = "postgresql+psycopg://smoke:smoke@127.0.0.1:1/docker_smoke_test"
if not urlsplit(database).path.endswith("_test"):
    raise ValueError("The smoke database name must end in _test")
os.environ.update(
    PROJECT_NAME="Docker smoke test",
    SECRET_KEY="docker-smoke-test-key-with-at-least-32-characters",
    FIRST_SUPERUSER="smoke@example.com",
    FIRST_SUPERUSER_PASSWORD="docker-smoke-test-password",
    DATABASE_URL=database,
    ORIGIN_PROXY_SECRET="docker-smoke-origin-secret-with-at-least-32-characters",
    APP_RUNTIME_ENV_FILE="/nonexistent/docker-smoke.env",
    SERVE_FRONTEND="true" if runtime != "ingestion" else "false",
)
app_dir = Path("/app/backend/app")

# Exercise the worker's real import graph, which also uses shared legal modules.
importlib.import_module("app.ingestion.runtime.runner")
importlib.import_module("app.legal.evidence")
importlib.import_module("psycopg")
for path in (app_dir / "legal/data").glob("*.json"):
    json.loads(path.read_text())
for path in (app_dir / "languages/data").glob("*.json"):
    json.loads(path.read_text())

if runtime == "ingestion":
    from ingestion_worker.cli import WorkerSettings
    from pypdf import PdfWriter

    from app.ingestion.ocr import OcrPageInput, TesseractOcrProvider
    from app.ingestion.rendering import render_page_thumbnail

    assert WorkerSettings.from_env().max_tasks_per_poll > 0
    pdf = PdfWriter()
    pdf.add_blank_page(width=300, height=300)
    content = BytesIO()
    pdf.write(content)
    thumbnail = render_page_thumbnail(content.getvalue(), page_number=1)
    assert thumbnail.content.startswith(b"\x89PNG\r\n\x1a\n")
    result = TesseractOcrProvider().extract_page(
        OcrPageInput(page_number=1, image=thumbnail.content, content_type="image/png")
    )
    assert result.provider == "tesseract"
else:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.utils import generate_verify_email_email

    # Deliberately omit the lifespan, which would query the database.
    client = TestClient(
        app, headers={"X-Origin-Proxy-Secret": os.environ["ORIGIN_PROXY_SECRET"]}
    )
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200, response.text
    assert "/api/v1/utils/health-check/" in response.json()["paths"]
    assert (
        "docker-test-token"
        in generate_verify_email_email(
            email_to="smoke@example.com", token="docker-test-token"
        ).html_content
    )
    importlib.import_module("app.chat.worker")
    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="root">' in response.text
    subprocess.run(["bash", "-n", "scripts/prestart.sh"], check=True)
    subprocess.run(["alembic", "heads"], check=True)
    # Console scripts and direct app/*.py commands must resolve shared modules
    # without relying on the working directory or an editable installation.
    subprocess.run(
        [sys.executable, "-c", "from app.models import SQLModel"],
        cwd="/tmp",
        check=True,
    )
    subprocess.run(["uvicorn", "--version"], check=True)

if runtime == "development":
    subprocess.run(["fastapi", "dev", "--help"], check=True, stdout=subprocess.DEVNULL)
    assert shutil.which("uv")

if runtime != "development":
    for name in ("pytest", "mypy", "ruff", "fastapi_cli", "fastapi_cloud_cli"):
        assert importlib.util.find_spec(name) is None, (
            f"Unneeded runtime package: {name}"
        )
    for executable in ("uv", "uvx", "bun", "node", "gcc", "curl"):
        assert shutil.which(executable) is None, f"Unneeded runtime tool: {executable}"
    assert not (app_dir.parent / "scripts/lint.sh").exists()
    assert not list(Path("/app/.venv").rglob("*.pyc"))

print(f"{runtime}: runtime smoke checks passed")
