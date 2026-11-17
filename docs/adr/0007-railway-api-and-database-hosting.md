# 0007. Host the API, workers and database on Railway

Status: accepted on 17 November 2026; the move is prepared, not yet carried
out ([runbook](../runbooks/railway-migration.md)). Supersedes
[0005](0005-render-cloudflare-neon-hosting.md) for the API and the database.
The Cloudflare Worker and R2 parts of 0005 stand.

## Context

ADR 0005 put the API and an in-process chat worker on one Render free web
service and the database on Neon, to keep hosting free. That shaped the
system around free-plan limits:

- the service sleeps when idle, so the first request after a pause is slow,
  and the chat worker runs inside the API process only while requests wake it;
- there is no pre-deploy step or shell, so migrations and corpus copies run
  from an operator's machine before a push;
- the ingestion worker has no production home.

The owner has bought Railway Pro: $20 a month, which includes $20 of usage,
then billed by use. Spending that on always-on compute removes the limits
above, provided usage stays near the included credit.

## Decision

One Railway project, in one region (EU West, the closest to Nigerian readers),
with four services defined in `deployment/railway/railway.ts`:

- `api`: FastAPI under one Uvicorn process (`app.main:app`). It no longer runs
  a chat worker. `alembic upgrade head` is its pre-deploy command, so every
  deploy migrates once before the new version takes traffic, and Railway moves
  traffic only when `/readyz` passes.
- `chat-worker`: the standalone worker (`python -m app.chat.worker`), always
  on, as Compose already runs it.
- `ingestion-worker`: the `services/ingestion-worker` image, off between
  corpus runs and switched on for one.
- `postgres`: PostgreSQL 18 with pgvector, from the same `pgvector/pgvector`
  image as Compose and the restore checks, on a Railway volume. It serves the
  other services over the private network and operators through a TLS TCP
  proxy with a certificate generated for the volume.

The Cloudflare Worker remains the public site and the only route to the API,
which still rejects requests without the origin credential. R2 still stores
source PDFs and logical backups.

Railway's `railway.json`/`railway.toml` (Config as Code) stops being read on
1 December 2026, so the configuration uses its replacement, Infrastructure as
Code, applied with the Railway CLI.

## Consequences

- **Cost.** Measured idle memory puts the always-on stack at about $7 of usage
  a month and a busy month at about $14, inside the $20 credit; running
  ingestion on demand saves about $1 more
  ([estimate](../runbooks/railway-migration.md#cost-estimate)). Model and
  embedding spend is unchanged and bounded by the spend ledger
  ([0006](0006-reserve-then-settle-spend-ledger.md)).
- **No cold starts.** Answers start when they are asked, and the worker no
  longer depends on request wake-ups.
- **Migrations run with each deploy.** Operators no longer migrate by hand
  before pushing. Migrations must still be additive, and a column that new
  code reads must be migrated in an earlier deploy, because the workers deploy
  alongside the api rather than after its pre-deploy step.
- **Self-managed database.** Neon gave point-in-time restore and instant
  branches. Railway volume backups are daily and weekly snapshots, so the
  recovery point is up to a day old unless a logical dump is more recent; the
  nightly verified `pg_dump` to R2 stays the copy that survives losing the
  project. There is no point-in-time recovery unless WAL archiving is added.
  PostgreSQL upgrades, tuning and the TLS certificate are ours to manage.
- **Single region, single instance.** A volume allows one replica, and
  redeploying the database (only when its image changes) means a short outage.
  A Railway regional incident takes the API down; the Worker still serves the
  static site and cached public reads.
- **Exposure.** The API has a public `*.up.railway.app` domain, protected by
  the origin credential as on Render. The database's TCP proxy is public,
  protected by TLS and a 64-character password; it can be removed when not in
  use, at the cost of the nightly backup and corpus copies.
- **Edge headers.** Railway's edge may rewrite `X-Forwarded-For`, so the
  Worker sends the client address in its own header, which per-reader limits
  read first.
- **Health checks only gate deploys.** Railway does not restart on a failing
  check and cannot run a command check, so a watchdog in `run.sh` restarts a
  worker whose heartbeat goes stale.
- **Retired after cutover.** `render.yaml`, `deployment/render/` and the
  Render runtime (`backend/app/deployment/render_app.py`) remain until the
  rollback window ends, then are removed as the runbook lists.
