# Round 5 ingestion — NRS staged; source/scope approval pending (v2)

4 November2026, Africa/Lagos. **NRS is staged privately for review. Source verification and all232 candidate approvals remain pending.** No canonical wording, embeddings, candidate release or publication was created. The other six laws remain unstarted.

This version corrects v1’s task-count typo: seven task rows were retained, not six. No source, approval or database state changed for this correction. The complete count evidence is `packet-integrity-and-counts-v1.json`; v1 remains retained.

This report continues [the read-only preflight](round5-ingestion-nrs-preflight-2026-11-04-v1.md). Earlier artifacts/checkpoints were retained without overwrite.

## Review packet and exact requested approval

Open the complete [source-and-scope review packet](../backend/storage/statute-review/ingestion-round5-2026-11-04-nrs-stage-v1/review-packet-source-and-scope-v1.html). It contains30 complete page images, separate native/Vision/normalized text, the fresh selected-page Vision alternatives, all232 raw candidates with IDs/versions,31 open database issues, source observations and13 unapplied fragment proposals. The [machine-readable action request](../backend/storage/statute-review/ingestion-round5-2026-11-04-nrs-stage-v1/approval-request-source-and-scope-v1.json) is the exact proposed action set.

Requested user approval is limited to:

1. Verify the identity/provenance of source `c62eed90-8334-4e8c-84aa-3a6a461dc79d` at expected version1, bound to SHA256 `3d49f6bb28f76087416a5e2e3c146f37138887bf4c1fdb1eea7c78c086f75af4`, as this official NRS-hosted Gazette No117,26June2025,Vol112,Act4, historical/as-enacted2025 edition.
2. Confirm page-level canonical scope for review run `0ad31203-e00b-4feb-9700-0a7769b09b36` at expected version7, every source page at expected version1: include PDF5–28 (principal body5–23, own schedules24–28); exclude PDF1–4 and29–30 from canonical content while retaining them as source evidence.

**No candidate wording approval, revision application, issue resolution, materialisation, embedding or publication is requested.** The packet does not claim full-text acceptance. Margins/headers and incorrect within-page spans still require reviewed candidate revisions. Page selection may add an excluded-page blocker to a candidate whose mapping includes29; that finding must remain open. Source verification cannot materialise these unapproved candidates. Application actions would use existing account `admin@example.com`, ID `e4688cce-ea38-4543-858a-f4951c95d92a`, with legal-reviewer authority through its existing superuser role. No independent human/legal reviewer is claimed or invented.

Packet HTML SHA256: `87e0cba88aeaf47622de736435e3444e83de1ab935269d5e1c03f02e52ec5a2d`. Action-request SHA256: `04ed136cbfeff83dbaa524a24bed4dd2284964b8bbde3909562ffdd96a3e1c11`. Import SHA256: `b0b5e6ff64411ae5aeb828de503b1f1a6d7e514378e3e3a448b3c62691e75c29`. Re-read these identities and optimistic versions before applying any approved actions. Material changes require a new approval scope.

## Authorised technical change and runtime isolation

The user's `yes` approved the scoped importer amendment, focused regression coverage, temporary worker pause/resume and workspace-parser alignment. It did not approve source verification or candidates.

Only `backend/scripts/stage_statute_review.py` and new `backend/tests/scripts/test_stage_statute_review.py` were changed/added as implementation. The importer now validates all explicit existing PageRole values and reasons before writes, rejects partial/invalid/duplicate proposals, preserves legacy payload behaviour and records provisional role provenance/importer version. It leaves source verification, candidate approval and embedding disabled. It does not rewrite OCR or turn inclusion proposals into reviewed decisions.

Five standalone unittest regressions pass with `Engine.connect` forbidden; pytest's destructive conftest was not loaded. Focused mypy passes with explicit package bases. Final Ruff lint/format and diff-whitespace checks pass. No database test fixtures, migrations, dependency changes, commits, branches or worktrees were used. Existing unrelated working-tree changes remain untouched.

Staging used disposable local Compose processes with read-only mounts for the existing workspace parser v3, approved importer and NRS catalogue/input/images. The running application image was not edited, rebuilt or restarted. Local target remained Compose `db:5432/app`, PostgreSQL18.6, schema `c9d0e1f2a3b4`; local blob volume `/app/backend/storage/source-documents`. The host PostgreSQL endpoint was not used.

The existing unrestricted worker PID28103, start ticks4334787, ID `ingestion-worker-backend-image`, was paused only at an observed idle boundary with a post-signal race check. Initial attempts left it running when it was busy. It was resumed in finally blocks after both attempts and subsequently observed in normal sleeping/running state. No protected run was opened, reset, restarted or claimed by this task. No general worker or outbox drain was invoked by this task.

## Retained failure and successful source admission

The initial admission passed SHA/size/page validation but the older container scanner rejected `automatic_action`. Read-only isolated inspection found the sole raw `/AA` prefix at byte offset1754323 followed byB5, inside compressed image object45 (`FlateDecode`/`DCTDecode`), rather than a complete PDF name. Strict pypdf inspection of156 indirect objects found no corresponding action dictionary/name. This is not an antivirus certification.

The repository already contained a whole-name boundary fix in `app/ingestion/malware.py`; the running image did not. **No scanner code was changed, gate disabled or per-source exemption added.** Existing scanner rejection and name-boundary tests passed when directly invoked without pytest fixtures. The same NRS upload/run was resumed through the normal configured scanner with that unchanged repository module mounted read-only. It passed the normal gate. Executed scanner SHA256: `2c1f5b025c781f51f02cb42ed4f2f624a0ad876058e4ec296712678872b359d2`; older runtime SHA256: `2e8b78e90c73444ce2e7a05f0747815144d1002f88baff596beca6398804dc73`. The unchanged scanner version label is insufficient by itself to distinguish these implementations; hashes are retained.

The first failure handler committed NRS-run cancellation but then hit a detached-actor error while recording idempotency. Its error and cancelled state were retained and verified. Resumption reloaded the real actor in the active session and used existing audited services. No unrelated cleanup occurred. The original rejected task remains cancelled with its error; the later successful scan is a separate task. The admission run was finally cancelled/retained at profiling so its native/cloud OCR stages cannot run. The separate OCR review run has no live task after its three scoped review stages.

## Source, run and artifact identities

| Record | Identity/state |
|---|---|
|Instrument|`cb65ec2d-89ac-4d0a-9f32-285eb7b1c08f`|
|Upload|`119dd665-231a-49b1-addd-f5b72fc838ed`; same upload reused, completed|
|Admission run|`72ac777a-0e22-4c17-8b67-3e207f656ff1`; retained/cancelled after admission|
|Source document|`c62eed90-8334-4e8c-84aa-3a6a461dc79d`; `needs_review`, version1|
|OCR review run|`0ad31203-e00b-4feb-9700-0a7769b09b36`; `waiting_for_review`, stage `review`, version7|
|Parser|`act-hierarchy-v3`; source file mounted read-only|
|Importer|`statute-review-import-v2-explicit-roles`|
|Normalizer|`legal-page-normalizer-v3`|
|Raw OCR provider label|`retained-round5-apple-vision-accurate-lines`; original line evidence retained|
|Source identity|8039130bytes;30pages; SHA256 `3d49f6bb28f76087416a5e2e3c146f37138887bf4c1fdb1eea7c78c086f75af4`|

Every original page is retained once in the source-review image/page manifest. Physical canonical PDF storage was created through the supported upload promotion; the original PDF was not moved or overwritten. Its stored-blob SHA was recomputed and matches the original. SourceDocument parser/extraction metadata remains unset where the standard importer does not populate it; run/candidate/artifact versions are retained explicitly instead of inventing source metadata.

The full ID inventory is in `staged-review-snapshot-v2.json` plus `database-record-inventory-and-final-guards-v1.json`: source/upload/instrument,2runs,30pages,232candidates,31issues,62artifacts (original plus30raw/30thumbnail/1normalized),7tasks,38steps,18ingestion events/outbox records and4idempotency records. No ReviewDecisionRecord or CandidateRevision was created. All known created/transitioned IDs are listed in those retained snapshots; no release ID was created. Earlier snapshot v1 had an expired-object serialization omission; v2 is the complete fresh read-only snapshot, and v1 remains retained.

## Extraction and review findings

All30 page images have now been inspected across the task, including every principal section opening. This is assistant evidence review, not independent human/legal review or a claim that every character is correct. Original native layout/reading-order extraction, original Vision, normalization, new Vision alternatives and unfiltered raw differences are retained separately. No PDF was downloaded or modified.

Observed raw structural counts:43principal sections,6parts,3schedules,72subsections,83paragraphs,25schedule-item candidates. Images independently show17first-schedule items,5second-schedule items and2form paragraphs:24true numbered schedule items. The extra `54e22e75-5a38-4394-a63a-5cd5becab8de` is a false item20 from two year blanks and extends into29. Complete title/section counts do not establish text acceptance.

All232 candidates remain `needs_review`, revision1; paths are unique and all parent IDs exist. There are31open database issues,19blocking:7punctuation,10span coverage,1arrangement reconciliation and1provisional-boundary blocker;12low-confidence findings are nonblocking. File-based visual findings add unresolved issues without manufacturing database review decisions. No existing blocker was resolved or waived.

Key unresolved findings:

- Arrangement1/8 are split in original Vision; parser also misreads a header2025 as an arrangement entry. A separate3600×5000 Vision pass reads1/8 normally, but original raw lines remain unchanged.
- Sections4,11,41 lose closing parentheses; section4 paragraph(l) is read as numeral1 in original OCR, harming child boundaries. The letter proposal is independently supported by image/new OCR, not inferred from a sequence. The source itself has section11 paragraph(j); no(i) is supplied.
- Marginal headings, running headers and printed page labels enter provisions/cross-page continuations. Span precision findings and precise page mappings remain unresolved.
- Currency/spacing/punctuation differences are retained, including U+20A9 versus naira in32(2), source spacing and missing periods. Thirteen concrete fragment proposals are unapplied. They are not complete approved candidate revisions.
- First Schedule internal headings are appended to preceding item text and need a faithful reviewed representation.
- Third Schedule blank leaders, naira/kobo labels and paired signature/date layout remain defective even in the fresh Vision alternative. No blank amount, date or missing punctuation was filled by an LLM.
- Faithful source grammar variants and negatives/provisos are logged rather than silently corrected.

Actual normalization changed only spaces before punctuation on16pages; every page's complete non-whitespace character sequence is unchanged. The digit-line joining rules did not fire. The parser preview/run did not emit a sequence-repair finding. Full raw disagreement/diff evidence and all rejected attempts are retained. Normalizer/parser heuristics remain subject to review if another artifact is proposed.

Line boxes remain original normalized bottom-left image coordinates. No word-level coordinates, actual PDFKit pixel dimensions, or coordinate overlays against the separate Poppler images were fabricated. Original line text/boxes remain available; derived spans may still enclose the original whole line.

A fresh offline Apple Vision detail pass covered3,6,11,21,28 with accurate recognition, correction disabled and no custom words. Its initial sandboxed attempt failed before producing output (exit133, nilError); the authorised host-access retry succeeded. Both attempt metadata/logs remain. Raw new OCR SHA256 is `3864d8519226c3ec1d037c53cebfe45fed01a3e198026708aff43e71d02f1536`.

## Recovery, published preservation and remaining gates

Two new consistent local pg_dump archives were retained for the attempts, both mode600 and with readable archive listings. Latest backup: `app-before-nrs-staging-v2.dump`, 170368686bytes, SHA256 `bcfa3da93eb673ebf3a5110a5f5cfdd24ff83168e15ed6918922c3aaa4aedd5f`. No restore was tested or performed. These are database backups, not full blob-volume backups. Recovery remains run-scoped cancellation/retry while preserving evidence; never reset a corpus or restore over the active application merely to undo draft ingestion.

Active release remains `e152d7ab-6e98-44ae-aad4-8ee69e8f3b54`, target lock2, manifest `b6c2346af907b7bfd76568399b98742600600c419bcd52cced7eac4dc4737191`, build `5fcc6f1b-e880-4628-adf5-76280c34c418`, embedding run `9d13854a-ca2b-4feb-a572-94cbb5b2448b`, profile `36bfcf19-ca90-4e7f-8130-d635d179c2a1`. Published entry counts remain Constitution1811,ACJA1930,Police931. No canonical NRS provisions exist; public Browse/lookup/retrieval publication checks are not yet applicable or claimed successful. Conversation release pointers were not changed.

No NRS embedding/provider request, embedding reuse or retrieval build occurred. Workload/cost cannot be estimated from43section labels alone. Hugging Face billing remains authorised; the earlier profile/revision/pooling/truncation-compatibility limitations remain build gates, not reasons to request billing approval again.

| Stage | Result |
|---|---|
|Prepared offline|Yes; complete30-page evidence, raw/normalized/alternative OCR and findings|
|Staged for review|Yes;232private candidates,31open issues|
|Source/candidates explicitly approved|No|
|Materialised|No;0NRS provisions/versions|
|Embedded/indexed|No|
|Release validated|No candidate release exists|
|Publication approved|No|
|Actually published and locally checked|No|
|Blocked/not verified|Await explicit source/scope approval; complete wording/hierarchy/form corrections and candidate acceptance remain pending|

The next safe action is the exact limited source/scope approval above, with fresh version/hash/target checks before application. Later candidate review must bind complete concrete revisions and resolved evidence; local release approval remains a separate gate. Do not start JRB at this checkpoint.
