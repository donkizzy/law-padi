# Ingestion Runbooks (V1, dev mode)

## Source-verified formatting repair

Native PDF extraction now collects coordinate spans in PDF stream order and
reconstructs page text with pypdf's layout mode. Layout output is accepted only
when its complete non-whitespace character sequence matches plain extraction;
otherwise the plain text and a diagnostic are retained. Raw extraction artifacts
also retain `plain_text`. This repairs split glyphs and raised ordinal suffixes
without guessing missing letters or changing punctuation.

The versioned normalizer records the rules applied to each page. It preserves
hard hyphens at line breaks, subsection markers, and line boundaries. Spans can
be narrowed to a provision's exact character range while retaining their
original text, offsets, and enclosing bounding boxes. Repeated wording must have
unique parent context before it can be matched. Revision revalidation clears
coverage findings only on exact source-character agreement with coordinate
evidence; unrelated blockers remain open.

For a run already waiting for review, run the maintenance command from
`backend/`. Supply a local copy of its original PDF (its SHA-256 is checked), a
known superuser's email, and a report destination:

```bash
uv run python -m scripts.repair_extraction_formatting \
  --run-id RUN_UUID \
  --source-file /absolute/path/original.pdf \
  --reviewer-email REVIEWER_EMAIL \
  --report /absolute/path/formatting-preview.json
```

The default is a dry run. Inspect the JSON before rerunning with `--apply`.
`--repair-boundaries` restores schedule items swallowed by an unrecognized
source marker and creates their missing candidates; `--separate-appendices`
marks misattributed appendix candidates rejected while retaining the original
source, candidate text, issues, and decision history for separate ingestion.
The original PDF and raw candidates are never overwritten. Candidates with
existing revisions or decisions are skipped. New edits use the normal revision
service, optimistic versions, idempotency keys, before/after snapshots, diffs,
and recorded reasons. The command never approves or publishes candidates.

The Constitution parser handles wrapped schedule markers such as `(6.)` and
unnumbered Schedule 7 oaths. In the current source compilation, the appended
Fundamental Rights Rules begin partway through PDF page 172. That heading is an
explicit instrument boundary; its page and title are recorded in parser metadata.
The full original PDF is retained. Appended rules, orders, and their schedules
require a separate supported instrument parser and reviewed identity/date/status
metadata before ingestion; they must not be published as Constitution schedules.

Malformed punctuation and numbering already present in the source require source
review, not speculative normalization. Preserve those findings until a reviewer
has authoritative evidence for a correction. A whitespace revision does not
approve legal wording or establish the source's legal status.

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

## Local Compose review archive

The private R2 archive keeps the original review paths and links. Database dumps
stay in the local backup. Run these commands from `backend/` with the bucket's
R2 credentials configured in the repository-root `.env`.

```bash
uv run python -m scripts.migrate_local_documents \
  --manifest /path/to/archive.json fetch-archive-manifest SNAPSHOT_ID
uv run python -m scripts.migrate_local_documents \
  --manifest /path/to/archive.json lookup RELATIVE_REVIEW_PATH
uv run python -m scripts.migrate_local_documents \
  --manifest /path/to/archive.json restore /path/to/new-review-directory
```

To retrieve a single file, pass `--relative-path RELATIVE_REVIEW_PATH` to
`restore` and provide a new destination filename. Both restore modes check
file contents against the archive manifest.

## Rebuilding pgvector from PostgreSQL (source of truth)

PostgreSQL + pgvector is the only supported retrieval backend. Canonical law,
release membership, embeddings, validation and active-target publication stay in
one database, so publication needs no external index or alias switch. Historical
vector-index and collection metadata remain readable for publication evidence;
new ingestion runs create only pgvector builds.

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
