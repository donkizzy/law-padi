# Deployment Docker images

Cloud Run uses `backend/Dockerfile --target cloud-run`. Build from the repository
root so the shared dependency lockfile and application sources are available:

```bash
docker build --platform linux/amd64 --target cloud-run \
  --build-arg BUILD_REVISION="$(python3 scripts/build_revision.py)" \
  -f backend/Dockerfile -t law-padi:cloud-run .
docker run --rm -i --platform linux/amd64 --entrypoint python \
  law-padi:cloud-run - cloud-run < scripts/smoke_docker_image.py
```

Use the existing [Cloud Run deployment runbook](../deployment/README.md) for
runtime settings, secrets, IAM and deployment. The optimization does not deploy
services or change their configuration.

## Image contents

| Build | Included runtime files and tools |
| --- | --- |
| `backend/Dockerfile --target cloud-run` | Python 3.14 slim, production dependencies, backend source/data/email templates, migrations, startup script, PostgreSQL 18 `pg_dump` and its shared libraries. Runs as UID 10001. |
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

Cloud Run's backup tool is installed in a separate build stage. Only `pg_dump`
and the transitive shared libraries reported by `ldd` are copied into the final
image; psql, other client programs, Perl and installation tooling stay behind.
Rebuild the image to pick up updates to those libraries.

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
| Cloud Run | 101.9 | 69.9 | 31% |
| Compose API + frontend | 533.6 | 68.6 | 87% |
| Render | 85.3 | 68.2 | 20% |
| Ingestion worker | 138.0 | 107.6 | 22% |

The Cloud Run Linux amd64 build is approximately **68.2 MB compressed**. The worker
comparison includes the Python 3.12 → 3.14 compatibility fix. Base image tags and
OS repositories can change, so future build sizes may differ.

The verified local amd64 image is tagged `law-padi:cloud-run-optimized` and embeds
its source revision. Python compiles imported modules at startup instead of
shipping cached bytecode.

## Verification

`scripts/smoke_docker_image.py` runs inside an image with dummy settings. It
checks real application imports, OpenAPI responses, email rendering, legal and
language JSON, migration discovery, frontend serving where applicable, and
absence of development tooling/bytecode. The ingestion mode renders a synthetic
PDF and runs Tesseract against the resulting PNG. The development mode checks
the FastAPI development CLI. Render CI also builds and smoke-tests Cloud Run.

For a backup integration check, pass `DOCKER_SMOKE_DATABASE_URL` to the smoke
container and attach it to a throwaway PostgreSQL network. The database name
must end in `_test`; the check exports a custom-format backup into temporary
container storage. Do not pass deployment credentials to a smoke test.

Native image verification additionally ran all migrations against a temporary
PostgreSQL 18/pgvector database, started both Cloud Run roles using their actual
entrypoint, checked API database readiness and task request validation, and
restored a `pg_dump` export to a second temporary database. No existing database
or local document storage is used by these checks.

The focused backend suite passed 35 tests with one host-only rendering test
skipped; rendering and OCR passed in the actual worker image. All 17 deployment
unit tests passed. Native runtime checks passed for Cloud Run, Render, Compose,
development and ingestion; the Cloud Run amd64 runtime check also passed.
The Playwright image built successfully and discovered 152 tests; the full
browser suite was not run for these packaging changes.
