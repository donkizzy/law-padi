# Deployment

constitution.ng runs on one Render web service for the FastAPI API and
request-woken chat worker. A Cloudflare Worker serves frontend assets and public
HTML, caches eligible public reads, and proxies API requests and SSE streams.
Neon PostgreSQL stores the corpus, pgvector retrieval index, conversations and
spend ledger; private Cloudflare R2 stores source PDFs and database backups.

Follow the [Render deployment runbook](render/README.md) for service setup,
private configuration, release checks and recovery, and the
[Cloudflare runbook](cloudflare/README.md) for frontend and Worker releases.
[`render.yaml`](../render.yaml) defines the production service settings, including
AI budgets and query embeddings. Keep the frontend and API on matching source
revisions. The backup scripts under `render/` use a separate PostgreSQL 18 image;
the API image does not include database export tools.

A Cloud Run design was prepared but never deployed. Its code and original
runbook are preserved at tag `archive/pre-public-cleanup`.
