FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend:/app/services/ingestion-worker
ENV INGESTION_STORAGE_DIR=/app/backend/storage/source-documents

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY services/ingestion-worker/requirements.txt /tmp/ingestion-worker-requirements.txt

RUN pip install --no-cache-dir -r /tmp/ingestion-worker-requirements.txt

COPY backend/app /app/backend/app
COPY services/ingestion-worker /app/services/ingestion-worker

CMD ["python", "-m", "ingestion_worker.cli"]
