# Backup and restore runbook

PostgreSQL holds everything that matters: published law, the retrieval index,
conversations, accounts and the spend ledger. R2 holds source PDFs only, so the
database needs its own backups. The API image contains no `pg_dump`; backups run
from separate scripts in `deployment/render/`.

## What the scripts do

- `backup-nightly.sh` reads an inventory of the database (schema revision,
  active release, version and vector counts, a hash over all canonical text
  hashes), runs `pg_dump` from a `postgres:18` container that is read-only,
  CPU- and memory-capped and size-limited, then reads the inventory again and
  fails if it changed during the dump. It uploads the dump to the private backup
  bucket, downloads it again, checks size and SHA-256 against a manifest, and
  publishes the manifest only after that check passes.
- `backup-restore.sh` downloads one named dump and its manifest, checks them,
  restores into a disposable `pgvector/pgvector` PostgreSQL 18 container with no
  network, and compares the restored inventory with the manifest.
- `backup_tools.py` holds the hashing, manifest and verification helpers; it
  never prints credentials. `backup-lifecycle.s3.json` is the bucket lifecycle
  policy.
- `backup-workflow.yml` is a GitHub Actions workflow (nightly backup and an
  on-demand restore check) intended for a separate private repository that
  holds the backup credentials. It is not in `.github/workflows/` here, so this
  repository does not run it; whether it is installed and scheduled elsewhere
  is not visible from this repository.

## Taking a backup before a risky change

Before migrations or a corpus release:

1. Create a Neon branch as a restore point in the Neon console.
2. Run the backup workflow manually (`operation: backup`) or take a
   `pg_dump --format=custom` with PostgreSQL 18 client tools into private
   storage.
3. Record the dump key or file name in the release notes for the change.

## Verifying a restore

Run the workflow with `operation: verify_restore` and the exact dump key, or run
`backup-restore.sh` with the same environment variables on a machine with
Docker. A backup that has not been restored at least once is not known to work.

## Restoring production

1. Prefer restoring the Neon branch taken before the change; it is the fastest
   path and keeps connection strings.
2. Otherwise restore a verified dump into a new, empty database with the
   `vector` and `btree_gist` extensions available, run
   `cd backend && uv run alembic upgrade head`, and check
   `SELECT extversion FROM pg_extension WHERE extname = 'vector'`.
3. Point the Render `DATABASE_URL` and `DATABASE_LISTENER_URL` at it and redeploy.
4. Do not reset the spend ledger: reservations and settled amounts carry the
   month's spend.

Never delete source objects in R2 to save space; canonical source PDFs have no
delete path by design ([`ingestion.md`](ingestion.md)).
