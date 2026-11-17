# Deployment

The API, the chat worker, an on-demand ingestion worker and PostgreSQL 18 with
pgvector are moving from Render and Neon to one Railway project. A Cloudflare
Worker serves the frontend and public HTML, caches eligible public reads, and
proxies API requests and SSE streams. Private Cloudflare R2 stores source PDFs
and database backups.

- [`railway/`](railway/README.md): the Railway project as code
  (`railway.ts`), the service entry point, the Postgres image, the variables
  table and the connection budget.
- [`docs/runbooks/railway-migration.md`](../docs/runbooks/railway-migration.md):
  the move from Render and Neon, with the cost estimate.
- [`docs/runbooks/release.md`](../docs/runbooks/release.md): releasing code and
  corpus releases (`publish_release.py`).
- [`backup/`](backup/) and
  [`docs/runbooks/backup-restore.md`](../docs/runbooks/backup-restore.md):
  backups and restore checks.
- [`cloudflare/README.md`](cloudflare/README.md): building and deploying the
  Worker.
- [`docs/docker-images.md`](../docs/docker-images.md): what each image contains.
- [`render.yaml`](../render.yaml), [`render/`](render/README.md) and
  [`docs/runbooks/render.md`](../docs/runbooks/render.md): the Render service
  that serves until the migration's rollback window ends, then is removed.

The one-time initial seed of the production database was performed
and must not be run again. A Cloud Run design was prepared but never deployed;
its code and runbook are preserved at git tag `archive/pre-public-cleanup`
([ADR 0005](../docs/adr/0005-render-cloudflare-neon-hosting.md)).
