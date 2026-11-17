# Render runbook

Production runs on one Render free web service (API plus the in-process chat
worker), a Cloudflare Worker for the frontend and API proxy, Neon PostgreSQL 18
and private Cloudflare R2. Why this topology was chosen is in
[ADR 0005](../adr/0005-render-cloudflare-neon-hosting.md).

**`render.yaml` is the single source of production settings**: plan, region,
branch, deploy trigger, generation flags, model, languages, budgets, admission
limits, query embeddings and database timeouts. Read the values there; this
runbook does not repeat them, so it cannot drift from them.

## Service

- The image is built from `deployment/render/Dockerfile` with the repository
  root as context. It installs locked production dependencies, computes the
  source revision at build time and runs as an unprivileged user.
- `deployment/render/start.sh` starts exactly one Uvicorn worker for
  `app.deployment.render_app:app`. Incoming conversation requests wake the
  chat worker; runs, leases, events and spend reservations are durable in
  PostgreSQL, so sleeping or restarting loses no work.
- `/healthz` checks the worker without querying the database. Do not add
  uptime pings to keep the service awake.
- Keep `plan: free` explicit in `render.yaml`. Do not add a Render database,
  disk, paid worker, cron job or preview environment. Free services sleep after
  a period of inactivity and take time to wake, have an ephemeral filesystem and
  no shell, and cannot send mail over the standard SMTP ports; see
  [Render's free-service conditions](https://render.com/docs/free).

## Private configuration

Every credential in `render.yaml` uses `sync: false` and is set in Render's
environment editor, never in the file. `deployment/render/prepare_env.py`
combines private API and worker bundles into one ignored `deployment/render.env`
for import; never commit, print or paste that file.

- Use the direct Neon URL for both `DATABASE_URL` and `DATABASE_LISTENER_URL`
  (the listener holds a `LISTEN` connection for SSE). Keep
  `sslmode=verify-full` and point the root certificate at the `certifi` bundle
  inside the image; never weaken certificate verification.
- `ORIGIN_PROXY_SECRET` must match the Worker's secret. The API refuses to
  start without a secret of at least 32 characters and returns 403 to requests
  that do not carry it.
- `FRONTEND_HOST` must match the Worker's public origin (the Cloudflare build
  variable `PUBLIC_SITE_URL`).
- `R2_BUCKET_NAME` names the private source-document bucket.

## Hosting identifiers

Nothing that names the production deployment is tracked in the repository.
Each identifier is set where it is used:

| Identifier | Where it is set |
| --- | --- |
| Git repository Render deploys | Not in `render.yaml`: `repo` is omitted, so Render uses the repository that holds the Blueprint. |
| Public site origin | `PUBLIC_SITE_URL` (Cloudflare build variable) and `FRONTEND_HOST` (Render environment); keep them equal. |
| API origin the Worker proxies to | `API_ORIGIN` (Cloudflare build variable), a bare HTTPS `.onrender.com` origin. `prepare.py` rejects anything else. Details in [`deployment/cloudflare/README.md`](../../deployment/cloudflare/README.md#build-variables). |
| Source-document bucket | `R2_BUCKET_NAME` (Render environment). |
| Database host and backup bucket | `EXPECTED_NEON_HOST` ([`release.md`](release.md)) and `R2_BACKUP_BUCKET` ([`deployment/render/README.md`](../../deployment/render/README.md)), set privately. |

## Deploying

`render.yaml` deploys `master` once its GitHub checks pass
(`autoDeployTrigger: checksPass`). The full procedure, including migrations, which must run from an
operator machine because Render Free has no pre-deploy step, is in
[`release.md`](release.md). The frontend and Worker are released through
Cloudflare's native build ([`deployment/cloudflare/README.md`](../../deployment/cloudflare/README.md)).
Keep the frontend and API on the same source revision.

## Generation and spend controls

- `CHAT_GENERATION_KILL_SWITCH=true` stops new explanations immediately while
  lookup and reading continue. It is the first step in any incident involving
  answer quality or spend.
- Budgets and per-reader limits are enforced by the spend ledger and admission
  checks described in [ADR 0006](../adr/0006-reserve-then-settle-spend-ledger.md).
  Change them in `render.yaml`.
- Public generation is enabled under a recorded exception to the answer-quality
  gate; see [`evidence-chat-rollout.md`](../evidence-chat-rollout.md#launch-exception-recorded-16-november-2026).
- Do not reset the spend ledger when moving hosts or restoring. Spend from an
  isolated evaluation database can be carried in with
  `deployment/render/sync_spend.py`.
- The initial production seed is complete; new laws arrive through
  [`release.md`](release.md).

## Incidents

1. Set `CHAT_GENERATION_KILL_SWITCH=true` if grounding, spend, worker recovery or
   origin protection is in doubt.
2. Roll back the Render deploy to the previous good commit and restore the
   matching Cloudflare version.
3. Keep Neon, R2 sources and outstanding spend reservations intact. Restore data
   only through [`backup-restore.md`](backup-restore.md).
4. Check Render memory and CPU, and Neon connections and storage, after a sleep
   and wake cycle.

For self-hosted Compose, the backend and ingestion images run as UID 10001.
Before upgrading an existing installation, stop the application during a
maintenance window and change the existing `app-ingestion-source-documents`
volume ownership to UID and GID 10001 using an administrative container. A new
volume is initialized with the image directory's ownership. The default database
connection budget is 50; recalculate it before raising worker or pool settings.
