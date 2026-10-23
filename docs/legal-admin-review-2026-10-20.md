# Legal admin extraction review — 20 October 2026

This is an in-progress AI-assisted source-extraction audit, not certification by a human lawyer or verification of current consolidated law.

## Authority and scope

The user authorised repairs to the ingestion/review tools and continued review through the admin UI. The user subsequently expressly authorised approval of individually source-checked extraction candidates in the staged Police Act 2020 and ACJA 2015 runs. Source verification and publication are excluded. Uncertain candidates remain on hold.

The active public corpus remains the historical Constitution edition `draft-c8d50d87fae9`. Neither Act has been published in this review.

## Safety and source record

- A database safety dump was created at ignored path `backend/storage/backups/app-before-legal-review-20261020T122401Z.dump` before structural edits. It includes the first section-142 text revision.
- Police review run: `07e6dc81-c9d5-421c-83d5-1cb618a19578`.
- ACJA review run: `7b4b9bc4-0a9c-49d8-acfe-2344a16afe96`.
- Superseded cancelled runs are excluded from this review.
- The retained Police signed PDF has 57 pages. Body pages 5–53 and the statutory Schedule on page 54 are included. The explanatory memorandum and arrangement (1–4), Clerk authentication (55), and authentication/assent table (56–57) are excluded from legal body extraction while retained as provenance.
- The admin recorded boundary confirmation as run event 9. This invalidated earlier candidate approvals, which were subsequently reviewed and recorded again.

## Completed source comparisons and decisions

All 27 candidates under `police-act-2020.part17.` covering sections 135–142, including their existing and recovered children, were individually checked for text, identity, parentage, source pages, and source-span range. A final admin readback found no differences from the checked transcriptions. All 27 were approved under the user's explicit extraction-review authorisation.

The separately recovered `police-act-2020.schedule1` was compared with page 54 and approved. The original printed enumeration jumps from (xix) to (xxi); no item (xx) was invented.

Repairs include:

- Section 142 was separated from the merged Schedule and authentication material. Its wording and source mapping now end on page 53.
- The parser's section 14 near the end of the Act was corrected to section 141, Interpretation, based on pages 52–53.
- Missing section 138(1)(b), section 139(1), section 139(2), and the Schedule were recovered as separate candidates with retained origin evidence and individual review.
- Scan artefacts and marginal headings were removed from the checked provision bodies; child source ranges were narrowed where necessary.

Printed wording anomalies were preserved, including “made under to this Act” in section 135 of the retained signed copy, “Constitution of the Federal of Nigeria” in section 136, “is deem” in section 140(5), and the missing closing quotation mark in the final section-141 definition. They must not be silently harmonised with another source edition.

## Work remaining

Most Police Act candidates and all ACJA candidates remain to be individually checked. This document does not represent completion of the queue.

The Police Act arrangement labels the public-complaints Part XVI, but the retained body page 50 prints Part XV, duplicating the traffic-wardens Part number. The Gazette facsimile also prints XV in the body. A separate bodyless root was recovered as `police-act-2020.part15.source50`, preserving number 15 and documenting the disagreement. Sections 131–134 and their children were moved to that root. Five merged children were recovered: 133(2)(b), 133(2)(c), 133(5), 134(a), and 134(b). All 20 complaints body candidates passed final text/identity/hierarchy/page readback and were approved, together with the new root. The printed comma at the end of 132(2) and “Commissioner of Police a State” in 134 remain preserved.

The Part XVII root mapping was narrowed from a whole page to the five heading boxes and approved. The admin subsequently showed **50 approved Police Act candidates**. The comparison record is in `docs/legal-admin-source-comparisons-2026-10-20.json`; the live admin audit retains the full source mappings and reasons.

## Tooling changes and validation

The admin now supports audited structure/source-mapping edits, recovering missing provisions without altering the origin, nullable metadata clearing, page/path filters, readable audit reasons, and imported-run boundary confirmation. Graph validation rejects duplicate paths, cycles, cross-run parents, invalid page ranges, and edits to cancelled/materialised candidates. Raw source extractions and before/after snapshots are retained.

The initial full isolated backend run passed 667 tests with 4 skipped and 89% coverage. Structural recovery has since been extended to allow a bodyless Part/Chapter only when it has a heading. A live reparenting save exposed a UUID audit-serialization bug; the failed transaction rolled back, the serializer was repaired, and non-null reparenting regression coverage was added. All 54 admin backend tests then passed. Application Mypy/ty, Ruff, frontend build and Biome passed. Explicitly checking the whole legacy test file with Mypy also reports pre-existing fixture/type errors; these are outside the application type-check scope. Authored frontend regression specs have not yet been run as a suite; the live recovery, metadata-only structure, reparenting, filtering, readback and approval flows were checked through computer use.

## Source verification and materialisation (23 October 2026)

### Pre-flight audit

A read-only audit found no pending candidates or open issues on either live run. Both runs' page boundaries were already confirmed (Police Act 20 October, ACJA 21 October). Pressing **Confirm reviewed boundaries** again returns every approved candidate to needs review, so it was not pressed.

Two defects blocked the hand-off, and both were fixed with regression tests:

- **Rejected candidates blocked completion.** The review gate (`service.py`) and the materialisation worker (`worker.py`) counted rejected candidates as unfinished, and counted open findings on rejected records as blocking. ACJA's 298 rejected duplicates and 46 findings on them would have held the run at review forever. Rejection is now treated as a final decision: rejected candidates are never materialised and their findings do not block.
- **Nested paragraph citations were truncated in retrieval text.** `citation_for_provision` kept only one paragraph level, so ACJA 123(b)(i)–(vi) were all cited "Section 123(b)". Every level is now kept ("Section 123(b)(iv)"). Reader-facing citations in `public_corpus.py` were already correct.

### Actions, with the user's authorisation

- A safety dump was taken at ignored path `backend/storage/backups/app-before-materialize-acts-20261023T100456Z.dump`.
- Both source documents were verified through `verify_source_document` as the as-enacted historical editions. Each reason records the known defects: ACJA section 120 and the missing page for Forms 8–9, and the Police Act Part XV/XVI numbering.
- The worker ran inside the backend container, with `INGESTION_ALLOWED_INSTRUMENT_TYPES=["constitution","act"]` set for that command only; `.env` is unchanged. The first local attempt failed on the container-only storage path and rolled back with nothing written. Both runs were retried through `retry_ingestion_run`.
- A rebuild of retrieval documents with corrected citations was refused by the immutable artifact store. The original artifacts were kept, and both runs were restored to ready to embed with a `retrieval_documents_rebuild_withdrawn` event. The corrected citations take effect when the composite release rebuilds retrieval documents. The per-run member artifacts keep the truncated citations, so nested Roman items are re-embedded at composition.

### Result

A post-materialisation audit compared every live candidate with its provision: identity, kind, number, heading, sort key, parent and version text all match, and every version has historical status. No rejected candidate was materialised.

| Run | Source | Candidates | Release entries | Retrieval documents | State |
| --- | --- | --- | --- | --- | --- |
| ACJA `7b4b9bc4` | verified | 1,979 materialised, 298 rejected | 1,930 | 1,948 | ready to embed |
| Police Act `07e6dc81` | verified | 953 materialised | 931 | 938 | ready to embed |

The releases without entries are bodyless Part and cross-heading roots (ACJA 49; Police Act 17 Parts and 5 cross-headings). Retrieval documents outnumber entries because long provisions are split into chunks. Draft releases `draft-7b4b9bc40a9c` and `draft-07e6dc81c9d5` are building. The production Constitution release `draft-c8d50d87fae9` is unchanged. Embedding, release validation, composition and publication have not been started.
