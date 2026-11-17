# syntax=docker/dockerfile:1
# No RUN --mount=type=cache: Railway rejects cache mounts whose id is not
# prefixed with the service's id.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.26@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b /uv /bin/uv
WORKDIR /app
RUN uv venv --no-project --python /usr/local/bin/python /app/.venv
COPY services/ingestion-worker/requirements.txt /tmp/requirements.txt
RUN uv pip install --no-cache --python /app/.venv/bin/python -r /tmp/requirements.txt

FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend:/app/services/ingestion-worker \
    INGESTION_STORAGE_DIR=/app/backend/storage/source-documents
WORKDIR /app
# psycopg[binary] carries libpq. Only PDF rendering and local OCR need OS tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --create-home app \
    && mkdir -p /app/backend/storage/source-documents \
    && chown -R 10001:10001 /app/backend/storage
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app /app/backend/app
COPY services/ingestion-worker/ingestion_worker /app/services/ingestion-worker/ingestion_worker
# Railway starts the worker through run.sh (deployment/railway/railway.ts).
COPY deployment/railway/run.sh /app/deployment/railway/run.sh
USER 10001
CMD ["python", "-m", "ingestion_worker.cli"]
