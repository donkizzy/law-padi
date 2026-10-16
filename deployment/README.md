# Free-tier deployment runbook

The user selected **Render Free** after GCP required an unaffordable upfront
payment. Follow [the active Render beta runbook](render/README.md). The GCP
procedure below is retained for a future migration and has not been deployed;
do not execute its resource or scheduling commands for the current beta.

This implements [the deployment plan](../docs/deployment-free-tier-plan.md):
Cloudflare Workers Static Assets, two request-billed Cloud Run services, Neon
PostgreSQL 18, private R2 sources, Cloud Tasks, and private GCS backups. There is
no always-running worker, Cloud SQL, load balancer, VPC connector or Cloud NAT.
The default Docker image and Compose workflow are preserved; Cloud Run explicitly
builds the `cloud-run` target.

The first stage is private and has generation disabled. Public release includes
AI chat, and requires the current prompt's completed 200-case live evaluation
and human grounding judgments. Earlier prompt evaluations cannot open this gate.
The ongoing hosting target is $0 within allowances, with a $5 monthly AI ceiling;
GCP and R2 remain metered services without an instantaneous account-wide $0 cap.

## 1. Account and spending setup

- Use the dedicated personal GCP project `secret-backbone-511708-j1`, displayed
  as `consituition-ng`. GCP project IDs cannot be renamed; use the assigned ID
  in config.
- Attach the user's selected billing account and confirm recurring free-tier
  eligibility. Trial credits alone are insufficient evidence.
- Configure low billing alerts, the supported Cloud Run spend-cap budget, and
  review its gross-cost threshold and delayed enforcement. Confirm free-tier
  usage from any other projects on the billing account counts toward allowances.
- Keep Cloudflare on Workers Free and Neon on Free. Use the free `workers.dev`
  hostname initially. Enable R2 only after verifying the card/billing conditions
  and free allowance. Disable provider auto-recharge and confirm prepaid funds
  within the agreed cash budget; these commands never purchase credits.
- Confirm one-call DeepSeek capacity and current maximum token prices. Initial
  paid query embeddings are disabled; evaluate the keyword/topic retrieval mode
  actually being deployed. Do not reuse semantic-mode judgments for a changed
  retrieval mode without validating that mode.

References: [GCP free-tier conditions](https://docs.cloud.google.com/free/docs/free-cloud-features),
[Cloud Run billing controls](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps),
[Workers Static Assets limits](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/),
[R2 limits](https://developers.cloudflare.com/r2/pricing/).

Install the Google Cloud CLI, Docker, Bun, and uv, and sign in interactively.
These scripts use the active personal CLI identity with explicit project flags;
they do not create service-account keys or change your active global project.
If adding CI later, use workload identity federation.

```bash
cp deployment/project.example.json deployment/project.json
cp deployment/api.env.example deployment/api.env
cp deployment/worker.env.example deployment/worker.env
chmod 600 deployment/api.env deployment/worker.env
```

Fill `project.json` with non-secret resource names and the final HTTPS browser
origin. Fill the two private dotenv bundles. API and worker share app signing and
database credentials; only the worker receives the DeepSeek key. The API receives
bucket-scoped R2 credentials for signed source links and the random
`ORIGIN_PROXY_SECRET` shared with the Cloudflare Worker. Configure free SMTP for
signup/password recovery, or keep those flows out of the beta until sending works.
Never source these dotenv files into a shell or copy their contents into a chat.

Set `spending_safeguards_confirmed` to `true` only after those controls are in
place. The script deliberately refuses cloud mutations while it is false.
This flag records an operator's verification; the provisioning command does
not create budgets. In Billing → Budgets & alerts, create an alerts budget
covering this project and a separate **Spend cap enforcement** budget scoped
to this project plus Cloud Run. Confirm its status is Configured. The cap uses
gross estimated costs before free-tier savings/credits, so a low cap may stop
the beta even while its net bill is zero. It does not cap registry, storage,
Tasks, Scheduler or Secret Manager costs, and delayed enforcement can overrun
the threshold. Record the selected amount and budget IDs privately before
confirming the flag.

```bash
python3 deployment/deploy.py validate
python3 deployment/deploy.py preflight
python3 deployment/deploy.py provision
python3 deployment/deploy.py upload-secrets --api-env deployment/api.env --worker-env deployment/worker.env
```

Provisioning creates four service identities, one Docker repository, one bounded
queue, two secret containers, and a private Standard GCS bucket in an eligible
US region. API/worker can enqueue to that queue and use its invoker identity;
only the worker can manage backup objects. Each runtime can access only its own
secret bundle. Secret uploads pin numbered versions in local config. Disable
superseded secret versions; two bundles with three enabled versions each use the
six-version allowance. Bucket soft delete is disabled so deleted exports do not
silently keep consuming storage.

## 2. Restore and verify the corpus

Create a Neon Free PostgreSQL **18** database in a region near Cloud Run, with
direct connection URLs in both secret bundles. Use SSL certificate verification.
The Cloud Run image's tested CA file is
`/app/.venv/lib/python3.14/site-packages/certifi/cacert.pem`; set that as
`sslrootcert` in both runtime URLs while retaining `sslmode=verify-full`.
The bundled PostgreSQL client's default system lookup failed certificate
verification in the deployment rehearsal. For local administration, supply the
local trusted CA file instead of the container path.
Install/verify `vector` and `btree_gist` before restoring.

For this authorized initial deployment, `deployment/seed_neon.py` pins the new
Neon host and database identity. Its preflight reads local `app` and the retained
validation spend ledger in read-only transactions and refuses a nonempty
destination. It applies migrations, transfers only the active published corpus
and existing vectors, clears nullable local reviewer/ingestion references, and
copies prior settled spend as detached audit records. The published release is
loaded as building inside a single private transaction, verified by hashes, then
returned to its original production status before commit; immutable retrieval
triggers remain enabled. It never copies local accounts or chat content.

```bash
.venv/bin/python deployment/seed_neon.py
.venv/bin/python deployment/seed_neon.py --apply --source-bucket lawpadi
```

The private `deployment/neon.env` supplies the destination URL. New random app
signing/bootstrap credentials are written once to chmod-600
`deployment/bootstrap.env`; reuse them consistently in both runtime bundles.
`deployment/seed.report.json` records exact counts/hashes, extensions, migration
head and the private data-only SQL.gz archive path. That archive excludes the
new administrator and must be restored only after applying the matching schema
to a separate empty database. The seed command deliberately refuses to overwrite
an already populated deployment. The initial October ledger carries $1.385829
already spent by the local validation environment, with no outstanding holds.

Take a fresh local `pg_dump` snapshot and record the current release, active
retrieval target, legal-text hashes, segment/vector counts and source hashes.
Restore into the empty Neon deployment using PostgreSQL 18 tools, with
`--no-owner --no-acl` as appropriate. Read the dump's schema version, then run only
remaining migrations using the deployment credentials. `prestart.sh` does not
populate the Constitution corpus. Do not invoke destructive test fixtures on
either the local published `app` database or the deployed database.

Copy the immutable original source PDFs from the local Docker volume into the
private R2 bucket, preserving every existing storage key. Compare each file's
SHA-256 with `source_document.sha256`, and confirm signed downloads return the
expected PDF. Updating storage environment variables alone transfers no files.
Verify the published identities, 1,811 legal-text hashes and 1,829 vectors against
the retained corpus evidence; preserve the historical/source-edition label and
the known missing Section 168/ambiguous Section 189 behavior.

## 3. Build, measure and stage privately

Choose a lowercase revision identifying the reviewed working-tree snapshot.
The repository currently contains product work outside these deployment files;
review the full intended version before publishing it.

```bash
python3 deployment/deploy.py build --revision YOUR_REVISION
python3 deployment/deploy.py push --revision YOUR_REVISION
python3 deployment/deploy.py stage --revision YOUR_REVISION
```

The build targets linux/amd64, Python 3.14 slim, production dependencies only,
one uvicorn process and a matching PostgreSQL 18 backup client. Poppler remains
in the development/ingestion image. Frontend output, local storage, test tooling
and secrets are omitted from the runtime. It runs as UID 10001.

`image.report.json` reports uncompressed bytes and a streamed gzip estimate.
The push command refuses an estimate above 240 MiB, and checks existing repository
bytes against 0.5 GiB before pushing. Check actual compressed registry storage
after the push, including other repositories on the billing account. Estimates
are not proof of free storage. Keep only needed release/rollback versions.

Both staged services require IAM invocation. The task service remains IAM-private
through public launch. It exposes `POST /internal/chat/run`,
`POST /internal/reconcile`, and `POST /internal/backup`; the Cloudflare proxy has
no route to these endpoints. The public API additionally checks an origin secret
on all requests, so its direct origin cannot bypass the edge's trusted IP boundary.

Initial limits are API min 0/max 2/concurrency 8/pool 5, worker min 0/max 1/
concurrency 1/pool 2, 512 MiB each, one vCPU, request CPU billing, no startup CPU
boost, and 300-second request/task deadlines. Queue dispatch concurrency is one,
with three bounded transport attempts. Duplicate/uncertain provider work is
handled by the application's leases and retained spend reservations; transport
retries do not authorize repeating an uncertain paid call.

The script sets generation/verification to $4 per Lagos month, total AI to $5,
and daily generation to $0.12. Guest/account daily limits are 3/10, burst limits
1/2, and only one active generation is admitted globally. Paid embeddings are
disabled. Lower limits as needed after measuring real usage.

Verify privately before opening the beta:

- Corpus lookup, source downloads, historical-edition labels, guest cookies and
  login/recovery after email configuration.
- Cloud Tasks OIDC and IAM identity; terminal duplicate delivery, lost enqueue,
  recovery, expired lease, interrupted worker, and uncertain provider dispatch.
- SSE starts immediately, heartbeat/disconnect, Last-Event-ID replay, and idle
  notification listeners stop so Neon can suspend.
- Budget exhaustion stops paid explanations without spending beyond retained
  reservations; browsing and keyword/topic retrieval still work.
- Measure cold starts, peak memory and direct PostgreSQL connection counts with
  real private requests before claiming 512 MiB is sufficient.

## 4. Backups and recovery

```bash
python3 deployment/deploy.py schedules
```

Exactly two Scheduler jobs use OIDC to invoke the IAM-private service: hourly
reconciliation and a 03:00 Africa/Lagos database export. They consume their own
runtime/database allowances. Backups use the worker's service identity, a private
GCS bucket, PostgreSQL 18 `pg_dump`, and seven-day retention. Run the backup once
privately, inspect the export, and restore it into a separate empty database.
Record successful restore evidence before launch. The restored test database
must never become a destructive fixture target unless its name ends `_test`.

## 5. Quality gate and public release

Follow [the existing evaluation workflow](../docs/evidence-chat-rollout.md) using
the current prompt and intended lexical retrieval configuration in an isolated
database. Include live evaluation in the $5 budget. Capture all 200 cases,
complete human grounding review, then pass the evaluator's perfect provenance/
citation checks, zero critical status errors, and at least 95% supported answers.

```bash
python3 deployment/deploy.py release --revision YOUR_REVISION \
  --captures backend/storage/evaluations/CURRENT_CAPTURES.jsonl \
  --judgments backend/storage/evaluations/CURRENT_JUDGMENTS.jsonl \
  --provider-capacity-confirmed
python3 deployment/deploy.py cloudflare --revision YOUR_REVISION
```

`release` first checks that every capture names the **current** prompt and lexical
retrieval mode, and that any known build revision matches the release, then runs the
existing evaluator against the explicitly configured evaluation database. Only
after it passes does the script enable generation on both services and add the
public API's `allUsers` invoker binding. The task service retains IAM checks.
The required provider flag records the operator's confirmation of prepaid funds,
disabled recharge, prices and one-call capacity; it does not obtain provider quota.

`cloudflare` builds with an empty `VITE_API_URL` and matching frontend revision,
then prepares ignored `deployment/wrangler.generated.json`. Upload the matching
Worker secret interactively (never print or pass its value in command arguments):

```bash
bunx wrangler@4.151.0 secret put ORIGIN_PROXY_SECRET --config deployment/wrangler.generated.json
python3 deployment/deploy.py cloudflare --revision YOUR_REVISION --publish
```

If Wrangler 4.151.0 is already installed locally, avoid another download by
setting `WRANGLER_CLI_JS` to its absolute `node_modules/wrangler/bin/wrangler.js`
path. The deploy script verifies its package name/version and invokes Node
directly. Node must be 22 or later; `WRANGLER_NODE` can select its executable.
For the interactive secret command, use `node "$WRANGLER_CLI_JS" secret put`
with the same arguments shown above. Never paste the secret into a command
argument or terminal transcript.

Use Workers Free, and confirm the secret before publishing browser traffic. The
Worker runs only for `/api/*`; deep links/static assets use the assets platform's
SPA handler. It fixes the destination to the configured HTTPS `run.app` origin,
allows only `/api/v1/`, overwrites the proxy credential/forwarding headers, passes
guest/account credentials, disables API caching, rewrites origin redirects, and
forwards the response stream without buffering SSE. See [asset routing](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/).

Smoke-test the final hostname: deep links, new/returning guest chat, history,
login, recovery email, exact/keyword search, a validated AI answer, source links,
refresh/replay, logout, quotas and exhaustion behavior. Confirm direct API calls
without the origin secret fail and unauthenticated private task calls fail.
Observe errors, memory, connection counts and costs for the first fifteen minutes.

## Rollback and operational review

Record the prior Cloud Run revisions/image digest and Cloudflare deployment ID
before each release. If grounding checks fail, paid calls escape admission, or
private endpoints become accessible, immediately set
`CHAT_GENERATION_KILL_SWITCH=true` and `CHAT_GENERATION_ENABLED=false` on **both**
Cloud Run services; pause task dispatch while investigating. Repoint API/handler
traffic to the last verified revisions and use Cloudflare's deployment rollback.
Review database migration compatibility before reverting application code. Do
not delete the database, source bucket or backups as part of a software rollback.

Check costs, provider reservations/invoices, Neon CU-hours, image storage, source
operations and backup retention daily during the first week. Avoid keep-alive
monitoring that wakes the database constantly. Reassess at 70–80% of any allowance
or when cold starts/busy responses harm the experience. Instance limits constrain
concurrency; they do not enforce a monthly hosting bill.

## Local checks

```bash
bun test deployment/cloudflare/worker.test.ts
python3 -m unittest discover -s deployment/tests -v
python3 deployment/deploy.py validate
sh -n backend/scripts/start-cloud-run.sh
```

Also run the relevant backend regression/lint checks on a dedicated `_test`
database and the frontend build. Cloud tests, restore evidence, current human
evaluation and exact registry bytes require real configured accounts and cannot
be replaced by static tests.
