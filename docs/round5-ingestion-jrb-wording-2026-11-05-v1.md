# JRB candidate wording and decisions for approval

5 November 2026, Africa/Lagos. This packet proposes exact candidate wording, hierarchy and decisions for the retained gazette of the Joint Revenue Board of Nigeria (Establishment) Act, 2025, Act No. 6. The edition is as enacted. The approved source caption gives 26 June 2025.

- [Readable proposed wording](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-wording-v2/proposed-wording-v1.md)
- [Exact candidate graph, text hashes, diffs and line spans](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-wording-v2/proposed-candidate-graph-v1.json)
- [Exact request bodies, IDs, optimistic versions, issue dispositions and execution order](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-wording-v2/candidate-wording-actions-v1.json)
- [Page and line collation](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-wording-v2/reviewed-page-transcript-v1.json) and [alternate OCR readings and visual checks](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-wording-v1/ocr-disagreement-visual-findings-v1.json)
- [Deployed request schema and read-only runtime validation](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-wording-v2/deployed-schema-validation-v1.json)

The action file SHA-256 is `a66b5ecbd76a148578b40d555a339db2fc6fcd5633bd7c7c7ef54d65f661ffe9`. The candidate graph SHA-256 is `de21491f1436844a7d36ac23b1a2e22a4c2700a15bf09e669959fee2d4b9a891`.

## Bound source and review

- PDF SHA-256 `808fb7b9d83606a4eea1c9b5f341d9ef260dc6db79a581fefab11e8f593974b0`, 9,711,228 bytes, 35 pages. [Retained original](../backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/Joint-Revenue-Board-Est.-Act-2025.pdf)
- Instrument `36b14c9b-7854-40c9-8b49-d52d8ba6db05`, source `26807b39-e84a-49c0-9fa1-39c131695e20` at lock 2, review run `24e70272-cf7f-4b97-98c5-5e32d254bebf` at lock 8. Operator `e4688cce-ea38-4543-858a-f4951c95d92a` passed active superuser and legal reviewer checks. User approval supplies the authorisation.
- Importer `statute-review-import-v2-explicit-roles`, scoped staging parser `act-hierarchy-v3` with file SHA-256 `e4ce0369db429f1836689b758948e31b6594f6bf0a8672e95439918b5f6a9a68`, extractor `jrb-apple-vision-lines-import-v1`. The request file binds all 72 artifact IDs and hashes. The original artifact is `fbe38d12-4352-4767-b823-c22f500894eb` and the normalized artifact is `115d4bb1-055a-44cf-a319-ca0624cbc98d`. [Approved scope and readback](round5-ingestion-jrb-source-scope-2026-11-05-v2.md)
- The read-only checks found the enacted target `5f3fe60c-c691-4ced-a60b-05aae29697c6` at lock 4 with manifest `b7ad4d1ead3683de6f4b8562310f0ca66f2e8815a2c42ae36da4987b315e45d0`. At 15:16:54 WAT the shared queue still had one running row carrying a lease ending at 15:14:36 WAT on 5 November 2030. The backend container had no shared worker process in that snapshot. The lease owner must release or coordinate the window before substantive writes.

## Wording and structure checked

I compared the operative text of PDF pages 4–34 with the images, alongside the original Vision extraction, a second Vision pass and the arrangement and body-opening evidence. The collation classifies all 1,320 retained OCR lines on these pages and maps 1,003 included lines to proposed candidates, including the visually confirmed conjunction on PDF 23 that only the second OCR pass captured. Line coordinates describe the original OCR line box. The original image and OCR remain available alongside visual corrections and span trims. The checks were performed by this agent.

The arrangement on PDF pages 2–3, all 61 body openings and catalogue titles reconcile. Page 3 prints 31 and “Zones” in 32. Part III appears both in the arrangement and in the body. The packet uses arrangement titles for section navigation, retaining the printed capitalisation variants at sections 26, 27 and 31. Section 5(f) and (l) are direct paragraphs. Section 28(2) continues across pages 12–13 with a wrapped cross-reference. Section 41(1)(j) continues onto PDF 17 before (k) and (l). Section 58(1) names section 86. The 12 definitions in section 60 include the conjunction before “President.” The Third Schedule ends at “such party.” on PDF 34, above the certification.

The proposal restores the printed ₦1,000,000 in section 51(2) and ₦500,000 in section 52(2). It retains source wording such as “Public Officers Protection Act” in section 54 and “Public Officer Protection Act” in Second Schedule paragraph 12. The proposed reading joins line wraps, joins explicitly identified line-end word divisions, retains compound hyphens, represents introductory dashes as en dashes and normalises spacing before punctuation. It preserves paragraph breaks as blank lines. Roman subclauses stay within their containing paragraphs and schedule subparagraphs stay within their numbered schedule items. The proposal records printed schedule captions as item headings and omits the staged OCR-generated excerpts in paragraph and subsection headings. Whole paragraphs retain continuation language where the source prints it in the same paragraph, including the closing clause in section 28(1)(c) and Second Schedule paragraph 7(10)(d).

## Exact proposed audited actions

| Action | Count |
| --- | ---: |
| Derive missing candidates | 29 |
| Update existing candidate wording, metadata or source spans | 312 |
| Apply conditional reviewed blocker resolutions | 5 |
| Reject false section 5 subsection (1) | 1 |
| Approve candidates | 342 |

The 342 active candidates comprise 7 Parts, 61 sections, 76 subsections, 159 paragraphs, 3 schedules and 36 schedule items in groups of 16, 15 and 5. The graph has 335 candidates with body text. One existing active candidate needs approval without a revision. The 29 derived candidates include 23 body paragraphs and the Third Schedule with its five items.

Ten blocking issues are expected to clear through the deployed revision revalidation. Verify those outcomes before approving the affected candidates. Five issue resolutions need explicit permission in this packet. They are the arrangement reconciliation and OCR span coverage for sections 15, 44, 51 and 51(2). The coverage resolutions preserve raw OCR and record why the image-confirmed punctuation or currency reading differs. Each resolution is conditional on the issue remaining open after the exact candidate patch. The 20 nonblocking extraction findings are retained as review history. The page-scope issue has already resolved.

Request schemas validated in the deployed app. The review, queue completion and idempotency functions checked in the workspace and running app have matching AST hashes. The running image still has `act-hierarchy-v2` with file SHA-256 `26a9da48b1b488b594b119435c21b5a0883264f807ee5ea73c73b392f21cafc8`. This packet revises the staged graph through review services. Materialisation consumes the audited revisions. The operation validation substituted a sentinel only for unresolved derived parent UUIDs. Resolve them from the audited derive response and recompute the affected hashes before sending those requests. Review application, materialisation and retrieval remain live validations.

## Next execution

After explicit approval of this action file, obtain a coordinated queue window, retain and decode a fresh backup, and recheck the source, operator, run, all 314 staged candidates, issue and idempotency state, artifacts and target. Reconcile any material change before proceeding. Apply the exact actions through supported review services. Confirm candidate texts, spans, IDs, issue outcomes and decisions before the final approval can enqueue JRB materialisation. Use only a scoped worker for that task. Verify the resulting counts, provenance and retrieval, and check the embedding endpoint’s revision guarantee and profile compatibility before paying for calls. Present the exact local release separately for publication approval.

This checkpoint records a privately staged review run and a complete offline wording proposal. The latest live state has zero candidate decisions, canonical versions and release entries for JRB. The earlier read-back with a strict idle-queue assertion failed when the shared queue became active. The observational read-back removed that stale assertion and retained the source and run checks. The default sandbox denied Docker socket access for the schema check. The authorised read-only retry succeeded.
