# Deployment Docker images

Render uses `deployment/render/Dockerfile`. Build from the repository root so
the shared dependency lockfile and application sources are available:

```bash
docker build --platform linux/amd64 \
  -f deployment/render/Dockerfile -t constitution-ng-api:render .
docker run --rm -i --platform linux/amd64 --entrypoint python \
  constitution-ng-api:render - render < scripts/smoke_docker_image.py
```

Use the [Render deployment runbook](../deployment/render/README.md) for runtime
settings, secrets and deployment. Building an image does not deploy a service.

## Image contents

| Build | Included runtime files and tools |
| --- | --- |
| `backend/Dockerfile` (default / `production`) | Same Python application dependencies, migrations, compiled frontend, and `scripts/prestart.sh`. Serves the API and frontend with Uvicorn. Also used by the standalone chat worker. |
| `backend/Dockerfile --target development` | Production image plus development dependencies, FastAPI CLI, uv, maintenance scripts and Poppler. Local Compose selects this target and tags it `backend:development` to avoid overwriting the production/chat-worker image. |
| `deployment/render/Dockerfile` | Python 3.14 slim, production dependencies, backend, migrations, Render startup script and computed source revision. Runs as UID 10001. |
| `services/ingestion-worker/Dockerfile` | Python 3.14 slim, worker dependencies/source, backend source/data, Poppler and Tesseract. No frontend or FastAPI deployment CLI. |

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
`deployment/render/backup-nightly.sh`; the API image contains no `pg_dump`.

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
the FastAPI development CLI. Render CI builds and smoke-tests the Render image.

Backup and restore verification run separately through the scripts under
`deployment/render/`, using a PostgreSQL 18 container and private R2 storage.
