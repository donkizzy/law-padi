# 0001. Keep retrieval in PostgreSQL with pgvector

Status: accepted. The separate vector-store backend was removed from the code
on 16 November 2026 (commit `5568909`).

## Context

The first design kept PostgreSQL as the legal source of truth and used Qdrant
for retrieval, with one collection per release and aliases switched on
publication. The code carried both a Qdrant backend and a pgvector backend for a
time; only pgvector was deployed.

The corpus is small: each instrument contributes a few thousand retrieval
segments, and a release is published rarely and reviewed by hand. The hard
requirement is that readers never see a retrieval index that does not match the
published text.

## Decision

Store retrieval segments, embeddings, index builds and the active retrieval
target in the same PostgreSQL database as the canonical law, using `pgvector`
for dense search and PostgreSQL full-text search for lexical search
(`backend/app/ingestion/pgvector_repository.py`). Promote an index by updating
`ActiveRetrievalTarget` in the same transaction that publishes the release.

## Consequences

- Publication and rollback are single database transactions; there is no
  external alias to switch or reconcile.
- Every ranked segment can be joined back to its `ProvisionVersion` and
  `SourceDocument` in SQL, which the evidence boundary relies on
  ([0002](0002-evidence-boundary-and-server-citations.md)).
- One managed database serves the whole application, which suits free-tier
  hosting ([0005](0005-render-cloudflare-neon-hosting.md)).
- Dense search is an exact cosine scan scoped to one embedding run; there is no
  approximate index. That is accurate and fast enough at the current size, but
  an HNSW index will be needed if the corpus grows by an order of magnitude.
- Backups and restores must include the `vector` extension.
