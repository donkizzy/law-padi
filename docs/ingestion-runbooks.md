# Ingestion Runbooks (V1, dev mode)

## Upload quarantine and promotion

Upload completion is not source verification. The API only checks the
quarantine object's `HEAD` metadata and creates a queued run; it never parses,
hashes, or promotes the object. The worker then:

1. Streams the quarantine object to a bounded temporary file.
2. Verifies PDF magic bytes, SHA-256, size, encryption, readability, and the
   1,000-page limit.
3. Runs the configured malware scanner while the object is still quarantined.
4. Reuses an existing canonical source by SHA-256, or promotes the clean object
   to `sources/sha256/<sha>/original.pdf` and creates `SourceDocument`.

If verification or malware scanning fails, the upload is marked failed and no
canonical source row or canonical object is created. A worker restart is safe:
canonical promotion is content-addressed and duplicate hashes are reused.

## R2 lifecycle policy

Bucket: `${R2_BUCKET_NAME}`. Apply via Cloudflare dashboard or API
(`developers.cloudflare.com/r2/buckets/object-lifecycles/`).

- Retain indefinitely: `sources/sha256/*`, `runs/*/raw_extraction*`,
  `runs/*/normalized*`, `runs/*/revision*`, `runs/*/release-manifest*`,
  audit evidence blobs.
- Expire after 90 days: `runs/*/thumbnail*`, `runs/*/ocr-temp*`,
  `runs/*/page-render*`.
- The worker writes `retention_policy` (`retain_indefinitely` /
  `expire_after_90_days`) on every `IngestionArtifact`; the lifecycle rule
  keys off the same prefixes. There is intentionally no delete path for
  canonical source objects.

## Rebuilding pgvector from PostgreSQL (source of truth)

The V1 production backend is PostgreSQL + pgvector. Qdrant remains only as a
transition backend while retained releases are migrated.

1. Confirm the database has the `vector` extension and `RETRIEVAL_VECTOR_DIMENSIONS=1024`.
2. Pick the release's `RetrievalIndexBuild` and retained retrieval-document and
   embedding artifacts. Do not rebuild an approved or production release in place.
3. Recreate `RetrievalSegment` rows from `CorpusReleaseEntry` + `ProvisionVersion`,
   then insert one `RetrievalEmbedding` per segment for the selected run.
4. Run exact dense, lexical GIN, and hybrid RRF smoke queries. Validate row
   counts, hashes, dimensions, canonical joins, and the recall gate before marking
   the build `ready`.
5. Promote by updating `ActiveRetrievalTarget` in the same PostgreSQL transaction
   as release publication. Rollback is a transaction rollback or a later target
   promotion; no external alias operation is required.

Public retrieval must always reload `ProvisionVersion.text` and source provenance
after ranking. `RetrievalSegment.retrieval_text` is derived context, not legal truth.

## Rebuilding Qdrant from PostgreSQL (legacy transition only)

Qdrant is a derived index. On loss or drift:

1. Pick the production `CorpusRelease` and its ready `VectorIndex`
   (`index_kind`: `enacted` → alias `constitution_enacted`,
   `proposals` → alias `constitution_proposals`).
2. Re-export retrieval documents from `CorpusReleaseEntry` +
   `ProvisionVersion` (authoritative text always reloaded from PG).
3. Re-embed with the pinned `EmbeddingProfile.model_revision`, recompute
   `sparse_legal` vectors, rebuild immutable collections
   (`ng_constitution_{kind}_{version}_{profile}_{hash}`), validate
   counts/dimensions/checksums/sparse/smoke queries, then alias-swap.
4. Never mutate a `READY`/`PROMOTED` collection; a name collision with
   different release/profile IDs is a hard error.

## Outbox + SSE contract

- `workflow.append_run_event` writes `IngestionEvent` (monotonic `sequence`)
  plus a `transactional_outbox` row (idempotent key
  `ingestion-event:{run}:{sequence}`).
- `GET /admin/ingestion-runs/{id}/events` replays `sequence >
  Last-Event-ID`, emits keepalives, and remains open until the client
  disconnects. The frontend still has five-second polling as a fallback.
- `workflow.drain_outbox_batch` claims rows with `FOR UPDATE SKIP LOCKED` and
  marks them `published_at` only after the supplied publisher succeeds.
- The worker loop drains the outbox before task polling and fsyncs a durable
  JSONL event record before acknowledging the row. Production deployments may
  replace this configured sink with an event-bus relay using the same callback
  contract.
  Failures stay on the row (`attempt_count`, `error_message`) for retry.

## Backup, restore, and rollback

- Back up PostgreSQL with WAL/PITR enabled; the `vector` extension must be
  available before restoring the schema.
- Restore the database first, then run `alembic upgrade head` and verify
  `SELECT extversion FROM pg_extension WHERE extname = 'vector'`.
- Rebuild a failed pgvector build into a new release or embedding run. Never
  update segments or embeddings belonging to an approved/production release.
- Roll back retrieval by promoting the previous `ActiveRetrievalTarget` in a
  normal publication transaction. No external vector-service rollback is
  required.

## Deferred schema follow-ups (observability, not correctness)

- Add `updated_at` to `source_document`, `source_page`,
  `candidate_revision`, `review_issue`, `embedding_run` (mutations currently
  bump `lock_version` without a timestamp).
- Add unique `(release_id, profile_id)` on `embedding_run` (dedupe is
  currently application-level in `_embedding_run_for_profile`).
- Add `admin_role_assignment.revoked_by` (revocation currently stamps
  `revoked_at` only).
- Add `file_size > 0` check on `source_document` (legacy backfill used 0).
- `CandidateRevision` stores before/after snapshots, changed fields, and a
  unified text diff for audit readability.
