# Deployment Docker images

Railway builds `backend/Dockerfile` (default target) for the `api` and
`chat-worker` services, `services/ingestion-worker/Dockerfile` for the
ingestion worker and `deployment/railway/postgres/Dockerfile` for the
database. Build from the repository root so the shared dependency lockfile and
application sources are available:

```bash
docker build -f backend/Dockerfile -t constitution-ng-backend .
docker build -f services/ingestion-worker/Dockerfile -t constitution-ng-ingestion .
docker build -t constitution-ng-postgres deployment/railway/postgres
```

Runtime settings, secrets and deployment are in
[`deployment/railway/README.md`](../deployment/railway/README.md).
Building an image does not deploy a service.

## Image contents

| Build | Included runtime files and tools |
| --- | --- |
| `backend/Dockerfile` (default / `production`) | Same Python application dependencies, migrations, compiled frontend, `scripts/prestart.sh`, `deployment/railway/run.sh` and the computed source revision (`/app/source-revision`). Serves the API and frontend with Uvicorn on `$PORT` (default 8000). Also used by the standalone chat worker. |
| `backend/Dockerfile --target development` | Production image plus development dependencies, FastAPI CLI, uv, maintenance scripts and Poppler. Local Compose selects this target and tags it `backend:development` to avoid overwriting the production/chat-worker image. |
| `services/ingestion-worker/Dockerfile` | Python 3.14 slim, worker dependencies/source, backend source/data, `deployment/railway/run.sh`, Poppler and Tesseract. No frontend or FastAPI deployment CLI. |
| `deployment/railway/postgres/Dockerfile` | `pgvector/pgvector:0.8.6-pg18` plus a start script that generates a TLS certificate on the data volume. |

`frontend/Dockerfile.playwright` is a test-only image and retains its browser
tooling. It copies Bun directly from the Bun image and installs locked workspace
dependencies, without downloading a shell installer or adding unzip.

Build tools, package download caches, Python bytecode, development dependencies,
local documents/backups, IDE files, credentials, reports and unrelated docs do
not enter production images. The root `.dockerignore` allows only explicit build
inputs. Python source, legal JSON data, language glossaries, generated email HTML
and migration files remain available at runtime.

FastAPI's CLI/cloud deployment extras are now development dependencies. Fastar
(frontend serving) and Uvicorn remain explicit runtime dependencies. No existing
locked package version changed. The application is imported from `/app/backend`
via `PYTHONPATH`, so Alembic and direct maintenance commands can resolve it
without an editable install or a second copy of the source.

Database backups use the separate PostgreSQL 18 image invoked by
`deployment/backup/backup-nightly.sh`; the API image contains no `pg_dump`.

Neither Dockerfile uses `RUN --mount=type=cache`: Railway rejects a cache
mount whose id is not prefixed with one service's id, and `backend/Dockerfile`
builds two services. Docker's layer cache still reuses the dependency layers
while the lockfiles are unchanged.

The worker now matches the backend's Python 3.14 requirement. Its previous Python
3.12 runtime could not parse the shared backend's unparenthesized multiple
exception handlers. PDF rendering and local OCR remain in the worker.

## Measurements

Fresh before/after builds on 16 November 2026, using the same native Linux arm64
platform and application sources. Sizes are decimal MB of compressed image
content (`docker image inspect --format '{{.Size}}'` on the local containerd
image store), including a small amount of manifest metadata. Docker Desktop's
local disk usage also counts unpacked content and is larger.

| Deployment image | Before (MB) | After (MB) | Reduction |
| --- | ---: | ---: | ---: |
| Compose API + frontend | 533.6 | 68.6 | 87% |
| Render | 85.3 | 68.2 | 20% |
| Ingestion worker | 138.0 | 107.6 | 22% |

The worker comparison includes the Python 3.12 → 3.14 compatibility fix. Base
image tags and OS repositories can change, so future build sizes may differ.
Python compiles imported modules at startup instead of shipping cached bytecode.

## Verification

`scripts/smoke_docker_image.py` runs inside an image with dummy settings. It
checks real application imports, OpenAPI responses, email rendering, legal and
language JSON, migration discovery, frontend serving where applicable, and
absence of development tooling/bytecode. The ingestion mode renders a synthetic
PDF and runs Tesseract against the resulting PNG. The development mode checks
the FastAPI development CLI. Railway CI builds and smoke-tests the backend and
ingestion images.

Backup and restore verification run separately through the scripts under
`deployment/backup/`, using a PostgreSQL 18 container and private R2 storage.
