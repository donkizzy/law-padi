# syntax=docker/dockerfile:1
FROM python:3.14-slim-trixie AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv
WORKDIR /app
RUN uv venv --no-project --python /usr/local/bin/python /app/.venv
COPY services/ingestion-worker/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/.venv/bin/python -r /tmp/requirements.txt

FROM python:3.14-slim-trixie
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
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app /app/backend/app
COPY services/ingestion-worker/ingestion_worker /app/services/ingestion-worker/ingestion_worker
CMD ["python", "-m", "ingestion_worker.cli"]
