# 0005. Host on Render, a Cloudflare Worker and Neon instead of Cloud Run

Status: accepted. `render.yaml` was added on 16 October 2026. The Cloud Run
code was removed on 16 November 2026; it is preserved at git tag
`archive/pre-public-cleanup`.

## Context

A Google Cloud design was prepared first: two request-billed Cloud Run services,
Cloud Tasks for dispatching generation, Cloud Scheduler and private Cloud
Storage backups, with Neon PostgreSQL and R2. The runbook at the tag records
that the Google Cloud account required an upfront payment, and that the design
was never deployed. The project's hosting target was to stay within free
allowances, with paid spend limited to model calls.

## Decision

- One Render free web service runs the API and the chat worker in a single
  process (`backend/app/deployment/render_app.py`). Requests wake the worker;
  runs, leases, events and spend reservations are durable in PostgreSQL, so a
  sleeping or restarted service loses no work.
- A Cloudflare Worker serves the frontend and public HTML, proxies the API with
  a shared secret, and caches public reads.
- Neon hosts PostgreSQL with pgvector; R2 stores source PDFs and backups.
- Production settings live in `render.yaml`.

## Consequences

- No hosting cost within the free allowances; model and embedding calls are
  bounded by the spend ledger ([0006](0006-reserve-then-settle-spend-ledger.md)).
- Free services sleep when idle, so the first request after a pause is slow.
- `render.yaml` allows one active generation at a time
  (`CHAT_MAX_ACTIVE_GENERATIONS=1`); while an answer is generating, the API
  refuses another reader's question with HTTP 429 rather than queueing it.
- Render Free has no shell or pre-deploy job, so migrations and release copies
  run from an operator machine ([runbooks/release.md](../runbooks/release.md)).
- The self-hosted Docker Compose stack remains for local development and browser
  tests.
