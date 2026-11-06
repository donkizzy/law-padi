# Criminal Code Act: review report (5 November 2026)

Approved by the user on 5 November 2026. Source verified, materialised, embedded (Recall@10 0.97) and included in `composite-2026-11-05-fifteen-laws`, which is ready to publish.

| Item | Value |
|---|---|
| Instrument | `criminal-code-act`, Cap. C38 LFN 2004, as enacted (historical) |
| Source | PLAC C38.pdf, `trusted_secondary`, SHA-256 `42be35360b26…`, status `needs_review` |
| Run | `dfec47e4-0c73-4a2b-87ff-ead6fc149144`, waiting for review, parser `act-hierarchy-v3` |
| Pages | 32-207 included; 1-31 arrangement, 208 table and index, 209-214 subsidiary orders excluded |
| Backup | `backend/storage/statute-review/tier1-2026-11-05/app-before-tier1-v1.dump` (taken before this work; take a fresh one before compose) |

## Reconciliation

572 arrangement sections against 572 body sections: none missing, unexpected or repeated, no parser notes. Round 4's 571 distinct labels become 572 once the second arrangement "190" is read as 190A.

## Review counts

- Approved 1,460: 572 sections, 450 subsections, 364 paragraphs, 57 chapters, 8 parts, 1 schedule group, 8 enabling Act items.
- Rejected 16: sub-lists inside section 1 definitions, 8 numbered items and the 8 lettered items beneath them.
- Revised 160, with a specific reason on each. 100 of these remove headings or printed sub-headings from the text.
- Derived 14: subsections 295(4)-(6) and paragraphs 467(2)(g)-(q), which had merged into the item before them.
- Issues: 34 raised, all resolved. 11 blocking issues cleared by revision. No override used.

## Label decisions

- `l0A`, `l2A`, `l4A` are 10A, 12A, 14A: the sequence and body prove it.
- Second arrangement `190` is 190A: the body and the Federal sections table print 190A.
- Chapter 6 has no title in the arrangement; the body title is used.
- Stored numbers keep the print (`10A`); paths are lower case (`section10a`).

## Misprints corrected

- s.46 `habours` to `harbours`.
- s.89 `194l` to `1941`.
- s.98D `section 1 (i) or` to `section 1) or`: the bracket opened at "(within" never closes, and section 1 defines the term by numbered items, not a paragraph (i). **Please look at this one: it is the most interpretive correction.**
- ss.1, 86, 383, 459B capital `IS` to `is`.
- s.383 capital `If` to `if`.
- s.264 `Repeal ed` to `Repealed`.
- s.295 `(4)a` to `(4) a`.
- s.467(2) `(g a bank` to `(g) a bank`; `(I) a policy` to `(l) a policy`.
- s.495 `over ‐dri ves` to `over‐drives`.
- Spaces after hyphens in `dwelling‐ house` and `self‐ defence`.
- Notes: `L.N. 112 or 1964` to `of 1964`; `Cap. Tl4.` to `Cap. T14.`.
- Headings: `Perjury,` to `Perjury.`, `lnterfering` to `Interfering`, stray `(1)` markers on ss.236, 237, 243, 494.

## Kept as printed and flagged

- s.49D: the arrangement cites L.N. 112 of 1964, the body L.N. 121 of 1964.
- Body headings differ from the arrangement in about 20 places, for example `Personating` / `Impersonating` (ss.108, 109, 484-489), s.17 `punishments`, s.346 and s.334 `person` / `persons`. Arrangement headings are used, as the rules require.
- Part 5 reads `Offence against the person` (singular).
- p185 prints `1976 No. 27` where the same note elsewhere reads `1967 No. 27`. Kept, because the Act does not prove which year is right.
- Money: the text layer prints plain `N` and the word `naira`; the PDF is typed, so nothing was restored as ₦.
- LFN and amendment notes such as `[L.N. 112 of 1964.]` and `[Cap. P3.]` are kept.

## Unresolved, for your decision

- Enabling Act sections are stored as items of a separate group, so "section 2" stays unambiguous. They will cite as `Schedule Act → Schedule Item 2`. It works but reads badly; a one-line citation change would fix it.
- Printed `DIVISION` headings (Part 6) are removed from text and not modelled as structure.
- Copyright Act 2022 s.106(2) repeals Code ss.491-493. The retained text still shows them, so a provision notice is advisable.
- The Code applies as State law and several States have replaced it (Lagos 2015, Ekiti 2021, Edo 2022), so reader wording needs care.

## Checks

The text layer was compared with an independent macOS Vision pass in overlapping bands across all 176 pages; numbers and words agree apart from the items above. All 21 numeric mismatches were opened one by one: the rest are punctuation attached to a number, or subsection markers Vision dropped, which the sequence confirms. Regression tests in `backend/tests/legal/test_act_parser.py` pass.

Benchmark draft: `docs/criminal-code-act-retrieval-benchmark.json` (34 questions).
