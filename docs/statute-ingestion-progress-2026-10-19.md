# Statute ingestion: identity foundation and Act extraction review

Status updated 20 October 2026: Phase 1 and the Phase 2–6 infrastructure are implemented. Qualified retrieval and prompt v11 answer contracts pass synthetic release checks. Both real Acts remain in extraction review; OCR/numbering defects and pending human verification still block materialisation and composite activation. Real statute benchmarks and live answer evaluation remain pending; Phase 6 law navigation and public metadata are implemented; only the Constitution appears in the actual public picker. Phase 7 evaluation and rollout remain pending. See [Phase 3](statute-phase3-composite-release-2026-10-19.md), [Phase 4](statute-phase4-references-retrieval-2026-10-20.md), [Phase 5 validation](statute-phase5-answer-generation-2026-10-20.md) and [Phase 6](statute-phase6-frontend-2026-10-20.md).

## Source copies awaiting review

The user approved both downloads in this chat on 19 October 2026. Download approval is distinct from source verification and publication approval.

| Source | Publisher / host | File size | PDF pages | Native text | Local source status |
|---|---|---:|---:|---|---|
| ACJA 2015 | National Assembly signed copy, hosted by Federal Ministry of Justice | 14,002,925 bytes | 243 | None | `needs_review`, `trusted_secondary` |
| Nigeria Police Act 2020 | National Assembly signed copy, hosted by PLAC | 2,699,714 bytes | 57 | None | `needs_review`, `trusted_secondary` |

- [ACJA download source](https://justice.gov.ng/wp-content/uploads/2020/09/Administration-of-Justice-Criminal-Act-2015.pdf)
- [Police Act download source](https://placng.org/i/wp-content/uploads/2020/09/Police-Act-2020.pdf)
- [ACJA retained PDF](../backend/storage/statute-review/acja-2015/Administration-of-Justice-Criminal-Act-2015.pdf)
- [Police Act retained PDF](../backend/storage/statute-review/police-act-2020/Police-Act-2020.pdf)
- [Full provenance, hashes, registration IDs and review findings](statute-source-review-2026-10-19.json)

The Ministry of Police Affairs also has an indexed candidate, but its HTTPS certificate was expired when checked. Its PDF was not downloaded. PLAC's approved copy was used instead.

Both downloaded files passed the repository's static PDF safety scanner. Their retained originals are unchanged. Local `SourceDocument` rows point to content-addressed copies in the existing local ingestion storage volume; audit events record the approval boundary and conservative source-tier choice. The instruments remain drafts, and neither source is verified. No Act provisions or release entries have been published.

Both scans include National Assembly authentication and presidential-assent sheets. A Gazette cover was not confirmed, so the source tier remains `TRUSTED_SECONDARY` under the plan's rule. The provisional source-edition dates were read from the assent sheets: 13 May 2015 for ACJA and 15 September 2020 for the Police Act. A human must confirm these metadata choices.

### OCR review

All 300 pages were processed locally using the existing `ingestion-worker:latest` image, Tesseract 5, automatic page segmentation/orientation (`--psm 1`), and 150 dpi renders. Networking was disabled for OCR. Each source folder contains `inspection.json`, `ocr-pages.json`, `ocr-text.txt`, and first/final-page previews. These are review artifacts, not approved canonical legal text or golden fixtures.

- ACJA: page 1 is rotated and poorly recognized. Arrangement numbering is displaced or omitted on several pages. The body also has marginal headings and numbering that OCR reorders. Pages 1 and 204 have mean word confidence below 0.75.
- Police Act: the OCR retains all pages, but examples include section `1` recognized as `L`, section `42` as `421`, and rearranged marginal numbering. High mean word confidence does not establish legal accuracy.
- ACJA search provisions should be checked against PDF pages 16–18; Police Act search provisions against pages 22–24. These page locations are review aids, not verified extraction boundaries.

The source PDFs are ready for a source-authenticity review. The OCR output requires layout correction and legal-text review before Act parsing can be approved.

### Amendment research remains open

Research found leads that must be resolved before treating either source as a verified as-enacted edition:

- A [National Assembly midterm report, hosted by Legis360](https://lip.legis360.org/uploads/resources/1769429986_MTR_1.0.pdf), lists a Nigeria Police (Amendment) Act 2024. The amendment's primary text, assent and commencement have not been verified. No further PDF was downloaded, and no amendment wording was merged.
- The [Federal Ministry of Information](https://fmino.gov.ng/president-tinubu-committed-to-building-an-efficient-judiciary-system-agf-fagbemi/) reports stakeholder review of a **draft** ACJA Amendment Bill. This does not prove enactment or establish that there are no other amendments.
- The [Nigeria Police Force](https://www.police.gov.ng/news/details/769) reports gazetted Police Regulations in April 2026. Regulations must be distinguished from amendments to the Act.

No unverified amendment lead has been represented as an enacted `Amendment` row. Obtain the primary amendment sources, follow the download-approval rule, and record confirmed amendments separately before completing Phase 0. Keep the planned notice: **“As enacted, may have been amended.”**

## Phase 1 implementation

- `SectionReference` now carries an instrument slug, defaulting to `constitution-1999`. Qualified identities preserve hierarchy and exact section-number boundaries.
- A shared `matches_reference` helper handles Python matching and escaped SQL matching. Search, evidence assembly, chat context, deterministic citation validation, topic retrieval, and selected-provision validation use instrument scope.
- Public result, provision-reference and evidence schemas carry instrument slug, title, short title, type and short citation. The canonical loaders obtain metadata from `LegalInstrument`.
- Constitution citation strings are preserved. Act citations are qualified, for example `Section 9, ACJA 2015` and `ACJA s.9`. Act provisions cannot inherit Constitution section titles.
- Retrieval documents carry the canonical instrument ID; segment writes derive and validate it from `Provision`. The index validator checks for instrument mismatches.
- Alembic revision `f5a6b7c8d9e0` backfills `RetrievalSegment.instrument_id`, adds its foreign key and indexes, and restores the published-row trigger within the same migration transaction. It was applied to the dedicated test database and local development database.
- Regressions cover same-numbered sections across laws, SQL wildcard escaping, evidence validation, source cross-reference scope, selected chat provisions, and a populated production-release migration round trip. The migration test compares every existing retrieval field and verifies the immutability trigger still rejects changes.

## Validation

- Backend: **524 passed, 2 skipped**, **89%** total coverage; mypy, ty, Ruff lint and formatting passed.
- Frontend production build and Biome checks passed.
- Constitution retrieval benchmark: before/after JSON reports are identical, including misses and all ranking signals. The 57-case dataset retains **0.98 hit@1 / 1.00 hit@5**; the 40-case held-out dataset retains **0.95 hit@1 / 1.00 hit@5**. [Recorded reports](statute-phase1-retrieval-validation-2026-10-19.json).
- Local active release `draft-c8d50d87fae9`: index validation passed with **1,829 segments and 1,829 embeddings**. Segment and embedding checksums match the stored validation report.
- Browser tests: final full run exited successfully with **87 passed and 1 flaky (passed on retry)**, using one worker and one retry. The flaky case was “Draft survives reload and New clears it even when already on an empty chat.” Earlier runs also had intermittent admin polling/navigation and saved-search timeouts; those cases passed on isolated reruns and in the final run. Browser timing remains a validation caveat.

## Phase 2 implementation and actual-source results

Act uploads carry an explicit instrument type through quarantine and verification. `INGESTION_ALLOWED_INSTRUMENT_TYPES` defaults to `["constitution"]`; enable `["constitution","act"]` for an authorised Act ingestion operation. The local review import enabled this setting only for its own commands. Alembic revision `a7b8c9d0e1f2` adds the upload type with a Constitution default for existing rows and clients. It is applied locally and in the dedicated test database. The generated frontend client was refreshed with `scripts/generate-client.sh`.

`ActParser` (`act-hierarchy-v2`) handles Parts without Chapters, numbered sections, subsections, paragraphs, Roman clauses retained within paragraphs, interpretation text, schedules with inline references, and authentication boundaries. Arrangement headings are navigation metadata; they never create missing body sections. Observed comma/noise punctuation is accepted without changing digits or wording. Oversized headings retain their original content as review evidence instead of failing database insertion. A regression also covers database rollback before recording a failed worker task.

Act provision materialisation always uses historical semantics, even if a run incorrectly requests current-law status. Its edition notice is **“As enacted, may have been amended.”** Per-instrument title files contain source hashes and partial, unverified navigation catalogues: 17 ACJA headings and 24 Police Act headings. Completing and checking those catalogues remains part of source review.

All 300 approved PDF pages now have resumable OCR artifacts with line boundaries, word confidence, word coordinates and source hashes, plus source-page previews in the review queue. OCR ran offline at 200 dpi with Tesseract 5 (`--psm 6`). The original PDFs are unchanged. Imported page roles and inclusion boundaries are provisional; each run has a blocking issue requiring their confirmation. No source was verified, candidate approved, canonical Act version created, embedding requested or release published.

| Act | Current review run | Section candidates / expected | Unique numbers | Blocking issues | Source previews |
|---|---|---:|---:|---:|---:|
| ACJA 2015 | `7b4b9bc4-0a9c-49d8-acfe-2344a16afe96` | 594 / 495 | 444 | 241 | 243 |
| Police Act 2020 | `07e6dc81-c9d5-421c-83d5-1cb618a19578` | 131 / 145 | 124 | 78 | 57 |

**20 October correction:** the table above preserves the Phase 2 review snapshot. The Police Act arrangement on PDF page 4 ends at section **142**, not 145. The current catalogue and acceptance check expect 142; a recheck of the same OCR finds 21 missing expected numbers. Source verification and full reconciliation still fail. [Updated source-count evidence](statute-phase4-source-checks-2026-10-20.json).

The candidate counts include false and repeated markers; they are **not** approved statutory section counts. ACJA has 57 missing expected numbers, 6 unexpected numbers and 97 repeated numbers. Police Act has 24 missing, 3 unexpected and 7 repeated numbers. Examples include `48` read as `4g` and `52` read as `59`. The parser retains and flags these readings; it does not repair numbers to fit an expected sequence. Repeated sections and page boundaries must also be checked against the scans.

Both optional full-PDF acceptance tests were explicitly run and **failed**. Each search-text needle was found in one candidate (ACJA s.9 and Police Act s.49), but neither Act passes complete section reconciliation. Those limited substring matches do not verify full provision wording. The ordinary suite skips these two checks when the ignored local source artifacts are absent; its green result does not certify the scans. [Full-PDF acceptance evidence](statute-phase2-full-pdf-acceptance-2026-10-19.json) and [complete review findings](statute-phase2-source-review-2026-10-19.json).

Two superseded import runs were cancelled after the parser refinement, retaining their evidence for audit. The current run IDs above are the review targets. Open the admin workspace, select the matching ingestion run, and use Page boundaries and Review queue to compare candidates with the PDF previews. The source PDFs linked above remain the reference for full-size inspection.

Review tooling is in `backend/scripts/extract_statute_review.py` and `backend/scripts/stage_statute_review.py`. The first validates approved local file hashes and produces offline OCR/previews; the second imports those artifacts and executes only its own normalization/parsing/validation tasks, stopping at review. Rerunning an unchanged import reuses its run. No global worker queue is drained by these scripts.

### Phase 2 regression validation

- Backend: **543 passed, 4 skipped**, **89%** coverage; mypy, ty, Ruff lint and formatting passed. Two skips are the optional real-PDF checks, which were also run separately and failed as recorded above. New script/test Ruff checks passed.
- The generated-client production frontend build and Biome checks passed. Browser regressions for upload/review and Constitution lookup passed: **34 tests**, using one worker and one permitted retry; no test needed a retry. No new product UI was added in this phase.
- Constitution retrieval results are identical to Phase 1 across all 97 benchmark cases, including ranking signals and misses: **0.98 / 1.00 hit@1 / hit@5** on the 57-case dataset and **0.95 / 1.00** on the 40-case held-out set. [Comparison report](statute-phase2-retrieval-validation-2026-10-19.json).
- The active Constitution release remains `draft-c8d50d87fae9`, with **1,829 segments and 1,829 embeddings**. Index validation passes and both stored checksums are unchanged. [Index evidence](statute-phase2-index-validation-2026-10-19.json).

## Remaining review boundary

Phase 0 requires human confirmation of each source's authenticity, provenance and metadata. Amendment verification remains outstanding. Phase 2 requires corrected OCR and page boundaries, complete checked arrangement headings, passing full-PDF acceptance checks, and approved materialised runs with zero blocking issues. The plan explicitly defines completion as **“each Act has an approved, materialised ingestion run with zero blocking review issues.”** These conditions have not been met; broad approval should not clear the recorded defects. Composite-release, mixed-law retrieval and answer-generation infrastructure are implemented, but actual activation and statute evaluation depend on these reviews. Frontend law navigation is implemented and tested with synthetic multi-law releases. Actual Act activation, evaluation and rollout remain gated by the source reviews.

The existing Constitution production release remains active. Existing local user changes were retained, and no dependency lockfiles were changed.


## Phase 6 interface and metadata

The selected published release now drives the law picker, filtered Browse trees and Find searches. Canonical `/laws/<slug>/…` links preserve editions; legacy `/constitution` links and bookmarks remain supported. Chips, source panels, saved items and exports retain law identity and edition caveats. Landing and server-rendered public pages use the same published membership, including the sitemap. The real public list still contains only the Constitution. See [the Phase 6 implementation and validation report](statute-phase6-frontend-2026-10-20.md).
