# syntax=docker/dockerfile:1
FROM oven/bun:1 AS frontend-build
WORKDIR /app
COPY package.json bun.lock /app/
COPY frontend/package.json /app/frontend/
WORKDIR /app/frontend
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile
COPY frontend/index.html frontend/vite.config.ts frontend/tsconfig*.json frontend/playwright.config.ts /app/frontend/
COPY frontend/src /app/frontend/src
COPY frontend/public /app/frontend/public
COPY docs/plain-language-retrieval-benchmark-v1.json /app/docs/
ARG VITE_API_URL=
ARG BUILD_REVISION=development
ENV VITE_BUILD_REVISION=$BUILD_REVISION
RUN bun run build

# Dependency tooling and caches never enter a production image. Import the app
# from /app/backend rather than installing another copy of its source in .venv.
FROM python:3.14-slim-trixie AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package app

FROM python:3.14-slim-trixie AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app/backend
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app /app/backend/app
COPY backend/alembic.ini /app/backend/alembic.ini
ARG BUILD_REVISION=development
ENV BUILD_REVISION=$BUILD_REVISION

# Install the PostgreSQL client in a builder. The backup handler only executes
# pg_dump; psql, Perl, package caches and the other client tools stay here.
FROM python:3.14-slim-trixie AS postgres-backup-tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl --fail --silent --show-error \
       https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       --output /usr/share/keyrings/postgresql.asc \
    && echo 'deb [signed-by=/usr/share/keyrings/postgresql.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main' \
       > /etc/apt/sources.list.d/postgresql.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*
# ldd includes the transitive shared-library dependencies. Resolve directory
# symlinks while retaining each library's SONAME (e.g. libpq.so.5).
RUN python - <<'PY'
from pathlib import Path
import shutil
import subprocess

root = Path('/pg-runtime')
binary = Path('/usr/lib/postgresql/18/bin/pg_dump')
destination = root / 'usr/local/bin/pg_dump'
destination.parent.mkdir(parents=True)
shutil.copy2(binary, destination)
for line in subprocess.check_output(['ldd', str(binary)], text=True).splitlines():
    if 'not found' in line:
        raise RuntimeError(line)
    if '=>' not in line:
        continue
    library = Path(line.split('=>', 1)[1].strip().split()[0])
    destination = root / library.parent.resolve().relative_to('/') / library.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(library, destination)
PY

# The API and task handler share this target. pg_dump 18 is required by the
# scheduled backup handler; PDF/OCR tools and the frontend belong elsewhere.
FROM runtime AS cloud-run
ENV SERVE_FRONTEND=false \
    APP_RUNTIME_ENV_FILE=/run/secrets/runtime.env
COPY --from=postgres-backup-tools /pg-runtime/ /
RUN useradd --system --uid 10001 --create-home app
COPY backend/scripts/start-cloud-run.sh /app/backend/scripts/start-cloud-run.sh
USER 10001
EXPOSE 8080
CMD ["sh", "/app/backend/scripts/start-cloud-run.sh"]

# Same-origin frontend + API for server deployments. Migrations remain runnable
# with: docker compose run --rm backend bash scripts/prestart.sh
FROM runtime AS production
COPY backend/scripts/prestart.sh /app/backend/scripts/prestart.sh
COPY --from=frontend-build /app/backend/app/frontend /app/backend/app/frontend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Local Compose explicitly selects this target for fastapi dev / live reload.
FROM production AS development
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
COPY pyproject.toml uv.lock /app/
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/scripts /app/backend/scripts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package app
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Unqualified builds and production Compose use the lean production target.
FROM production AS default
