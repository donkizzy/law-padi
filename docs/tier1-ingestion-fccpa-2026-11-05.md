# Federal Competition and Consumer Protection Act 2018: review report (5 November 2026)

Approved by the user on 5 November 2026. Source verified, materialised, embedded (Recall@10 0.967) and included in `composite-2026-11-05-nineteen-laws`, which is ready to publish.

| Item | Value |
|---|---|
| Instrument | `federal-competition-and-consumer-protection-act-2018`, Act No. 1 of 2019 gazette, as enacted (historical) |
| Source | FCCPC copy of the Official Gazette of 1 February 2019, `official`, SHA-256 `aa942cdef860…`, status `needs_review` |
| Run | `a1b74318-51ec-474a-996a-a4674047be6b`, waiting for review, parser `act-hierarchy-v3` |
| Pages | 8-98 included; p25 kept in range with its text removed; cover, arrangement and bill schedule excluded |

## Malware scan

The file first failed on a single `/AA` byte run inside compressed image data. By decision of 5 November 2026 the scanner was narrowed (`pdf-static-safety-v2`): a marker is ignored only inside an image object's declared data whose direct length lands exactly on `endstream`. Markers in dictionaries, non-image streams, or objects with an indirect or wrong length still fail. The file then passed the normal scan; no exception was used. Regression tests are in `backend/tests/ingestion/test_malware.py`.

## Reconciliation

168 catalogue sections against 168 body sections: none missing, unexpected or repeated, no parser notes. 18 Parts and 2 Schedules. The second "58" in the arrangement is section 59.

## Review counts

- Approved 1,014: 168 sections, 18 parts, 2 schedules, 3 schedule items and the subsections and paragraphs beneath them.
- Revisions 651, each with a reason. 20 unbalanced-punctuation blockers cleared by revision; no override was used.
- Pre-parse corrections to labels, markers and wrapped references: 206.
- Rejected 6: sub-lists inside definitions in s.167(1).
- The pre-parse corrections are logged in `backend/storage/statute-review/tier1-2026-11-05/fccpa/label-corrections.json`.

## Corrections

- OCR slips across the Act, from a hand-read list of proposed changes. An automatic matcher was rejected after it proposed false fixes such as `conferred` to `concerted`.
- Lines rebuilt from the page in ss.84, 86, 95, 114, 130, 148 and 167.
- Struck naira sign restored where the page prints it.
- Printed page A23 appears twice; the second copy (PDF p25) contributes no text.

## Kept as printed and flagged

- s.72 prints two subsections read as (3) before (4); the second (`An undertaking shall not be treated as abusing...`) stays inside (3). Please check it.
- s.167 prints (10) then (12). The gap is kept.
- s.156 list items stay in subsection (2)'s text.
- s.160's wrapped cross-reference crosses a page and shows as an extra "(2)" in the text.

## Limits of the check

This is the least certain text so far. The scan is 200 dpi and only Vision was available as a reader, with the damaged text layer not used. A few tokens remain unresolved, mostly in s.167 definitions (for example `urursthieh`, `enuemen`), and real-word OCR errors are not detectable by spelling. A full read against the page is advisable before verifying, especially s.167. Headings use the reviewed catalogue.

## Amendments

BOFIA 2020 s.65 changes how this Act applies to banking. It is not folded in. A notice is advisable.

Benchmark draft: `docs/federal-competition-and-consumer-protection-act-2018-retrieval-benchmark.json` (30 questions).
