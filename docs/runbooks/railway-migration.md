# Railway migration runbook

Moves the API and the database from Render and Neon to one Railway project
([ADR 0007](../adr/0007-railway-api-and-database-hosting.md)). The Cloudflare
Worker stays the public site and `/api` proxy, and R2 stays the store for
source PDFs and backups. The services, variables and settings are described in
[`deployment/railway/README.md`](../../deployment/railway/README.md); read it
first.

**Status.** The move is complete and production runs on Railway. The Render
files were removed on 19 November 2026 (step 13, item 3), so steps that act on
Render are a record of the cutover and can no longer be repeated from this
repository.

Each step has a check and a rollback. Do not start a step until the previous
check passes. Commands that need a credential read it from the environment of
the shell running them, so it never appears in a command line, a file in the
repository or the shell history. Enter each with `read -rs NAME && export NAME`.

| Name | Holds |
| --- | --- |
| `NEON_DATABASE_URL` | The direct Neon URL of the `app` database (as in Render's `DATABASE_URL`). |
| `RAILWAY_DATABASE_URL` | `DATABASE_PUBLIC_URL` of the Railway `postgres` service, copied from its Variables tab, with `&sslrootcert=/run/railway-postgres.crt` appended. |

The commands use PostgreSQL 18 client tools from the `postgres:18` image, the
same major version as both servers. `CA` is a public CA bundle for Neon's
certificate: `CA=$(uv run --project backend python -m certifi)`.
`railway-postgres.crt` is the pinned Railway certificate from step 3.

## Before you start

- The code on `master` must include this migration's changes (the Worker
  accepting `*.up.railway.app`, the `X-Origin-Client-IP` header, the platform
  health check host, `run.sh` and the Railway images), deployed to Render and
  Cloudflare as usual. They change nothing on Render.
- Railway CLI 5.42.1 or later, logged in to the Pro workspace, and the Railway
  GitHub app allowed to read the repository.
- A verified backup from the last 24 hours
  ([`backup-restore.md`](backup-restore.md)), and its key noted.
- A Neon branch as a restore point, created in the Neon console.

## Downtime and the write freeze

Public reading (laws, provisions, search) never stops. Writes stop for the
**write freeze**: from step 8, when Neon becomes read-only, to step 10, when
the Worker sends traffic to Railway. During it, sign-in, sign-up, new
conversations and answers fail with an error, and the Render service keeps
serving reads from the read-only database. Explanations are switched off a few
minutes earlier so no answer is cut off.

The freeze lasts as long as one dump, one restore, the verification and the
Worker change. To keep it short:

- Rehearse steps 5 to 7 first, on the same data, while Render serves normally,
  and time them. The rehearsal also leaves a fully configured Railway stack
  that only needs fresh data at cutover.
- Restore with parallel jobs (`--jobs=4`). The retrieval index uses exact
  search with no approximate vector index, so the restore builds only B-tree,
  GIN and GiST indexes.
- Switch the Worker's origin with a runtime variable change, which takes
  effect at once, rather than waiting for a build.
- Choose a quiet hour; at the current size the freeze should be about 15 to
  30 minutes. Announce it if accounts are in use.

## 1. Create the project and services

1. Create an empty project named `constitution-ng` in the Pro workspace (the
   dashboard, or `railway init --name constitution-ng`), and link this checkout
   to it and its `production` environment with `railway link`.
2. Add the project shared variables listed under "Set by hand" in
   `deployment/railway/README.md`, with the current production values from
   Render's environment.
3. Apply the configuration:

   ```sh
   bun install --frozen-lockfile --cwd deployment/railway
   export RAILWAY_GITHUB_REPO=<owner>/<repository>
   railway config plan --file deployment/railway/railway.ts
   railway config apply --file deployment/railway/railway.ts
   ```

   Then set `POSTGRES_PASSWORD` on the new `postgres` service to a new value
   from `openssl rand -hex 32` and deploy it. Its first deploy fails without
   one: the image refuses to initialise a database with no password.

4. Before the first deploys go far, set `CHAT_GENERATION_KILL_SWITCH=true` on
   `api` and `chat-worker` in the dashboard. Until step 11 the Railway stack
   must not generate answers: a restored copy can contain pending runs, and
   answering them would spend against a ledger that is about to be replaced.
5. Generate a public domain for `api` (Settings, Networking). Record the
   `https://<name>.up.railway.app` origin for step 10.
6. Enable Daily and Weekly volume backups on the `postgres` service.

**Check.** `railway config plan` reports no changes. `postgres` is running and
its log shows `generated a TLS certificate` and `database system is ready`.
`ingestion-worker` shows `worker_disabled`. Until step 6 restores the data, the
database has no tables: `chat-worker` restarts with database errors and the
`api` deploy fails its health check. That is expected.

**Rollback.** Delete the Railway project. Nothing outside Railway has changed.

## 2. Enable pgvector

```sh
railway ssh --service postgres
psql -U postgres -d app -c 'CREATE EXTENSION IF NOT EXISTS vector' \
  -c 'CREATE EXTENSION IF NOT EXISTS btree_gist' \
  -c "SELECT extname, extversion FROM pg_extension ORDER BY 1"
```

(The service's shell in the dashboard works too.) The dump creates the same
extensions with `IF NOT EXISTS`; doing it first proves the image provides them.

**Check.** `vector` reports `0.8.6`, and `btree_gist` is listed.
**Rollback.** None needed.

## 3. Pin the database certificate

In the same shell, print `/var/lib/postgresql/tls/server.crt` and save it on
your machine as `railway-postgres.crt` (outside the repository). Then:

```sh
docker run --rm -e RAILWAY_DATABASE_URL \
  -v "$PWD/railway-postgres.crt:/run/railway-postgres.crt:ro" \
  postgres:18 sh -c 'psql "$RAILWAY_DATABASE_URL" -Atc "SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()"'
```

**Check.** It prints `t|TLSv1.3`. A connection without `sslrootcert`, or with
the wrong host, must fail certificate verification.
**Rollback.** None needed.

## 4. Freeze generation on Render (cutover only)

Skip this step in the rehearsal.

1. Set `CHAT_GENERATION_KILL_SWITCH=true` on Render and deploy.
2. Wait until no run is active:

   ```sql
   SELECT status, count(*) FROM generation_run
   WHERE status IN ('pending', 'running') GROUP BY status;
   ```

**Check.** The query returns no rows; readers see that explanations are
paused, and reading works.
**Rollback.** Set the kill switch back to `false` on Render.

## 5. Dump Neon

```sh
mkdir -p ~/constitution-migration && chmod 700 ~/constitution-migration
docker run --rm -e NEON_DATABASE_URL -v "$CA:/run/ca.crt:ro" \
  -v ~/constitution-migration:/dump postgres:18 sh -c '
    pg_dump "$NEON_DATABASE_URL" --format=custom --compress=gzip:6 \
      --no-owner --no-acl --lock-wait-timeout=30s --file=/dump/neon.dump' \
  && echo dumped
```

If `NEON_DATABASE_URL` does not already carry it, add
`sslmode=verify-full&sslrootcert=/run/ca.crt` to it. Keep the dump only in that
private directory, and delete it at the end of the rollback window.

**Check.** The command prints `dumped`. List what it will restore and confirm
that the only extensions are `btree_gist`, `uuid-ossp` and `vector` (plus
`plpgsql`):

```sh
docker run --rm -v ~/constitution-migration:/dump:ro postgres:18 \
  pg_restore --list /dump/neon.dump | grep -i extension
```

If Neon added another extension, write the list to a file, delete that line
and pass the file to `pg_restore` with `--use-list`.

**Rollback.** None needed; the dump reads only.

## 6. Restore into Railway

The target database must be empty. After the rehearsal, or a failed attempt,
recreate it first. This also closes the connections of the Railway services,
which reconnect on their own:

```sh
railway ssh --service postgres
psql -U postgres -d postgres -c 'DROP DATABASE IF EXISTS app WITH (FORCE)' \
  -c 'CREATE DATABASE app' && psql -U postgres -d app \
  -c 'CREATE EXTENSION vector' -c 'CREATE EXTENSION btree_gist'
```

Then restore:

```sh
docker run --rm -e RAILWAY_DATABASE_URL \
  -v "$PWD/railway-postgres.crt:/run/railway-postgres.crt:ro" \
  -v ~/constitution-migration:/dump:ro postgres:18 sh -c '
    pg_restore --dbname="$RAILWAY_DATABASE_URL" --no-owner --no-acl \
      --exit-on-error --jobs=4 /dump/neon.dump' && echo restored
```

**Check.** It prints `restored`, with no errors.
**Rollback.** Recreate the database as above and restore again.

## 7. Verify

Fingerprint both databases with
[`deployment/railway/verify.sql`](../../deployment/railway/verify.sql) and
compare:

```sh
docker run --rm -e NEON_DATABASE_URL -v "$CA:/run/ca.crt:ro" \
  -v "$PWD/deployment/railway/verify.sql:/verify.sql:ro" postgres:18 \
  sh -c 'psql "$NEON_DATABASE_URL" -X -A -t -q -v ON_ERROR_STOP=1 -f /verify.sql' > neon.txt
docker run --rm -e RAILWAY_DATABASE_URL \
  -v "$PWD/railway-postgres.crt:/run/railway-postgres.crt:ro" \
  -v "$PWD/deployment/railway/verify.sql:/verify.sql:ro" postgres:18 \
  sh -c 'psql "$RAILWAY_DATABASE_URL" -X -A -t -q -v ON_ERROR_STOP=1 -f /verify.sql' > railway.txt
diff neon.txt railway.txt && echo identical
```

It compares the Alembic revision, extensions, the exact row count of every
table, the embedding column type and stored dimensions (1,024), every index and
constraint, the active release, the canonical text and vector hashes, and the
month's spend ledger.

Then redeploy `api` (or wait for its retry): the pre-deploy step runs
`alembic upgrade head`, which does nothing when the dump is already at the
build's head, and the deploy goes live only when `/readyz` answers.

The first cutover is different: production is older than this build, so the
pre-deploy step applies the pending migrations (`alembic history -r
<neon revision>:head` lists them). Two of them stop rather than lose data, and
change nothing when they do:

- `a3c3553158d1` makes email addresses unique regardless of case. It stops if
  two accounts share an address that differs only in case, and prints how many.
  Find them with `SELECT lower(email) FROM "user" GROUP BY 1 HAVING count(*) > 1`,
  resolve each account, and redeploy.
- `d8e9f0a1b2c3` removes the unused remote-vector tables and columns. It stops
  if any history remains in `vector_index` or the promotion attempts'
  collection columns. Export those rows if you want them, then set
  `ALLOW_DROP_VECTOR_HISTORY=1` on `api` for one deploy and remove it after.

Run both checks against Neon before the freeze so neither can stop the cutover. Confirm it
from your machine with the origin credential in a file, never on the command
line:

```sh
printf 'x-origin-proxy-secret: %s\n' "$ORIGIN_PROXY_SECRET" > ~/constitution-migration/origin.header
curl -sS -H @"$HOME/constitution-migration/origin.header" https://<api>.up.railway.app/readyz
curl -sS -o /dev/null -w '%{http_code}\n' https://<api>.up.railway.app/readyz
curl -sS -H @"$HOME/constitution-migration/origin.header" \
  https://<api>.up.railway.app/api/v1/conversations/capabilities
```

**Check.** `diff` prints `identical`. The first `curl` returns
`{"status":"ok"}`; the second, without the credential, returns `403`; the third
reports the `build_revision` that `python3 scripts/build_revision.py` prints
for the deployed commit. In the rehearsal, record how long steps 5 to 7 took.

**Rollback.** Before step 8 nothing public has changed: fix and repeat step 6.

## 8. Freeze writes on Neon (cutover only)

In the rehearsal, stop here, and come back for the cutover from step 4.

At cutover, make Neon read-only first, then take the final dump:

```sql
-- On Neon, as the database owner.
ALTER DATABASE app SET default_transaction_read_only = on;
```

Restart the Render service so its connections pick the setting up. Then run
steps 5, 6 and 7 again on the frozen data.

**Check.** On Render, reading works and a sign-in attempt fails. The step 7
`diff` is `identical`.
**Rollback.** `ALTER DATABASE app RESET default_transaction_read_only;`, restart
Render and set its kill switch back to `false`.

## 9. Point backups at Railway

Update the private backup repository's workflow from
[`deployment/backup/backup-workflow.yml`](../../deployment/backup/backup-workflow.yml)
and its settings: variable `EXPECTED_DATABASE_HOST` (the TCP proxy host),
variable `BACKUP_DATABASE_CA` (the contents of `railway-postgres.crt`) and
secret `BACKUP_DATABASE_URL` (`DATABASE_PUBLIC_URL` of `postgres`, without the
`sslrootcert` parameter). Remove the old `NEON_*` names. Run it once with
`operation: backup`, then with `operation: verify_restore` on the new key.

**Check.** Both runs pass, and the manifest's inventory matches step 7.
**Rollback.** Restore the previous workflow settings; Neon is still intact.

## 10. Switch the Worker to Railway

1. In Cloudflare, set the build variable `API_ORIGIN` to the Railway origin
   from step 1.
2. In the Worker's settings, change its runtime variable `API_ORIGIN` to the
   same origin and deploy. It takes effect at once; the next build carries the
   same value from the build variable.

The Worker's `ORIGIN_PROXY_SECRET` does not change: Railway's shared
`ORIGIN_PROXY_SECRET` holds the same value.

**Check.** Through the public site, `GET /api/v1/legal/releases/current`
answers, and `GET /api/v1/conversations/capabilities` reports the expected
`build_revision`. In the Railway `api` logs, requests arrive with their
`request_id`.
**Rollback.** Set both `API_ORIGIN` values back to the Render origin. Render is
still serving reads; then follow the step 8 rollback to reopen writes on Neon.

The write freeze ends here.

## 11. Turn generation on and smoke test

Set `CHAT_GENERATION_KILL_SWITCH=false` on Railway `api` and `chat-worker`
(remove the dashboard overrides so `railway.ts` is the source again), and
confirm `railway config plan` shows no change. Then, through the public site:

1. **Login.** Sign in with an existing account and reload: the session
   survives (refresh cookie). Sign out.
2. **Search.** Search for "right to fair hearing" and open a provision; open
   one source PDF.
3. **Chat with SSE.** As a guest, ask "How long can police detain me?". Source
   cards arrive first, then the answer, with citations.
4. **Replay.** Ask another question and reload the page while it is being
   generated. The client reconnects with `Last-Event-ID` and the answer
   completes without repeating events. Or with `curl`, read
   `/api/v1/conversations/<id>/events?run_id=<run>` once to the end, note an
   event `id:`, and read it again with `-H 'Last-Event-ID: <id>'`: only later
   events come back.
5. **Admin.** As the superuser, open the admin workspace and the chat metrics
   (`/api/v1/conversations/metrics`).
6. **Limits.** Search once from two different networks (for example a phone
   on mobile data and a laptop). `SELECT key FROM rate_limit_counter WHERE key
   LIKE 'search-ip:%' ORDER BY window_start DESC LIMIT 5;` shows two keys, not
   one shared key for the address of Cloudflare's Worker.

**Check.** Every item works. In the Railway metrics, `api`, `chat-worker` and
`postgres` memory stay near the estimates below.
**Rollback.** Set the kill switch to `true` on Railway (answers stop, reading
continues) while investigating, or follow the step 10 rollback. Writes made on
Railway since step 10 are not on Neon: to keep them, dump Railway and restore
into a new Neon branch with steps 5 and 6 reversed before switching back. Never
reset the spend ledger.

## 12. Watch

For the first day, then daily during the rollback window:

- Railway logs for `api`, `chat-worker` and `postgres`: `unhandled_exception`,
  `worker_heartbeat_stale`, `worker_exited`, restarts, and Postgres `FATAL`.
- Sentry, if `SENTRY_DSN` is set: new issues under the release equal to the
  build revision.
- Railway usage (Workspace, Usage) against the estimate below, and the
  nightly backup workflow.
- `SELECT count(*) FROM pg_stat_activity;` stays well inside the connection
  budget.

## 13. Rollback window, then decommission

Keep Render and Neon for 14 days. Neon stays read-only; the Render service
stays deployed but receives no traffic. If a rollback is needed in that time,
follow the step 11 rollback.

After the window:

1. Take a final dump of Neon to R2 with the backup workflow's Neon settings, or
   keep the step 8 dump in private storage, and record its key.
2. Delete the Render service and the Neon project.
3. In a pull request:
   - remove `.onrender.com` from `API_HOST_SUFFIXES` in
     `deployment/cloudflare/worker.ts` and `prepare.py`, with their tests;
   - delete `render.yaml`, `deployment/render/` and
     `backend/app/deployment/render_app.py` with its tests;
   - remove the Render files from `scripts/build_revision.py`, `.dockerignore`
     and the api watch paths in `deployment/railway/railway.ts`;
   - replace the `production-container` job in `.github/workflows/render-ci.yml`
     with a build of the Railway images, and update the required checks in
     `branch-protection.md`;
   - delete `docs/runbooks/render.md`, mark ADR 0005 superseded in full, and
     remove the Neon fallbacks (`EXPECTED_NEON_HOST`,
     `NEON_BACKUP_DATABASE_URL`) from `deployment/backup/` and
     `deployment/publish_release.py`.

   Done on 19 November 2026, except the Neon fallbacks: remove them once the
   backup workflow's settings and the local release environment use only
   `EXPECTED_DATABASE_HOST` and `BACKUP_DATABASE_URL`. The Edge CI workflow
   now carries the `frontend-and-edge` job, and Railway CI already builds the
   Railway images.
4. Delete `~/constitution-migration`.

## Cost estimate

Railway Pro costs $20 a month and includes $20 of usage. Usage is billed per
minute at $20 per vCPU-month, $10 per GB-month of memory, $0.15 per GB-month of
volume (backups at the same rate on their incremental size) and $0.05 per GB
of public egress; private-network traffic is not billed.

Memory is measured: the production images were run locally against
PostgreSQL with `docker stats` after one minute idle (17 November 2026). The
database figure is an estimate: the local server holds many test databases,
and production holds published releases only. CPU is the idle share measured
for the application processes; answers spend most of their time waiting on the
model provider, and retrieval is a scan over one release's vectors in
PostgreSQL.

| Service | Memory, idle (measured) | Memory, busy (estimate) | CPU (estimate) | Monthly, idle | Monthly, busy |
| --- | --- | --- | --- | --- | --- |
| `api` | 137 MiB | 300 MiB | 0.01 vCPU | $1.55 | $3.10 |
| `chat-worker` | 98 MiB | 250 MiB | 0.01 vCPU | $1.15 | $2.65 |
| `postgres` | 250 MiB (estimate) | 500 MiB | 0.02 to 0.05 vCPU | $2.85 | $5.90 |
| `ingestion-worker`, always on | 94 MiB | 1 GiB during OCR | 0.005 vCPU idle | $1.00 | see below |
| Volume and backups | about 1.5 GB used at most, plus increments | | | $0.40 | $0.60 |
| Public egress | 5 to 10 GB | | | $0.25 | $0.50 |

- **Everything always on, including the ingestion worker:** about $7 a month
  idle and about $14 busy, inside the $20 credit.
- **Ingestion on demand (recommended):** the ingestion worker costs nothing
  while `WORKER_ENABLED=false`, saving about $1 a month; a corpus run at 1 GiB
  and one vCPU for ten hours adds about $0.40. Total about $6 idle, $13 busy.

The volume figure is an upper bound from the local database, which also holds
ingestion review evidence and every draft release. Check the real size before
cutover with `SELECT pg_size_pretty(pg_database_size('app'));` on Neon.
Usage beyond these figures most likely means a process holding memory (check
the service's memory graph) or unexpected egress; the model and embedding
spend is separate and bounded by the spend ledger.
