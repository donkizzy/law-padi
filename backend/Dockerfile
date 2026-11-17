# syntax=docker/dockerfile:1
FROM oven/bun:1@sha256:1d22548f177f4ff38e0c15baa3c2c46c6c2060ba2d1bc573bb4720b407548f1d AS frontend-build
WORKDIR /app
COPY package.json bun.lock /app/
COPY frontend/package.json /app/frontend/
WORKDIR /app/frontend
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile
COPY frontend/index.html frontend/vite.config.ts frontend/tsconfig*.json frontend/playwright.config.ts /app/frontend/
COPY frontend/src /app/frontend/src
COPY frontend/public /app/frontend/public
COPY eval/datasets/plain-language-retrieval-benchmark-v1.json /app/eval/datasets/
ARG VITE_API_URL=
ARG BUILD_REVISION=development
ENV VITE_BUILD_REVISION=$BUILD_REVISION
RUN bun run build

# Dependency tooling and caches never enter a production image. Import the app
# from /app/backend rather than installing another copy of its source in .venv.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.26@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package app

FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS runtime
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
RUN useradd --system --uid 10001 --create-home app \
    && mkdir -p /app/backend/storage/source-documents \
    && chown -R 10001:10001 /app/backend/storage
USER 10001

# Same-origin frontend + API for server deployments. Migrations remain runnable
# with: docker compose run --rm backend bash scripts/prestart.sh
FROM runtime AS production
COPY backend/scripts/prestart.sh /app/backend/scripts/prestart.sh
COPY --from=frontend-build /app/backend/app/frontend /app/backend/app/frontend
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2}"]

# Local Compose explicitly selects this target for fastapi dev / live reload.
FROM production AS development
USER root
COPY --from=ghcr.io/astral-sh/uv:0.9.26@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
COPY pyproject.toml uv.lock /app/
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/scripts /app/backend/scripts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package app
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

USER 10001

# Unqualified builds and production Compose use the lean production target.
FROM production AS default
