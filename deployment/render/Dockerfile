# syntax=docker/dockerfile:1
# Render Free runs one API process with a request-woken chat worker.
# Compute the packaged revision at build time for GitHub-triggered deploys.
FROM python:3.14-slim-trixie AS revision
WORKDIR /source
COPY backend/app /source/backend/app
COPY frontend/src /source/frontend/src
COPY frontend/public /source/frontend/public
COPY frontend/package.json frontend/vite.config.ts frontend/index.html /source/frontend/
COPY backend/pyproject.toml backend/Dockerfile /source/backend/
COPY deployment/cloudflare/worker.ts deployment/cloudflare/public-pages.ts deployment/cloudflare/wrangler.json deployment/cloudflare/tsconfig.json /source/deployment/cloudflare/
COPY deployment/render/Dockerfile deployment/render/start.sh /source/deployment/render/
COPY bun.lock uv.lock package.json .dockerignore /source/
COPY eval/datasets/plain-language-retrieval-benchmark-v1.json /source/eval/datasets/
COPY scripts/build_revision.py /source/scripts/
RUN python scripts/build_revision.py > /source-revision

# Keep dependency installation aligned with backend/Dockerfile's dependencies stage.
FROM python:3.14-slim-trixie AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package app

FROM python:3.14-slim-trixie
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PATH="/app/.venv/bin:$PATH" \
    SERVE_FRONTEND=false \
    APP_RUNTIME_ROLE=api \
    APP_RUNTIME_ENV_FILE=/etc/secrets/runtime.env
RUN useradd --system --uid 10001 --create-home app
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app /app/backend/app
COPY backend/alembic.ini /app/backend/alembic.ini
COPY deployment/render/start.sh /app/backend/scripts/start-render.sh
COPY --from=revision /source-revision /app/source-revision
ARG BUILD_REVISION=development
ENV BUILD_REVISION=$BUILD_REVISION
WORKDIR /app/backend
USER 10001
EXPOSE 10000
CMD ["sh", "/app/backend/scripts/start-render.sh"]
