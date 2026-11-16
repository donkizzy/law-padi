# Round 5 ingestion — NRS preflight and blocked checkpoint

Date: 4 November 2026 (Africa/Lagos). Current law: Nigeria Revenue Service (Establishment) Act 2025. **Offline evidence prepared; database staging stopped before any writes.** The other six laws have not been started. This is a new ingestion report, separate from the retained Round 5 discovery report.

## Runtime established read-only

The actual application is `law-padi-backend-1`, exposed locally on port8000, using `law-padi-db-1` through `db:5432/app` on the Compose network. PostgreSQL18.6 reports internal address172.19.0.3. The database and backend are healthy; Mailpit is running. No services were started, stopped or restarted.

The host `.env` resolves to `localhost:5432/app`, where connection as its configured role fails; a separate host PostgreSQL16 process exists. That host endpoint is not the chosen ingestion target. No credentials appear in this report or the preflight evidence.

Database revision and repository migration head are both `c9d0e1f2a3b4`. The inspected ingestion/review/retrieval model columns exist; vector0.8.6 and btree_gist1.8 are installed. No schema migration or test fixture was run. Runtime settings allow Constitution and Act ingestion, use local blob storage in the Docker volume at `/app/backend/storage/source-documents`, use pgvector with1024 dimensions, and configure the static-PDF malware scanner. This scanner setting is an observation, not an antivirus certification.

All seven supplied eligible hashes have **zero source records, zero upload records and zero source-linked runs**. The final read-only snapshot also finds no pending, leased or running ingestion tasks. Protected source/run contents were not queried. Published-member aggregate metadata was inspected only to establish preservation requirements.

Active enacted target:

- Release: `e152d7ab-6e98-44ae-aad4-8ee69e8f3b54`, version `composite-2026-10-23-constitution-acja-police`, status `production`.
- Manifest: `b6c2346af907b7bfd76568399b98742600600c419bcd52cced7eac4dc4737191`.
- Embedding run: `9d13854a-ca2b-4feb-a572-94cbb5b2448b`.
- Retrieval build: `5fcc6f1b-e880-4628-adf5-76280c34c418`;1024 dimensions;4715 stored segments/embeddings; status `promoted`.
- Profile: `36bfcf19-ca90-4e7f-8130-d635d179c2a1`; target lock version2.
- Membership: Constitution1811, ACJA1930, Police931 canonical release entries. Counts differ from retrieval segment counts by design; they are not interchangeable.

These target identities and membership counts were unchanged in the final read-only snapshot. No new release or proposed promotion exists.

## Actors and review gates

The only discovered eligible administrative actor is existing active superuser `admin@example.com`, ID `e4688cce-ea38-4543-858a-f4951c95d92a`. There are no active explicit role assignments. Existing superuser logic grants uploader, legal-reviewer and corpus-publisher capabilities. No actor was created, impersonated or recorded as a reviewer.

Source verification and candidate decisions are separate audited actions with optimistic versions/idempotency. Blocking issues prevent candidate approval. Publication checks uploader/publisher separation; using the same superuser would require the supported explicit audited override reason, which has not been requested or supplied. A real distinct publisher is another option for that later gate. No source verification, review decision, boundary confirmation or publication approval is inferred from this task's ingestion authorisation.

## NRS identity and prepared evidence

Original PDF, unchanged and not copied to satisfy a helper's folder layout:

`backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/NIGERIA_REVENUE_SERVICE_ESTABLISHMENT_ACT_2025_84bc74e1bf.pdf`

Recomputed8039130bytes,30pages, SHA256 `3d49f6bb28f76087416a5e2e3c146f37138887bf4c1fdb1eea7c78c086f75af4`. Official NRS-hosted Gazette No117,26June2025,Vol112,Act4; historical/as-enacted2025 semantics, not current consolidated law. Page5 visibly gives26June2025 commencement; page30 visibly gives typeset assent on that date. No signature authentication is claimed. Current-status research was not extended and notices were not finalised; the retained4November2026 bounded currency findings remain qualified.

The new evidence folder is `backend/storage/statute-review/ingestion-round5-2026-11-04-nrs-v1/`. It retains30 new complete Poppler page images, one for each original page; original native reading-order/layout and Vision evidence are hash-linked in the source manifest. No PDF download or fresh OCR was performed. The incorrect inherited Vision statement that the text layer is absent is explicitly flagged: this PDF has a defective embedded OCR layer.

The prepared import envelopes retain all1119 raw Vision lines, original page text, line order, confidence and original boxes. The only coordinate conversion is `(x,y,width,height)` to `(x0,y0,x+width,y+height)` in the same normalized bottom-left space. No word boxes, pixel dimensions, coordinate flips, OCR substitutions or legal-text cleanup were invented. Actual PDFKit raster dimensions were not retained by the original artifact; no alignment to the new Poppler rasters is claimed.

Proposed evidence/canonical page map:

| PDF pages | Proposed existing PageRole | Proposed canonical inclusion |
|---|---|---|
|1–2|front_matter (2 is blank)|Exclude; retain evidence|
|3–4|table_of_contents|Exclude; retain arrangement evidence|
|5–23|legal_body|Include after full review|
|24–28|schedule|Include principal schedules after full review|
|29–30|back_matter|Exclude certification, memorandum and assent from canonical text; retain evidence|

Within included pages, headers, marginal headings and printed page labels still require source-backed candidate boundary/revision review. No inclusion decisions have been applied.

An independent broad numeric-marker audit initially found44 body candidates with43 distinct labels. Its v1 result remains retained. Page18/A246's monetary amount was a false section5 hit; the v2 audit explicitly rejects that hit using the page image and retains43 principal markers/43 distinct labels. This did not interpolate a sequence. Every retained arrangement label has a corresponding observed body hit. Schedule scanning produced26 raw numeric candidates, **not accepted schedule nodes**; parsed node counts are unknown because no parser run was created.

Targeted visual inspection in this task covers pages5,18,20,30 only. It is not full-text acceptance or independent human/legal review. A concrete unresolved discrepancy: Vision writes U+20A9 (won sign) before5,000,000 in section32(2), whereas page18 prints the naira symbol. Raw OCR remains unchanged; any correction requires an audited, explicitly approved candidate revision. Marginal-heading contamination and other native/OCR disagreements remain open. The other26 images have been retained but not visually accepted. No source/candidate approval packet is ready to approve.

## Blockers before staging

1. **Existing unrestricted worker.** PID28103 inside the backend runs `python -m ingestion_worker.cli`, ID `ingestion-worker-backend-image`, with no task-type filter. `lease_next_task` claims eligible tasks across runs. The normal upload and review-import services commit queued stages before a scoped caller can claim them. Therefore a scoped `run_to_review` caller alone cannot guarantee that this worker will not advance NRS. Its outbox loop can also append to an existing event sink. No worker was changed and no job was enqueued.
2. **Importer cannot accept explicit roles.** `backend/scripts/stage_statute_review.py:118` uses exact case-sensitive `ENACTED by`. Raw NRS page5 reads `EnACted by`, so it never starts the body and would mark every page2–30 as a table of contents. Even a case-insensitive fix would still lump schedules and certification into legal_body. `PageSelectionItem` and `update_page_selection` update inclusion/reasons, not page roles. Rewriting raw OCR to trigger the heuristic would conceal evidence and is not acceptable.
3. **Parser runtime differs from workspace.** The container has `act-hierarchy-v2` (hash `26a9da48b1b488b594b119435c21b5a0883264f807ee5ea73c73b392f21cafc8`); the workspace has v3 (hash `e4ce0369db429f1836689b758948e31b6594f6bf0a8672e95439918b5f6a9a68`). Other nine inspected-file comparisons except this parser match. The retained diff shows materially different back-matter/schedule handling. A resumed run must name and validate its actual parser rather than assuming the workspace version is running. No implementation was synchronized or changed.

Workspace v3 also contains sequence-conditioned split-numeral joining; the normalizer contains adjacent digit-line joining. The raw NRS audit finds zero matches for either inspected pattern, but no normalized/parser result is asserted. These behaviours require continued audit after runtime selection and must not be used to force section counts. No numeral repair has been performed.

Required narrowly scoped permission before the affected operation can proceed: permit an implementation amendment to the importer so every page can supply an explicit validated existing PageRole and reason, preserving raw text and provisional review status; permit focused regression coverage without using application-database fixtures. The concrete v2 import proposal contains these roles and reasons, which the current importer ignores. Separately, obtain permission from the worker's owner to temporarily pause/resume that worker during scoped staging, or provide an already isolated supported execution environment. A durable queue-ownership/exclusion implementation would be another separately authorised code change. Runtime-parser selection/alignment must be explicit before staging. None of these changes has been made under the present no-code-change authorisation.

## Embedding readiness

Configured active profile is `bge-m3-constitution-source-edition-v1`, provider `huggingface_tei`, model `BAAI/bge-m3`, recorded revision `5617a9f61b028005a4858fdac845db406aefb181`,1024 dimensions,batch size16. Its feature-extraction endpoint overrides the global sentence-similarity endpoint. Profile configuration explicitly says `provider_revision_pinned:false`; the request does not send a revision. The adapter sends `truncate:true`; pooling, normalization and an exact token limit are not specified in the retained profile or request and are not verified. Revision/pooling compatibility remains a build gate, not an assumption.

No embedding requests, provider charges or reuse occurred. Canonical/retrieval segment workload is not yet measurable;43 section markers do not predict subsection/schedule segments. Existing4715 vectors are only potential reuse candidates once profile identities and retrieval-text hashes are checked. Billing remains authorised for ordinary compatible Hugging Face calls; another billing approval is unnecessary.

## Recovery and retained failures

A new600-permission consistent custom-format pg_dump archive is retained as `app-before-round5-nrs-v2.dump`:156938743bytes; SHA256 `196762f7fe2125fad9fab88e5faa33790707e8b56673909ac871e46268fb0727`. The archive listing is readable (552lines). No restore was tested and this is not a full blob-volume backup; existing source storage remains untouched. The first failed empty backup and failure metadata remain retained: the database container does not set POSTGRES_USER, so the empty-username attempt selected role root. The successful retry uses the Compose health-check's explicit postgres role.

On resume, repeat duplicate/worker/target checks and obtain a fresh pre-write backup if the state has changed. Keep source blobs, raw/revision artifacts and audited decisions immutable. A failed new run should remain retained and be cancelled/retried only through its own supported services. Do not delete a corpus or restore over this live database to undo draft ingestion. Before any later approved publication, retain a new exact base/rollback proposal. Rollback should promote the previous valid target through the normal audited publication transaction; this backup is disaster-recovery evidence and must first be validated in a separately confirmed isolated recovery environment before any restore is contemplated.

Read-only SELECT failures, the host endpoint mismatch, one automatic-review timeout followed by a successful narrow retry, the failed empty backup and an offline audit assertion are documented in the new attempt notes. They are not reported as ingestion successes.

## Stage status and next action

| Stage | Status |
|---|---|
|Prepared offline|Yes: identity, manifests, line envelope,30 page images, structural label evidence|
|Staged for review|No; zero new source/upload/run/artifact database IDs|
|Source/candidates explicitly approved|No|
|Materialised|No|
|Embedded/indexed|No|
|Release validated|No candidate release exists|
|Publication approved|No|
|Actually published and locally checked|No|
|Blocked/not verified|Worker isolation, explicit page-role import, runtime parser choice; full wording and all-page review outstanding|

No existing repository files, title catalogues, original PDFs or retained Round5 artifacts were edited. No commits, branches, worktrees, migrations, fixtures, resets, remote deployment or protected-source processing occurred. Do not begin JRB while NRS remains at this checkpoint. Resume from the new checkpoint after resolving the named permissions/blockers; later source/candidate approval and local publication approval remain distinct required gates.
