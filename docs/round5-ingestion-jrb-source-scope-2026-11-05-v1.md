# JRB source and page-scope approval packet v1

5 November 2026, Africa/Lagos. The Joint Revenue Board of Nigeria (Establishment) Act 2025 is staged privately in Compose `db:5432/app`, schema `d0e1f2a3b4c5`. This packet requests two specific decisions. [Exact requests and live bindings](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-stage-v1/source-and-scope-approval-request-v1.json)

## Decisions requested

1. **Verify source `26807b39-e84a-49c0-9fa1-39c131695e20` at lock 1.** Use `verify_source_document` with key `round5-jrb-808fb7b9-verify-source-v1`. The retained PDF is 9,711,228 bytes and 35 pages, SHA-256 `808fb7b9d83606a4eea1c9b5f341d9ef260dc6db79a581fefab11e8f593974b0`. It is the Federal Government Printer gazette hosted by the Office of the Tax Ombud, Gazette No. 117, Vol. 112, Government Notice No. 25, Act No. 6. The printed commencement is 26 June 2025 on PDF 4. PDF 35 contains documentary assent evidence for that date, corroborated by the State House release. The edition is as enacted, with later amendments possible. The source review does not establish consolidated wording or authenticate a physical signature. [Tax Ombud mandate](https://taxombud.gov.ng/about-us/mandate/) · [State House signing announcement](https://statehouse.gov.ng/president-tinubu-new-tax-laws-the-way-forward-for-nigerias-prosperity/) · [Provenance and status checks](round5-ingestion-jrb-preflight-2026-11-05-v1.md)
2. **Confirm page scope for run `24e70272-cf7f-4b97-98c5-5e32d254bebf` at lock 7 and all 35 page locks at 1.** Use `update_page_selection` with key `round5-jrb-808fb7b9-confirm-page-scope-v1`. Include PDF 4–23 for the body, 24–25 for the First Schedule, 26–31 for the Second, and 32–34 for the Third. On page 34 the intended statutory boundary is the end of Third Schedule paragraph 5(3), after “such party.” Keep the clerk certification starting “I certify” and the explanatory memorandum as evidence only. PDF 1–3 and 35 are evidence only, comprising the cover, arrangement, legislative authentication table, clerk certification and assent. Keep the page 4 commencement caption as edition evidence and separate running folios and marginal headings from operative text. [All page roles and renders](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-preflight-v1/page-map-v1.json) · [Page 34 image](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-preflight-v1/review-previews/page-34.png)

The request file SHA-256 is `46d24e6032a1458ff4f1cb211aabaa96789de691f0f646f567f24d1b46f2f071`. Both request bodies and service request hashes passed validation using the deployed app schemas. The file enumerates all 35 page IDs and 72 artifact IDs and hashes. The originals and normalized artifact IDs are `fbe38d12-4352-4767-b823-c22f500894eb` and `115d4bb1-055a-44cf-a319-ca0624cbc98d`. Each request uses the existing active operator account `e4688cce-ea38-4543-858a-f4951c95d92a`. The app granted its uploader and legal reviewer roles through superuser status. The operator records the user's authorisation. Any publication actor separation or override belongs to the publication gate. [Request validation](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-stage-v1/approval-request-schema-check-v1.json)

Source verification records the audit and idempotency keys and moves the source lock to 2. Page selection moves the run lock to 8 and each page lock to 2. It increments candidate locks, records the confirmation event and automatically resolves the provisional page-boundaries issue. No new excluded-page blockers are expected from the staged spans. The separate wording packet must address the within-page cutoff on PDF 34 because the selection service acts at whole-page granularity. These requests grant no wording or candidate decisions, discretionary issue resolutions, materialisation, embedding or promotion. Recheck live bindings, the release target and any idempotency or partial actions before applying either request.

## Private staging and read-back

| Record | Identity |
|---|---|
| Instrument | `36b14c9b-7854-40c9-8b49-d52d8ba6db05` |
| Upload | `38e64532-27ab-4b7e-bc8a-1f4d7da47c24`, completed |
| Admission run | `2a9b6b25-36d0-4ff3-bd52-04391a57a969`, cancelled after successful byte and scan checks to retain history and stop the alternate profiling path |
| Source | `26807b39-e84a-49c0-9fa1-39c131695e20`, needs review, lock 1 |
| Review run | `24e70272-cf7f-4b97-98c5-5e32d254bebf`, waiting for review, lock 7 |

The first backup attempt used an empty container database-user setting and failed as role `root`. The empty file and error were retained. The retry used the role resolved from the app engine without exposing it. The mode 0600 archive is 283,093,665 bytes, SHA-256 `0858a0bbb915181b2659f65dfa184c1536c6ab8d75c6705b0210249211694a6d`. Its TOC identifies database `app`, and `pg_restore` decoded the full archive to a null file. Restore was not tested. The archive covers PostgreSQL, and the application blob volume holds source and artifact bytes. [Backup validation](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-stage-v1/backup-validation-v2.txt)

The scoped process loaded the existing preflight-bound `act-hierarchy-v3` parser and `statute-review-import-v2-explicit-roles` importer in memory with the JRB catalogue. Admission used the deployed static scanner and review used the deployed normalizer. No application files or deployment settings were edited. Both admission tasks succeeded, as did normalization, structure parsing and document validation. The admission profiling task was cancelled before execution. Automatic source verification, candidate approval and embedding were disabled or withheld throughout. The import placed all pages in provisional review, with their individual proposed roles and reasons retained.

Read-back hashed all 72 stored artifacts and checked every raw page and image against the preflight inputs. The text hash and recorded transform of each normalized page matched the offline copy. The run contains 314 candidates at revision 1, including 61 distinct principal sections. It has 36 open findings, 16 blocking. The staged parser emitted two schedules and 31 schedule items against a source baseline of three schedules with 16, 15 and 5 numbered items. The Third Schedule was missed and the Second Schedule's last candidate absorbed Third Schedule and page 34 certification text. The arrangement issue records seven missing OCR entries and a spurious 2025 entry. The preflight checked the disputed labels and the scope boundary visually. Full line-by-line wording, spans, hierarchy and any layout-sensitive evidence still need review before the separate candidate packet. The read-back emitted serializer warnings for database strings representing enums, which are retained alongside the passing checks. [Staging log](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-stage-v1/staging-progress-v1.jsonl) · [Record inventory and read-back](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-stage-v1/staged-readback-v1.json)

At 13:47:51 WAT the queue contained zero pending, leased or running tasks and zero rows with lease metadata. The shared worker remained stopped. The 20 JRB outbox events are undrained notification records. The active enacted release remains `5f3fe60c-c691-4ced-a60b-05aae29697c6`, lock 4, manifest `b7ad4d1ead3683de6f4b8562310f0ca66f2e8815a2c42ae36da4987b315e45d0`. Aggregate conversation pins match the preflight.

| Stage | Status |
|---|---|
| Prepared offline | Source identity, provenance, scope and all 35 images checked and retained |
| Staged | Private review run, 35 page records and 314 provisional candidates |
| Explicitly approved | Awaiting the two decisions above |
| Materialised | Zero JRB provisions or versions |
| Embedded or indexed | Zero JRB builds, provider calls or charges |
| Release validated | No JRB candidate release |
| Publication approved | Pending separate release proposal |
| Actually published and checked | JRB is absent from the active release |

[Restart checkpoint](round5-ingestion-jrb-checkpoint-2026-11-05-v2.json)
