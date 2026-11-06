# National Minimum Wage Act 2019 and 2024 amendment: review report (5 November 2026)

Approved by the user on 5 November 2026. Source verified, materialised, embedded (Recall@10 1.0 for both) and included in `composite-2026-11-05-fifteen-laws`, which is ready to publish.

| Item | 2019 Act | 2024 amendment |
|---|---|---|
| Instrument | `national-minimum-wage-act-2019` | `national-minimum-wage-amendment-act-2024` |
| Source | ILO NATLEX copy of the enrolled Act, signed clerk's certificate and assent | Lexark retype, blank signature lines (accepted by the user on 5 November 2026) |
| Status | `trusted_secondary`, `needs_review` | `trusted_secondary`, `needs_review` |
| SHA-256 | `6d624addf4e9…` | `9414ef03137a…` |
| Run | `cc9f9fbc-48a2-42ff-8a62-38dafe95f1de` | `52b969ba-9536-4100-81fa-8944bb1f68b5` |
| Sections | 18 of 18 | 3 of 3 |
| Approved | 83 | 5 |
| Rejected | 0 | 0 |
| Revised | 20 | 0 |
| Blocking issues | 1 (page boundaries), cleared by page confirmation | 1 (page boundaries), cleared by page confirmation |

No override was used. Two earlier runs were cancelled and retained: one for the 2019 Act and one for the 2024 amendment, after parser and marker fixes.

## How the text was read

The 2019 file is a scan with handwritten section numbers. 34 label, marker and clipped-line corrections were made before parsing and are logged in `backend/storage/statute-review/tier1-2026-11-05/min-wage-2019/label-corrections.json`. Three Vision variants were compared on every page. The 2024 text layer agrees with an independent Vision pass word for word.

## Corrections (2019)

- Struck naira sign restored: ₦30,000.00 (s.3(1), read as `130,000.00`), ₦75,000.00 and ₦10,000.00 (s.10(2)), ₦250,000.00 (s.15).
- Words clipped at the column edge restored in ss.1 and 11(4).
- OCR slips: `Niggria`, `offenice`, `ayment`, `authorişed`, `not. later`, `ofthe`.
- Margin notes run into the text removed in ss.8 and 12.

## Kept as printed and flagged

- s.17 "wage": "by virtue of a `contact`" (read as contract). The Act does not prove it, so the print stands.
- s.17 "worker": "whether contract is for manual labour, clerical work, is expressed or implied" is garbled in print.
- s.9(2)(a) `offenders monthly wage`, s.14(3) `defense`, s.4(2) `Incomes and Wage` (elsewhere `Wages`).
- Dates: the assent line prints March, crossed out by hand and replaced with April, day 18. The clerk's certificate is 26 March. The commencement bracket is blank in both Acts, so 18 April 2019 and 29 July 2024 are stored as working dates.
- The 2024 text still says "A Bill" and its assent is typed. The publisher's editor's note was excluded.

## Unresolved, for your decision

s.3 of the 2019 Act states ₦30,000 and a five-year review, both replaced in 2024. A reader who lands on s.3 alone would be misled, so a notice on that section is advisable before publishing.

Benchmark draft: `docs/national-minimum-wage-retrieval-benchmark.json` (30 questions).
