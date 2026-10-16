# Render Free beta

The selected beta uses Cloudflare Workers Static Assets for the browser app,
one Render Free web service for the API and request-woken chat worker, Neon Free
PostgreSQL 18, and the existing private R2 `lawpadi` bucket. The earlier GCP
provisioning path is paused; do not run its provision, secret, schedule or release
commands for this deployment.

## Account limits

Before creating the service, inspect the existing Render workspace's billing
and usage. Its other applications share the allowances. Keep this service on
**Free**, use the existing free workspace tier, and do not create a Render
database, paid worker, disk, cron service or preview environment. If an allowance
is exhausted, stop and report the limitation instead of upgrading a plan or
changing another app.

Render Free provides 750 shared running hours per workspace per calendar month.
Idle services sleep after 15 minutes and may need about a minute to wake.
Build minutes and bandwidth have separate workspace allowances; excess usage
can be billed when a payment method exists. Check the account's actual billing
controls before proceeding. Free services have ephemeral filesystems, no shell
or one-off jobs, and blocked SMTP ports 25/465/587. The beta's database and PDFs
therefore live outside Render. See [Render's free-service conditions](https://render.com/docs/free).

## Prepare the exact source version

The root `render.yaml` explicitly selects Free, Virginia, one Docker instance,
the repository-root build context, `/healthz`, deployment on commit and a 30-second
shutdown delay. Never omit `plan: free`: Render's default for a new Docker web
service is paid. Its field definitions are in the [Blueprint reference](https://render.com/docs/blueprint-spec).

The backend container starts exactly one ASGI process. Incoming authorized
conversation requests wake its awaited worker. PostgreSQL retains runs, leases,
events and spend reservations across restarts. `/healthz` checks the worker
without querying Neon. Do not add uptime requests that keep free services awake.

Run the relevant isolated backend regressions, proxy checks, frontend build and
Render image smoke tests first. Freeze the sources, then record:

```bash
python3 scripts/build_revision.py
.venv/bin/python deployment/render/prepare_env.py --revision YOUR_SOURCE_REVISION
.venv/bin/python deployment/render/snapshot.py plan
.venv/bin/python deployment/render/snapshot.py prepare --expected-revision YOUR_SOURCE_REVISION
```

Inspect the ignored `deployment/render/snapshot.report.json` path list and diff.
The snapshot overlays only allowlisted application/frontend/tests/deployment
files onto HEAD. It scans for configured secrets and excludes runtime dotenv
files, corpus dumps, reports, generated output and unrelated new documents.
`prepare` uses a temporary index and creates no commit or branch. Existing files
outside the allowlist remain as they were at HEAD. The user's real index,
working files, current branch and `master` remain untouched.

Only after the release operator confirms the frozen build may they run:

```bash
.venv/bin/python deployment/render/snapshot.py commit --expected-revision YOUR_SOURCE_REVISION
git push origin refs/heads/codex/render-free-beta:refs/heads/codex/render-free-beta
```

The commit command advances only that deployment branch and never pushes.
Its `[skip ci]` marker avoids unrelated template push workflows; use the already
completed deployment checks as the initial validation evidence. Never force-push
or change the user's checkout to deploy this snapshot.

## Private environment and database

`deployment/render.env` combines the private API/worker credentials with the
single-process settings and starts with generation disabled. It is ignored and
chmod 600; never commit, print, paste into chat, or pass its contents as command
arguments. Import it through Render's private environment editor. Every sensitive
Blueprint value uses `sync: false`, so no credential belongs in `render.yaml`.

Use the direct Neon URL for both ordinary and notification connections. The
verified Linux certificate path is
`/app/.venv/lib/python3.14/site-packages/certifi/cacert.pem`; retain
`sslmode=verify-full`. Verify this exact path exists in the final image. Never
replace certificate verification with `sslmode=require` or disable verification.

The initial Neon seed is complete: 1,811 published legal versions, 1,829 retrieval
segments/vectors, the preserved production pointer and one immutable source PDF.
`deployment/seed.report.json` records exact hashes, schema/extensions and a private
data-only export. Its bootstrap administrator is newly generated in
`deployment/bootstrap.env`; local accounts and conversations were not copied.
Do not rerun the seed against the populated database. Future migrations must be
run locally with deployment credentials before manually releasing a compatible
image; Render Free has no pre-deploy shell available for that operation.

The imported ledger carries **$3.249977** already spent in October 2026 and
**$0.069612** held across four unresolved reservations. All 1,212 reservation
identities are preserved, including the earlier seed history. Do not reset the ledger when switching hosts. New generation is bounded
by $0.12 per Lagos day, $4 per Lagos month and a $5 overall monthly AI limit.
Paid query embeddings remain disabled; keyword/topic retrieval continues to work.
Additional evaluation spending must be carried from its isolated ledger before
enabling production generation. Confirm prepaid funds, disabled auto-recharge,
current prices and one-call capacity without purchasing credits automatically.

## Create and verify the service

Connect the private `donkizzy/law-padi` repository and its `master` branch. Inspect
the creation preview and confirm one Free web service in Virginia with no other
new resources. Import the private environment and set Auto-Deploy to **On Commit**,
matching `autoDeployTrigger: commit` in `render.yaml`. This temporary mode was
approved while GitHub Actions is blocked by the account billing restriction.
Pushes to `master` trigger Render's Docker build without waiting for GitHub tests.
Run relevant tests locally before pushing. Once hosted CI works again, restore
**After CI Checks Pass** in Render and `autoDeployTrigger: checksPass` here.
Record the exact assigned HTTPS
`onrender.com` URL rather than guessing it from the service name.

The GitHub workflows are configured for backend types/lint, migrations and tests against a disposable
`app_test` database, deployment helper tests, frontend formatting/type checking
and build, Cloudflare proxy tests, a production Render image build, Docker Compose
smoke checks, and Playwright browser tests. Coverage is uploaded and enforces the
measured 88% application baseline rather than the template's unused 90% target.
The template FastAPI Cloud deploy and optional Smokeshow integration are disabled
unless explicitly enabled with repository variables. CI needs no production
database, AI or R2 credentials. The Render image computes its packaged source
revision at build time; the startup script uses that value even if an older
`BUILD_REVISION` environment setting remains in Render. Frontend publishing is a
separate Cloudflare release and must use the matching revision.

Verify `/healthz`, protected direct-origin access, exact section lookup,
keyword/topic search, guest cookies, history, replay and source downloads. Confirm
the returned API revision matches the frozen source and that idle database
listeners stop. After one real sleep/wake cycle, verify durable recovery and the
first request's behavior. Check Render memory/CPU and Neon connection usage.

The existing Cloudflare Worker is `constitition-ng`, with eventual address
`https://constitition-ng.amosgodwin500.workers.dev`. The saved Render
`FRONTEND_HOST` must match it. Follow the [Cloudflare runbook](../cloudflare/README.md)
for native GitHub builds and private staging before launch.

Set the Cloudflare Worker's `API_ORIGIN` to that exact HTTPS origin and use the
matching `ORIGIN_PROXY_SECRET`. Build the frontend with an empty `VITE_API_URL`
and the same revision. The edge forwards only the public `/api/v1/` namespace,
replaces trusted headers and preserves streamed responses. Publish static assets
and the Worker together only when their backend version is verified.

Public launch includes AI chat. Keep `CHAT_GENERATION_ENABLED=false`,
`CHAT_GENERATION_KILL_SWITCH=true` and capacity approval false until the current
prompt/build and lexical retrieval configuration pass the required 200-case
evaluation and human grounding review. Then explicitly update those three
controls together and verify a bounded live answer plus spend accounting.
An earlier incomplete collector or different build cannot open this gate.

Use HTTPS API email delivery or a supported alternate mail port before claiming
signup/recovery email works. The current SMTP defaults cannot send from Render
Free. Record any temporarily unavailable account flow honestly in release notes.

## Recovery and maintenance

Keep the verified corpus export and original PDF privately. Before migrations,
take a fresh full Neon dump with PostgreSQL 18, and test restoration into a
separate empty database. The Render path currently has no automatic export job;
the former GCS/Scheduler backup setup was not deployed. Do not rely on Render's
ephemeral disk or describe a local export as an automated backup.

If grounding, spending, worker recovery or origin protection fails, disable
generation and set its kill switch first, then manually roll Render back to the
previous verified commit and restore the matching Cloudflare version. Preserve
Neon, R2 sources and retained spend reservations. Inspect usage daily during the
first week; quota exhaustion should suspend or limit the beta instead of
silently selecting paid resources.
