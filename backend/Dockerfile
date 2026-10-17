FROM oven/bun:1 AS frontend-build

WORKDIR /app

COPY package.json bun.lock /app/
COPY frontend/package.json /app/frontend/

WORKDIR /app/frontend

RUN bun install --frozen-lockfile

COPY ./frontend /app/frontend
COPY docs/plain-language-retrieval-benchmark-v1.json /app/docs/

ARG VITE_API_URL=
ARG BUILD_REVISION=development
ENV VITE_BUILD_REVISION=$BUILD_REVISION

RUN bun run build


FROM python:3.14 AS development

ENV PYTHONUNBUFFERED=1

# PDF rendering is part of the ingestion evidence workflow.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --package app

COPY ./backend/scripts /app/backend/scripts

COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/

COPY ./backend/app /app/backend/app

COPY --from=frontend-build /app/backend/app/frontend /app/backend/app/frontend

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --package app

ARG BUILD_REVISION=development
ENV BUILD_REVISION=$BUILD_REVISION

WORKDIR /app/backend/

CMD ["fastapi", "run", "--workers", "4"]

# The Cloud Run target does not depend on the frontend build or Poppler. Keep
# PDF rendering in the existing development/ingestion image above.
FROM python:3.14-slim-trixie AS cloud-dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package app
COPY backend/app /app/backend/app
RUN rm -rf /app/backend/app/frontend
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package app

FROM python:3.14-slim-trixie AS cloud-run
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    SERVE_FRONTEND=false \
    APP_RUNTIME_ENV_FILE=/run/secrets/runtime.env
# Match PostgreSQL 18 for scheduled pg_dump exports. No server, compiler,
# Poppler, frontend, uv cache, or development dependencies in this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl --fail --silent --show-error \
       https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       --output /usr/share/keyrings/postgresql.asc \
    && echo 'deb [signed-by=/usr/share/keyrings/postgresql.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main' \
       > /etc/apt/sources.list.d/postgresql.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home app
COPY --from=cloud-dependencies /app/.venv /app/.venv
COPY --from=cloud-dependencies /app/backend/app /app/backend/app
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/scripts/start-cloud-run.sh /app/backend/scripts/start-cloud-run.sh
ARG BUILD_REVISION=development
ENV BUILD_REVISION=$BUILD_REVISION
WORKDIR /app/backend
USER 10001
EXPOSE 8080
CMD ["sh", "/app/backend/scripts/start-cloud-run.sh"]

# docker compose and an unqualified docker build retain the existing image.
FROM development AS default
