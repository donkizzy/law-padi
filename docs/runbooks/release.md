# Release runbook

Two things are released separately: **code** (the API and workers on Railway
and the frontend and Worker on Cloudflare) and **corpus releases** (published
law in the production database). Corpus releases are built and reviewed locally
([`ingestion.md`](ingestion.md)) and copied to production with
`deployment/publish_release.py`.

## Code

Each Railway service deploys a commit on `master` once its GitHub Actions
workflows pass (Wait for CI), and only when the commit changes that service's
inputs ([watch paths](../../deployment/railway/README.md#services)).
Cloudflare's native GitHub build also builds `master`
(`deployment/cloudflare/README.md`). There is no staging environment in this
release path.

Before pushing to `master`:

1. Run the checks that CI would run: `cd backend && uv run bash scripts/lint.sh`,
   `cd backend && uv run bash scripts/test.sh`, `bun run lint`, `bun run build`,
   and `uv run python -m unittest discover -s deployment/tests`.
2. Migrations run on their own: the `api` service's pre-deploy command is
   `alembic upgrade head`, run once per deploy before the new version takes
   traffic. A failed migration stops the deploy and the previous version keeps
   serving. Take a restore point first when a migration rewrites or drops data
   ([`backup-restore.md`](backup-restore.md)).
3. Push, wait for the Railway deploys and the Cloudflare build, and confirm
   that `GET /api/v1/conversations/capabilities`, requested through the Worker,
   reports the expected `build_revision` and `prompt_version`.
   `python3 scripts/build_revision.py` prints the revision of the local
   sources. A Railway deploy that went live has already passed `/readyz`.

Migrations must be additive, because the previous version serves until the new
one is ready. When new code reads a new column, push the migration in an
earlier commit and let the `api` deploy finish before pushing the code: the
workers deploy alongside the `api`, not after its pre-deploy step.

Rollback: redeploy the previous deployment of each affected service in Railway
(Deployments, Redeploy) and the previous version in Cloudflare. Migrations can
usually stay in place.

Until the cutover in [`railway-migration.md`](railway-migration.md), the API
still runs on Render: `render.yaml` deploys `master` after checks pass,
migrations are run from an operator machine before pushing, and
[`render.md`](render.md) applies.

## Corpus releases

`deployment/publish_release.py` has two commands. Each runs in one transaction
and rolls back unless `--apply` is given, so run every command once without it
first.

- `copy --release-version <version>` adds the release's laws, sources,
  provisions, versions, entries, segments and vectors to production. Rows that
  already exist must match exactly; nothing is updated or deleted. The release
  lands as `approved` with a `ready` index build, so readers keep the current
  release.
- `activate --release-version <version>` points the enacted search target at the
  copied release and retires the current one. Activating the previous release is
  the rollback.

Review evidence (ingestion runs, candidates, issues, accounts) stays in the
local database. The release must already be published locally, where the source,
review and composition gates passed.

### Procedure

1. Take a restore point: a manual Railway volume backup of `postgres` and a
   fresh dump ([`backup-restore.md`](backup-restore.md)).
2. Confirm production is at the code's Alembic head with
   `SELECT version_num FROM alembic_version;` (the `api` deploy migrates it).
3. `copy` without `--apply`, inspect the report, then `copy --apply`.
4. Deploy the code that the release needs, if any, and wait for it.
5. `activate` without `--apply`, then `activate --apply`.

### Checks after release

- `/api/v1/conversations/capabilities` reports the expected revision.
- `GET /api/v1/legal/releases/current` shows the new release and
  `GET /api/v1/legal/instruments` lists the expected laws.
- Exact lookup and search return the expected sections for a few known queries,
  including one per newly added law.
- Edition notices appear on the new laws.
- A source PDF opens for one new law and for the Constitution.
- A request to the Railway API origin without the proxy secret returns 403.
- Railway memory and volume usage, and `SELECT count(*) FROM pg_stat_activity`,
  are within the [budgets](../../deployment/railway/README.md#connection-budget).

### Rollback

| Failure | Action |
| --- | --- |
| `copy` fails | Nothing to undo; it runs in one transaction. |
| New code fails | Roll back the deploys in Railway and Cloudflare. |
| New release is wrong | `activate` the previous release version. |
| Database damaged | Restore the volume backup or the dump taken in step 1. |

For corpus copy, the private target env file (`--target-env`) holds
`DATABASE_URL`, the Railway `DATABASE_PUBLIC_URL` with
`sslrootcert=<path to railway-postgres.crt>` appended, and
`EXPECTED_DATABASE_HOST`, the TCP proxy host
([TLS](../../deployment/railway/README.md#tls-and-the-tcp-proxy)). The script
connects with `sslmode=verify-full` and refuses any other target. Pass
`--source-bucket` with the source R2 bucket.
