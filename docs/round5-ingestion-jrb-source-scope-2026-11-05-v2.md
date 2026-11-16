# JRB source and page scope approved

5 November 2026, Africa/Lagos. The user's reply “approve” authorised the two actions in [JRB source and page-scope packet v1](round5-ingestion-jrb-source-scope-2026-11-05-v1.md). The exact request file SHA-256 was `46d24e6032a1458ff4f1cb211aabaa96789de691f0f646f567f24d1b46f2f071`. The user authorised the actions and the app recorded operator `e4688cce-ea38-4543-858a-f4951c95d92a`.

| Action | Recorded result |
|---|---|
| Verify the retained Tax Ombud-hosted gazette | Source `26807b39-e84a-49c0-9fa1-39c131695e20` moved to verified, lock 2. Audit `0477ff34-5788-48d3-a33d-31c5207293e5` and idempotency row `66684d8b-d299-47a1-8d3a-cbd6813939e8`. |
| Confirm PDF 4–34 with the shared boundary on PDF 34 | Run `24e70272-cf7f-4b97-98c5-5e32d254bebf` moved to lock 8 and remains waiting for review. All 35 pages moved to lock 2. Confirmation event `603dbd6d-5b39-478c-a33d-4d0ba3774368` and idempotency row `07191464-e456-467a-b7f7-ef42e569e1c5`. |
| Automatic bookkeeping | Provisional page-boundaries issue `baa287d3-4bde-41c8-8fce-064a9b6e0157` resolved. All 314 candidates still need review at revision 1 and lock 3. There are 35 open issues, 15 blocking. No wording or discretionary issue decisions were recorded. |

The retained original matched its hash, size and 35-page count. The two services were applied only after their request hashes, live versions, actor roles, target and 72 artifact bytes were checked. The read-back matched both idempotency request hashes and found the candidate text, artifacts, tasks and conversation pin counts as previously recorded. At 13:58:37 WAT the shared worker was stopped and the queue had zero pending, leased or running tasks and zero rows with lease metadata. The active enacted release was `5f3fe60c-c691-4ced-a60b-05aae29697c6`, target lock 4. [Read-back](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-approval-v1/approved-readback-v1.json)

The fresh pre-write PostgreSQL archive was 286,331,640 bytes with mode 0600 and SHA-256 `d6be769f540ce88be4bd7a2b53d94f90020ba86fe0d965355335cb8f1544d99e`. The TOC identifies database `app` and full archive decoding passed. Restore was untested. [Backup validation](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-approval-v1/backup-validation-v1.txt)

## Wording evidence and release blockers

Ten offline drafts link targeted visual readings to staged IDs and lock versions, raw OCR line observations, source image hashes and text hashes. They separate the three schedules at their printed boundaries, recover the Third Schedule and its five printed numbered paragraphs, and recover the section 60 conjunction “and” which Vision omitted. The drafts retain original OCR alternatives and distinguish OCR line boxes from page-level visual evidence. The revision of the draft corrected the definition-block detection so that all 12 unnumbered definitions are separated. Both draft versions remain available. These are partial working drafts. Full visual collation of every included page and opening, paragraph hierarchy, spans and exact audited wording actions remains open. [Targeted wording drafts v2](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-approval-v1/targeted-wording-drafts-v2.json)

**Exact reference routing.** The deployed `app/legal/instruments.py` registry recognises three laws. Its live parser returns `constitution-1999.section41` for “Section 41 of the Joint Revenue Board of Nigeria (Establishment) Act, 2025”. The generated short-title citation “Section 41, Joint Revenue Board Act 2025” and the JRB Act alias produce the unrecognised-law error. The exact citation route invokes this parser without a selected instrument. An explicitly instrument-filtered section query does resolve to JRB in the probe, and canonical-path lookup exists separately. The full title collision fails the required qualified exact lookup and cross-law separation checks. The test used synthetic paths and made no public source or database read. Natural-language schedule citations also fall outside the current section-only exact parser. Canonical-path lookup is the available route to validate for schedule identities once materialised. [Deployed citation probe](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-approval-v1/deployed-citation-probe-v1.json)

**Section 60 reader.** The workspace's `frontend/src/lib/legal-provisions.ts` helper rendered the 12 separated definitions as a single paragraph in an in-memory probe. The draft can retain those breaks in canonical text, but the current reader helper discards them. The probe tested the helper, and a deployed browser rendering check remains pending. [Section 60 reader probe](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-approval-v1/section-60-reader-probe-v2.json)

Separate authorisation is needed for changes to the JRB citation recognition and exact-reference routing, and for preserving explicit statutory paragraph breaks in the reader. The intended scope is the exact JRB full and short names, an explicit wrong-year or unknown-law failure in the tested qualified cases, and preserving deliberate paragraph breaks while still reflowing single source line wraps. Include focused regression coverage and leave the existing app, data and worker untouched until that authority is supplied.

| Stage | Status |
|---|---|
| Prepared offline | Source and page map complete. Ten targeted working wording drafts, full packet pending. |
| Staged | Private review, run lock 8 |
| Explicitly approved | Source verification and page scope, applied |
| Materialised | Zero JRB provisions or versions |
| Embedded or indexed | No JRB calls, vectors or index |
| Release validated | No JRB candidate release |
| Publication approved | Pending separate proposal |
| Actually published and checked | JRB absent from the active release |

[Restart checkpoint](round5-ingestion-jrb-checkpoint-2026-11-05-v3.json)
