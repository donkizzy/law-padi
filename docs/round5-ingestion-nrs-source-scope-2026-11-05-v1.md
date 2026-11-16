# Round 5 NRS ingestion on 5 November 2026

The official NRS-hosted Gazette No. 117, Vol. 112, Act No. 4 is verified as the retained as-enacted source. The local review run includes PDF pages 5–28, with the body on 5–23 and three schedules on 24–28. All 30 pages remain in source evidence. The run is still waiting for wording review. [Working review packet](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/candidate-wording-working-evidence-v1.html) · [Wording and form addendum](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/wording-review-addendum-v1.md)

## Live checks and applied approvals

Compose backend used `db:5432/app`, PostgreSQL 18.6. The schema was already at `d0e1f2a3b4c5`. Its migration widens the embedding benchmark version column and leaves the approval tables compatible. The active release had changed since the previous checkpoint to `a36a3cf5-4e55-47bf-b28f-2167b0dae26e`, with enacted retrieval target lock version 3 and manifest `d427ea4c2e8c2977a34434f29c2f671b818eecc74168025ab040660165658c7c`. The user explicitly renewed approval for the same two actions against this baseline, conditional on the NRS records still matching.

Checked the bound request and HTML SHA-256 values, 8,039,130-byte original PDF, 30-page count, stored original hash, import hash, 62 stored artifact hashes, and the live rows against the retained snapshot. The failed admission task and successful retry are both present. The application role checks succeeded for legal reviewer and ingestion uploader through the active operator account `e4688cce-ea38-4543-858a-f4951c95d92a`. The user supplied the authorisation. The app account identifies the operator. No independent legal review or signature authentication was performed.

The first backup attempt used an empty database-user setting and failed as local role `root`; the zero-byte output was retained. The retry produced a mode 0600, 212,917,576-byte PostgreSQL custom archive with SHA-256 `6684818954f81fb032b4962d4c5fad32c0acf8e75033fb21de36dcdd27a08a45`. The TOC identified database `app`, and `pg_restore` decoded the full payload to a null file. Restore behavior remains untested. The archive covers PostgreSQL. Stored PDFs and review artifact bytes remain in the source volume.

| Action | Recorded result |
|---|---|
| `verify_source_document` | Source `c62eed90-8334-4e8c-84aa-3a6a461dc79d` went from lock 1 to 2. Audit `a701d652-ca60-4bd0-9778-55e5b28f007c`, idempotency row `6942967e-86b3-42f0-b1d3-e5cceb405054`. |
| `update_page_selection` | Run `0ad31203-e00b-4feb-9700-0a7769b09b36` went from lock 7 to 8. All 30 page locks went from 1 to 2. Page event `ec68d111-6304-484f-8013-306a763a4c9a`, idempotency row `fb7ac317-beac-449b-902e-eed11b31adf5`. |
| Automatic service bookkeeping | Resolved provisional-boundary issue `13a33871-a1a1-42ce-a405-ce19b7747843`. Opened excluded-page blocker `d2883905-b64f-4e14-bdb3-8ef5f7c87097` on false Third Schedule item 20. The other 30 original open findings were preserved. |
| Independent read-back | Verified the exact request hashes, actor and audit linkage, 24 included pages, 6 excluded pages, all 232 candidates awaiting review at revision 1, and 31 open issues including 19 blocking. The seven NRS task rows were unchanged and unleased. The active target and manifest still match the refreshed baseline. |

The backend process inventory showed two shared worker processes. Neither authorised action made NRS work claimable. Source verification requires all candidates approved before it can queue materialisation. The imported-review page-selection branch records the boundaries and keeps the run at review. No worker intervention was needed. The runtime parser and scanner still differ from the workspace and neither ran for these approvals. The approval service module matched the workspace byte for byte. [Preflight](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/live-preflight-v1.json) · [Post-action read-back](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/live-after-actions-v1.json)

## Wording and implementation gate

Visually checked the arrangement pages, every included page and each of the 43 body openings against retained images. Compared each arrangement title with the catalogue and staged heading. Section 21 picked up folio A232, and section 43 picked up subsequent display text. The visual evidence also distinguishes the three First Schedule headings, confirms 17 + 5 + 2 genuine numbered schedule items, and retains the unnumbered offence tail in section 33(2), the section 11 (j) label, and the source's section 4(1)(l). The working evidence contains 30 candidate text drafts with diffs and hashes and 31 paragraph drafts, including 28 missing paragraph proposals. These are partial working drafts. Final line-by-line wording, corrected source mappings, hierarchy counts and audited mutation payloads still need reconciliation.

The warrant is the implementation blocker. In the current workspace, `ReviewItemUpdate` carries text and spans and `ProvisionView` passes authoritative text to `StatuteText`. The exact reader functions still collapse a plain source-form sample from 17 lines to one. The new table path uses explicit pipe separators and a header row. It does not represent the printed warrant's separate blanks and signature/date rows without additional encoding. A form-capable representation or a supported existing path that demonstrably preserves that layout is needed before requesting wording approval. Application changes require separate authorisation under the handoff. [Reader reproduction](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/warrant-reader-layout-probe-v2.json)

| Stage | State |
|---|---|
| Prepared offline | Verified source evidence and partial wording drafts. Complete approval packet pending. |
| Staged | Existing NRS review run, lock 8. |
| Explicitly approved | Source identity and page scope, applied. Zero wording decisions, revisions or discretionary issue resolutions. |
| Materialised | Zero NRS provisions. |
| Embedded or indexed | No NRS calls, vectors or build. Hugging Face compatibility has not been established. |
| Candidate release validated | No NRS candidate release. |
| Publication approved | Pending separate release proposal and approval. |
| Actually published and locally checked | NRS has not been promoted. |

The checkpoint and inventory identify the two applied actions, affected rows, derived files, backup and retained failed attempt. Application code, tests, migrations and configuration were outside the scope of this run. Other local repository activity was observed separately, including the new reader table code. No unrelated source or run was opened or processed. [Checkpoint](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/checkpoint-004-source-scope-approved-wording-blocked-v1.json) · [File inventory](../backend/storage/statute-review/ingestion-round5-2026-11-05-nrs-review-v1/created-file-inventory-v1.json)
