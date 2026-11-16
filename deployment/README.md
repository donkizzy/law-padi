# Deployment

constitution.ng runs on one Render web service for the FastAPI API and its
request-woken chat worker. A Cloudflare Worker serves the frontend and public
HTML, caches eligible public reads, and proxies API requests and SSE streams.
Neon PostgreSQL stores the corpus, the pgvector retrieval index, conversations
and the spend ledger; private Cloudflare R2 stores source PDFs and database
backups.

- [`render.yaml`](../render.yaml): the production service and all of its
  settings.
- [`docs/runbooks/render.md`](../docs/runbooks/render.md): operating the Render
  service.
- [`docs/runbooks/release.md`](../docs/runbooks/release.md): releasing code and
  corpus releases (`publish_release.py`).
- [`docs/runbooks/backup-restore.md`](../docs/runbooks/backup-restore.md):
  backups and restore checks (`render/backup-*.sh`).
- [`cloudflare/README.md`](cloudflare/README.md): building and deploying the
  Worker.
- [`docs/docker-images.md`](../docs/docker-images.md): what each image contains.

`seed_neon.py` performed the one-time initial seed of the production database
and must not be run again. A Cloud Run design was prepared but never deployed;
its code and runbook are preserved at git tag `archive/pre-public-cleanup`
([ADR 0005](../docs/adr/0005-render-cloudflare-neon-hosting.md)).
