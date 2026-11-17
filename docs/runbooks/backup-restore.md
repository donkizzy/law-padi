# Backup and restore runbook

PostgreSQL holds everything that matters: published law, the retrieval index,
conversations, accounts and the spend ledger. R2 holds source PDFs only, so the
database needs its own backups. There are two:

- a nightly logical dump, verified and stored in R2 by the scripts in
  `deployment/backup/`. It is independent of the database host and is the copy
  that survives losing it;
- Railway volume backups of the `postgres` service: Daily (kept 6 days) and
  Weekly (kept 27 days), incremental snapshots of the running database, enabled
  in the service's Backups tab. Restoring one mounts a new volume in the same
  project and environment, so it does not protect against losing the project,
  and wiping the volume deletes them.

There is no point-in-time recovery: the newest restore point is the latest
dump or snapshot. The API image contains no `pg_dump`; dumps run from the
separate scripts.

## What the scripts do

- `backup-nightly.sh` connects through the database's TCP proxy with
  `sslmode=verify-full`, checking the server against `BACKUP_DATABASE_CA` (the
  pinned Railway certificate, see
  [`deployment/railway/README.md`](../../deployment/railway/README.md#tls-and-the-tcp-proxy))
  or, when that is empty, the runner's public CA bundle. It refuses any host
  other than `EXPECTED_DATABASE_HOST` and any database other than `app`, and
  reads in read-only transactions. It reads an inventory of the database (schema revision,
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
  holds the backup credentials: repository variables `R2_BACKUP_BUCKET`,
  `EXPECTED_DATABASE_HOST` and `BACKUP_DATABASE_CA`, and secrets
  `BACKUP_DATABASE_URL` and the three `R2_BACKUP_*` values. The Neon-era names
  `EXPECTED_NEON_HOST` and `NEON_BACKUP_DATABASE_URL` are still accepted until
  the Neon project is deleted. The workflow is not in `.github/workflows/`
  here, so this repository does not run it; whether it is installed and
  scheduled elsewhere is not visible from this repository.

## Taking a backup before a risky change

Before migrations or a corpus release:

1. Take a manual volume backup of `postgres` (Backups, Backup now). Manual
   backups are limited to half the volume's size.
2. Run the backup workflow manually (`operation: backup`) or take a
   `pg_dump --format=custom` with PostgreSQL 18 client tools into private
   storage.
3. Record the dump key or file name in the release notes for the change.

## Verifying a restore

Run the workflow with `operation: verify_restore` and the exact dump key, or run
`backup-restore.sh` with the same environment variables on a machine with
Docker. A backup that has not been restored at least once is not known to work.

## Restoring production

1. Set `CHAT_GENERATION_KILL_SWITCH=true` on `api` and `chat-worker`.
2. Prefer the volume backup taken before the change, if it is recent enough:
   in the `postgres` service's Backups tab choose it and Restore, review the
   staged change and deploy. Railway mounts a new volume made from the backup
   at the same path and keeps the old volume unmounted. The services keep their
   `DATABASE_URL`, so nothing else changes. The restored volume has a new, dated
   name: run `railway config plan --file deployment/railway/railway.ts` before
   the next `apply` and do not apply a plan that would move the mount back to
   the old volume; update `railway.ts` to the restored volume first.
3. Otherwise restore a verified dump: recreate the `app` database empty with
   the `vector` and `btree_gist` extensions, and run `pg_restore` through the
   TCP proxy, exactly as in steps 6 and 7 of
   [`railway-migration.md`](railway-migration.md). Redeploy `api`; its
   pre-deploy step migrates the restored schema to the build's head. Check
   `SELECT extversion FROM pg_extension WHERE extname = 'vector'`.
4. Do not reset the spend ledger: reservations and settled amounts carry the
   month's spend.
5. Turn the kill switch off once reads and `/readyz` are healthy.

Never delete source objects in R2 to save space; canonical source PDFs have no
delete path by design ([`ingestion.md`](ingestion.md)).
