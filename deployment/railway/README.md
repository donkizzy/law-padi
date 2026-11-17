# Railway deployment files

The API, the chat worker, the ingestion worker and PostgreSQL run in one
Railway project. The Cloudflare Worker stays the public site and `/api` proxy,
and R2 stays the store for source PDFs and backups. Why is in
[ADR 0007](../../docs/adr/0007-railway-api-and-database-hosting.md); the
one-time move from Render and Neon is
[`docs/runbooks/railway-migration.md`](../../docs/runbooks/railway-migration.md).

| File | Purpose |
| --- | --- |
| `railway.ts` | Infrastructure as Code: every service, its build, start, pre-deploy, health check, restart policy, watch paths, region and variables. |
| `package.json`, `bun.lock`, `tsconfig.json`, `env.d.ts` | Pin the `railway` SDK that `railway.ts` imports, and type-check it. Not part of the Bun workspace. |
| `run.sh` | Entry point inside the api and worker images: Uvicorn on `$PORT`, or a worker under a heartbeat watchdog. |
| `postgres/` | PostgreSQL 18 with pgvector (`pgvector/pgvector:0.8.6-pg18`, as in Compose) plus a TLS certificate generated for the volume. |

## Applying the configuration

Railway's `railway.json` and `railway.toml` files (Config as Code) are
deprecated and stop being read on 1 December 2026. Their replacement,
Infrastructure as Code, is a TypeScript file that the Railway CLI (5.42.1 or
later) plans and applies; Railway does not read it during deploys.

```sh
bun install --frozen-lockfile --cwd deployment/railway
bun run --cwd deployment/railway typecheck
export RAILWAY_GITHUB_REPO=<owner>/<repository>   # not tracked in the repository
railway link                                       # the project and the production environment
railway config plan --file deployment/railway/railway.ts
railway config apply --file deployment/railway/railway.ts
```

Read the plan before applying. Variables declared with `preserve()` or as
`${{shared.NAME}}` are never written by `apply`; they are the values set by
hand below. A change to a service's settings takes effect on its next deploy.

Settings that the file cannot express, and that are set once in the dashboard:

- **Public domain** for `api` (Settings, Networking, Generate Domain). It is a
  `*.up.railway.app` host; that origin is the Cloudflare `API_ORIGIN` build
  variable. No other service gets a public domain.
- **Volume backups** for `pgdata` (the `postgres` service, Backups): enable
  Daily and Weekly. See [backups](#backups).
- **Wait for CI** is set by `checkSuites: true` on every service; confirm the
  toggle shows as on in each service's settings. See [CI gating](#ci-gating).

## Services

| Service | Image | Start | Health | Restart | Region, replicas |
| --- | --- | --- | --- | --- | --- |
| `api` | `backend/Dockerfile` | `run.sh api`: one Uvicorn process on `$PORT` | `/readyz`, 120 s, deploy only | on failure, 10 retries | EU West, 1 |
| `chat-worker` | `backend/Dockerfile` | `run.sh worker … -- python -m app.chat.worker` | heartbeat watchdog | always | EU West, 1 |
| `ingestion-worker` | `services/ingestion-worker/Dockerfile` | `run.sh worker … -- python -m ingestion_worker.cli` | heartbeat watchdog | on failure, 10 retries | EU West, 1 when enabled |
| `postgres` | `postgres/Dockerfile` on volume `pgdata` at `/var/lib/postgresql` | image entrypoint with TLS | none (not HTTP) | always | EU West, 1 (a volume allows no more) |

**Migrations.** `alembic upgrade head` is the api's pre-deploy command. Railway
runs it once per deploy, in a separate container from the new image, on the
private network, before the new version starts. If it fails, the deploy stops
and the running version keeps serving. Workers never migrate, and their
deploys of the same commit start at the same time as the api's, not after its
pre-deploy step. Two rules from [`release.md`](../../docs/runbooks/release.md)
therefore still hold: migrations stay additive, because the old version serves
until the new one is healthy, and when new code reads a new column, the
migration is pushed and deployed in an earlier commit than that code.

**Health checks.** Railway calls the health check path only while a deploy
starts, to decide when traffic moves to the new version; it never restarts a
service because of it. That is a readiness decision, so the api uses `/readyz`
(the database answers and its schema is at this build's head), not `/livez`.
The reasons `/healthz` avoids the database on Render (a failing check restarts
the service, and a probe would wake a suspended Neon database) do not apply.
The check arrives with the Host `healthcheck.railway.app` and cannot send the
origin credential, so `PLATFORM_HEALTHCHECK_HOST` lets that Host read the three
probe paths, and nothing else, without it.

Railway has no command health checks and no continuous checks, so the
workers' heartbeat files (`app.core.heartbeat`) are checked by `run.sh`
instead: every 30 seconds after a start-up grace period it runs the same
command as the Compose health check, and when the heartbeat is stale it stops
the worker and exits non-zero, so the restart policy starts a fresh container.

| Worker | Heartbeat | Stale after | Stop signal, drain |
| --- | --- | --- | --- |
| `chat-worker` | every loop, 2 s polls × 30 | 60 s | `SIGINT` (cancels the asyncio runner so runs are requeued or settled), 30 s |
| `ingestion-worker` | every poll and stage checkpoint, 5 s × 180 | 15 min, the task lease | `SIGTERM` (the worker stops between pages and batches), 60 s |

Railway sends `SIGTERM` and, by default, `SIGKILL` at once; `drainingSeconds`
sets the grace period per service.

**Watch paths.** A push rebuilds only the services whose inputs changed:

- `api`: everything `scripts/build_revision.py` hashes, plus `run.sh`. The api
  image contains the built frontend and reports the packaged source revision,
  so a frontend change redeploys it and the revision it reports always matches
  the Worker built from the same commit.
- `chat-worker`: `backend/app/**`, the backend's Python dependencies,
  `backend/Dockerfile`, `.dockerignore` and `run.sh`. A frontend-only change
  leaves it running, so its `BUILD_REVISION` (used as the Sentry release) can
  lag the api's.
- `ingestion-worker`: `backend/app/**`, `services/ingestion-worker/**`,
  `.dockerignore` and `run.sh`.
- `postgres`: `deployment/railway/postgres/**` only. Redeploying a service
  with a volume stops it first, so the database restarts only when its own
  image changes.

**Ingestion on demand.** The ingestion worker polls the database every five
seconds. Railway's app sleeping puts a service to sleep only after 5 to 10
minutes without outbound traffic, and a database poll is outbound traffic, so
app sleeping would never apply. Corpus runs are occasional, so the worker is
off between them: `WORKER_ENABLED=false` makes `run.sh` exit 0 at once, and
the `ON_FAILURE` policy leaves it stopped, using no CPU or memory, even when a
push redeploys it. For a corpus run:

1. In the dashboard, set `WORKER_ENABLED=true` on `ingestion-worker` and deploy
   the staged change. Check its logs for `ingestion worker started`.
2. Run the corpus work through the admin workspace.
3. When the run's tasks are finished, set `WORKER_ENABLED=false` and deploy.
   Interrupted tasks are released by the worker or recovered from their lease.

`railway config apply` writes `WORKER_ENABLED=false`, so applying during a run
stops the worker; finish the run first. Admin uploads accept only the types in
`INGESTION_ALLOWED_INSTRUMENT_TYPES` (default `["constitution"]`); set it on
`api` and `ingestion-worker` before a run that adds Acts. There is no schedule.

## Variables

Values in `railway.ts` are written by `apply`. Railway references resolve when
a service deploys: `${{postgres.DATABASE_URL}}` (written in the file as
`postgres.env.DATABASE_URL`) is the database's private-network URL, and
`${{shared.NAME}}` is a project shared variable.

### Set by hand

Set these once, never in a file. Shared variables are under Project Settings,
Shared Variables; generate new values where marked rather than copying
anything into a terminal history.

| Variable | Where | Value |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | `postgres` service | New: `openssl rand -hex 32`. Hex keeps the URLs unescaped. |
| `SECRET_KEY` | shared | The current production value (signs sessions; a new value signs everyone out). |
| `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD` | shared | The current production values. |
| `ORIGIN_PROXY_SECRET` | shared | The current value, equal to the Worker secret of the same name (at least 32 characters). |
| `FRONTEND_HOST` | shared | The Worker's public origin, equal to Cloudflare's `PUBLIC_SITE_URL`. |
| `DEEPSEEK_API_KEY` | shared | The current provider key. |
| `HUGGINGFACE_API_TOKEN` | shared | The current token. |
| `R2_ENDPOINT_URL`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | shared | The current source-document bucket and its scoped key. |
| `SENTRY_DSN` | shared | Optional; reporting is off while it is empty. |

### Per service

`core` is the set every application process validates at start:
`PROJECT_NAME`, `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`,
`DATABASE_URL=${{postgres.DATABASE_URL}}`, the database connect, statement and
lock timeouts (15 s, 30 s, 5 s), `LOG_FORMAT=json`, `SENTRY_DSN` and
`SENTRY_ENVIRONMENT=production`. `generation` is the chat, budget, language,
provider and query-embedding block, with the values that ran on Render.

| Service | Variables |
| --- | --- |
| `postgres` | `POSTGRES_USER=postgres`, `POSTGRES_DB=app`, `POSTGRES_PASSWORD` (by hand), `PGDATA=/var/lib/postgresql/18/docker`, `DATABASE_URL` (private: `${{RAILWAY_PRIVATE_DOMAIN}}:5432`), `DATABASE_PUBLIC_URL` (TCP proxy, `sslmode=verify-full`). Railway provides `RAILWAY_PRIVATE_DOMAIN` and `RAILWAY_TCP_PROXY_DOMAIN`, which `start.sh` names in the certificate. |
| `api` | `core`, `generation`, R2 (`INGESTION_STORAGE_BACKEND=r2` and the four `R2_*`), `APP_RUNTIME_ROLE=api`, `SERVE_FRONTEND=false`, `ORIGIN_PROXY_SECRET`, `PLATFORM_HEALTHCHECK_HOST=healthcheck.railway.app`, `FRONTEND_HOST`, `DATABASE_POOL_SIZE=5`. Railway provides `PORT`. |
| `chat-worker` | `core`, `generation`, `CHAT_WORKER_HEARTBEAT_FILE=/tmp/chat-worker.heartbeat`, `WORKER_STOP_SIGNAL=INT`, `WORKER_STOP_TIMEOUT=25`, `DATABASE_POOL_SIZE=4`. |
| `ingestion-worker` | `core`, R2, `HUGGINGFACE_TEI_ENDPOINT_URL`, `HUGGINGFACE_API_TOKEN`, `WORKER_ENABLED=false`, `WORKER_STOP_TIMEOUT=55`, `INGESTION_WORKER_ID`, poll 5 s, lease 900 s, `INGESTION_WORKER_HEARTBEAT_FILE=/tmp/ingestion-worker.heartbeat`, `DATABASE_POOL_SIZE=5`. |

No service reads a secret file; `APP_RUNTIME_ENV_FILE` is unset, so settings
come from the environment only.

### What replaces each Render variable

| Render (`render.yaml`) | Railway |
| --- | --- |
| `DATABASE_URL` (direct Neon URL, `sslmode=verify-full`, certifi root) | `${{postgres.DATABASE_URL}}`, over the private network. Railway encrypts private-network traffic, and libpq's default `sslmode=prefer` still negotiates TLS with the server. |
| `DATABASE_LISTENER_URL` | Not set: the SSE listener falls back to `DATABASE_URL`, which is a direct connection (no pooler sits in between). |
| `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, `ORIGIN_PROXY_SECRET`, `DEEPSEEK_API_KEY`, `HUGGINGFACE_API_TOKEN`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `FRONTEND_HOST` (all `sync: false`) | The shared variables of the same names, referenced by each service that reads them. |
| `BUILD_REVISION` (`sync: false`, overridden by the image) | Not set: the backend image computes the source revision at build time and `run.sh` exports it. |
| `APP_RUNTIME_ROLE=api`, `SERVE_FRONTEND=false`, `PROJECT_NAME` | Same values on `api`. |
| `CHAT_*`, `DEEPSEEK_MODEL`, `CHAT_PROVIDER_CAPACITY_APPROVED`, `CHAT_DISPATCH_MODE`, budgets, `EMBEDDING_QUERY_ENABLED`, `HUGGINGFACE_TEI_ENDPOINT_URL` | Same values, in the `generation` block on `api` and `chat-worker`. |
| `CHAT_WORKER_CONCURRENCY=1` | Same, now read by the standalone `chat-worker`. |
| `DATABASE_POOL_SIZE=5` | `5` on `api`, `4` on `chat-worker`, `5` on `ingestion-worker`; see the budget below. |
| `DATABASE_CONNECT_TIMEOUT_SECONDS`, `DATABASE_STATEMENT_TIMEOUT_MS`, `DATABASE_LOCK_TIMEOUT_MS` | Same values on every service. |
| `INGESTION_STORAGE_BACKEND=r2` | Same, on `api` and `ingestion-worker`. |
| `healthCheckPath: /healthz` | `/readyz` with `PLATFORM_HEALTHCHECK_HOST`. |
| `autoDeployTrigger: checksPass` | `checkSuites: true` (Wait for CI). |
| `maxShutdownDelaySeconds: 30` | `drainingSeconds` per service (15, 30, 60, 60). |
| (none) | `PLATFORM_HEALTHCHECK_HOST`, `WORKER_*`, `CHAT_WORKER_HEARTBEAT_FILE`, `INGESTION_WORKER_*`, `LOG_FORMAT`. |

`deployment/render/prepare_env.py` combined private bundles into an import
file for Render. Railway needs no such file: each credential is entered once as
a shared variable, and a helper that read the bundles would put every secret
through one more file on disk.

## Connection budget

PostgreSQL keeps its default `max_connections` of 100, three of which are
reserved for superusers. The engine has `max_overflow=0`, so each process
opens at most `DATABASE_POOL_SIZE` connections, and the API also gates
concurrent requests at that size.

| Holder | Steady | During a deploy |
| --- | --- | --- |
| `api` pool, plus one `LISTEN` connection for SSE | 6 | 12 (old and new overlap for 10 s) |
| `chat-worker` pool | 4 | 8 |
| `ingestion-worker` pool (only during a corpus run) | 5 | 10 |
| `alembic upgrade head` (pre-deploy) | 0 | 1 |
| Backup (`pg_dump` and inventory `psql`), `publish_release.py`, operator `psql` | up to 6 | up to 6 |
| Reserved for superusers | 3 | 3 |
| **Total** | **24** | **40** |

That leaves more than half of the 100 free. Recalculate before raising a pool
size, `CHAT_WORKER_CONCURRENCY`, or the api's process count.

## TLS and the TCP proxy

Services reach the database at `postgres.railway.internal`. Operators, corpus
releases (`publish_release.py`) and the backup workflow use the TCP proxy
(`DATABASE_PUBLIC_URL`). `postgres/start.sh` generates a certificate for the
volume naming `localhost`, the private host and the proxy host, and keeps it
across deploys. To connect from outside:

1. Open a shell in the database container (`railway ssh --service postgres`,
   or the service's shell in the dashboard), print
   `/var/lib/postgresql/tls/server.crt` and save it locally as
   `railway-postgres.crt`.
2. Connect with the certificate pinned:

   ```sh
   psql "postgresql://postgres:<password>@<proxy host>:<proxy port>/app?sslmode=verify-full&sslrootcert=railway-postgres.crt"
   ```

The certificate is public; the password is not. If the TCP proxy is replaced,
`start.sh` issues a new certificate on the next start, and every pinned copy
(operators, the backup workflow's `BACKUP_DATABASE_CA`) must be refreshed.

## Backups

Two independent copies:

- **Logical dumps to R2.** The backup workflow
  ([`docs/runbooks/backup-restore.md`](../../docs/runbooks/backup-restore.md))
  takes a verified `pg_dump` through the TCP proxy every night and restores it
  on demand. This is the copy that survives losing the Railway project.
- **Railway volume backups.** Daily (kept 6 days) and Weekly (kept 27 days)
  schedules on `pgdata`. They are incremental, copy-on-write snapshots of a
  running database, so PostgreSQL recovers them as after a crash. Restoring
  mounts a new volume from the backup in the same project and environment.
  Wiping the volume deletes its backups.

## CI gating

`checkSuites: true` turns on Wait for CI for every service: Railway deploys a
pushed commit only after its GitHub Actions workflows finish, skips it as soon
as one fails, and skips it if they have not finished within two hours. It
looks at whole workflow runs, not individual jobs, and only at workflows that
run on `push` to `master`. See
[`docs/runbooks/branch-protection.md`](../../docs/runbooks/branch-protection.md#railway-deploys).
