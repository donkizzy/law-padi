# Evidence Act 2011: review report (5 November 2026)

Approved by the user on 5 November 2026. Source verified, materialised, embedded (Recall@10 1.0) and included in `composite-2026-11-05-fifteen-laws`, which is ready to publish.

| Item | Value |
|---|---|
| Instrument | `evidence-act-2011`, Act No. 18, as enacted (historical) |
| Source | Official Gazette No. 80 of 21 June 2011, A291-371, via Gazettes.Africa, `trusted_secondary` because of the archival host, SHA-256 `3d6d712682a9…`, status `needs_review` |
| Run | `59ff18b0-97c4-4516-b441-84836ba111b9`, waiting for review, parser `act-hierarchy-v3` |
| Pages | 11-80 included; cover, arrangement and bill schedule excluded |
| Earlier runs | Four import runs cancelled and retained (`f082bde1`, `65ab2e65`, `48824d77`, `2ccbad74`), plus the admission run |

## Why the source changed

The PLAC copy is the signed enrolled text, but a page is lost: it runs from the first line of s.131 straight to s.138. The gazette is complete. It is also a retyped print with its own errors, so neither copy is clean. The gazette is the base text and the PLAC copy is the independent check.

## Reconciliation

259 catalogue sections against 259 body sections: none missing, unexpected or repeated, no parser notes. 16 Parts.

## Review counts

- Approved 706: 259 sections, 233 subsections, 198 paragraphs, 16 parts.
- Rejected 4: paragraphs inside a definition in s.258(1).
- Revisions 518, each with a reason. No derived items. A comma-for-full-stop pass was applied by rule wherever a sentence ran on in lower case.
- Issues: 24 raised and all resolved. 7 unbalanced-punctuation blockers cleared by revision; 1 page-boundary blocker cleared by page confirmation. No override used.
- Pre-parse corrections to labels and markers: 149, listed in `backend/storage/statute-review/tier1-2026-11-05/evidence-gazette/label-corrections.json`, with the untouched consensus in `consensus.json` beside it.

## Gazette misprints corrected

The rule allows a fix when the Act's own text proves the reading. Decided by the user on 5 November 2026: the signed PLAC copy counts as the Act's own text where the sentence also requires the reading, so these corrections stay.

| Section | Gazette prints | Corrected to |
|---|---|---|
| 21 | case `is` expressly | `as` |
| 23 | made by `person` to whom | `persons` |
| 36 | `when` the period of 12 months | `within` |
| 62 | orders `of` decrees | `or` |
| 65, 164 | `assuring` | `assuming` |
| 82, 223 | `provision` to section | `proviso` |
| 90 | a seaman `issues` for his wages | `sues` |
| 96 | in the `matter` in which | `manner` |
| 98 | procure `is` due execution | `its` |
| 101 | words `of` figures | `or` |
| 106 | elsewhere `that` in | `than` |
| 110 | other `then` Nigeria | `than` |
| 116, 150 | `he` purpose, `he` President | `the` |
| 117 | it is `take` | `taken` |
| 126 | those `ground` | `grounds` |
| 143 | `at` possession | `in` |
| 165 | Matrimonial `Cases` Act | `Causes` |
| 210 | The `under` in which witnesses are produced and `examines` | `order`, `examined` |
| 246 | `proceeding` sections | `preceding` |
| 249 | police `office`, `evidence all`, in `its` | `officer`, `evidence of all`, in `it` |

## Kept as printed and flagged

- s.134 reads "in all civil proceeding". The PLAC copy lost this page, so nothing confirms the plural.
- s.256(1) runs (a), (b), (d) in both copies. The gap is kept.
- 33 places where the gazette reading makes sense and the PLAC reading differs, kept from the gazette (list in `flag.json`), for example s.128 `the`/`due execution`, s.207 `end`/`time`, s.40 `hope`/`hopes`, s.90 `to`/`of`. Several of these are PLAC OCR errors.

## Limits of the check

- All pages had three Vision passes in overlapping bands. A line-level audit against PLAC found no dropped gazette lines.
- 29 meaning-changing pairs were read on the page image. The other corrections rest on the PLAC reading and the sentence, not on my eye, so a sample check is worthwhile.
- Sections 132-137 and most of s.131 have no second copy. They rest on the gazette and OCR alone. I read the openings of those sections but did not check every word against the image, so please spot-check them; they are the burden and standard of proof.

## Amendment

The Evidence (Amendment) Act 2023 changes ss.84, 93, 108, 109, 110, 119, 255 and 258 and inserts ss.84A-84D. None of that is folded in, so s.84 here is the 2011 wording. A notice on the affected sections is advisable before publishing.

Benchmark draft: `docs/evidence-act-2011-retrieval-benchmark.json` (33 questions).
