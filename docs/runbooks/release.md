# Release runbook

Two things are released separately: **code** (the API on Render and the frontend
and Worker on Cloudflare) and **corpus releases** (published law in the
production database). Corpus releases are built and reviewed locally
([`ingestion.md`](ingestion.md)) and copied to production with
`deployment/publish_release.py`.

## Code

`render.yaml` deploys `master` after GitHub checks pass. Cloudflare's native
GitHub build also builds `master` (`deployment/cloudflare/README.md`). There is
no staging environment in this release path.

Before pushing to `master`:

1. Run the checks that CI would run: `cd backend && uv run bash scripts/lint.sh`,
   `cd backend && uv run bash scripts/test.sh`, `bun run lint`, `bun run build`,
   and `uv run python -m unittest discover -s deployment/tests`.
2. If the change includes migrations, migrate the production database first
   (below). Render Free has no pre-deploy shell, so migrations run from an
   operator machine with the private deployment credentials.
3. Push, wait for both builds, and confirm that `/healthz` returns `ok` and that
   `GET /api/v1/deployment/runtime`, requested through the Worker, reports the
   expected `build_revision` and `prompt_version`. `python3 scripts/build_revision.py`
   prints the revision of the local sources.

Order matters when new code reads a new column: migrate first, then push.
Additive migrations are safe to apply before the code that uses them.

Rollback: redeploy the previous commit in Render and the previous version in
Cloudflare. Migrations can usually stay in place.

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

1. Take a restore point: a Neon branch and a fresh dump
   ([`backup-restore.md`](backup-restore.md)).
2. Migrate production to the code's Alembic head if needed and confirm with
   `SELECT version_num FROM alembic_version;`.
3. `copy` without `--apply`, inspect the report, then `copy --apply`.
4. Deploy the code that the release needs, if any, and wait for it.
5. `activate` without `--apply`, then `activate --apply`.

### Checks after release

- `/healthz` returns `ok` and `/api/v1/deployment/runtime` reports the expected
  revision.
- `GET /api/v1/legal/releases/current` shows the new release and
  `GET /api/v1/legal/instruments` lists the expected laws.
- Exact lookup and search return the expected sections for a few known queries,
  including one per newly added law.
- Edition notices appear on the new laws.
- A source PDF opens for one new law and for the Constitution.
- A request to the Render origin without the proxy secret returns 403.
- Render memory and Neon storage and connections are within plan limits.

### Rollback

| Failure | Action |
| --- | --- |
| `copy` fails | Nothing to undo; it runs in one transaction. |
| New code fails | Roll back the deploy in Render and Cloudflare. |
| New release is wrong | `activate` the previous release version. |
| Database damaged | Restore the Neon branch or the dump taken in step 1. |

For corpus copy, set `EXPECTED_NEON_HOST` in the private target env file to the
authorized database hostname and pass `--source-bucket` with the source R2 bucket.
