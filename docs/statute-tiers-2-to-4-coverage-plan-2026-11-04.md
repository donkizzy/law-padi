# Statute coverage plan: Tiers 2 to 4 (2026-11-04)

Reference list for what to ingest after Tier 1. Tier 1 is tracked in `statute-tier1-source-checklist-2026-11-03.md`; this file covers everything after it. The list was drafted from general knowledge with a June 2026 cutoff. **No source below has been found, downloaded or tested, and every currency note must be checked against NASS or the Federal Ministry of Justice before ingestion.** Nigeria passed several replacement Acts in 2025 and 2026.

"Total coverage" of Nigerian law (hundreds of Acts plus 36 states) is not achievable at once. The target is the roughly 15 to 20 laws people ask about most, with everything else labelled "not yet covered" in the UI. Keep the "As enacted, may have been amended" label on every Act.

Selection rule: prefer born-digital sources (NASS, agency or gazette text PDFs) over scans. OCR cost and number misreads (`48` read as `4g`) are what slowed ACJA and the Police Act.

## Status of the Tier 1 items that appear below

| Law | Tier in this plan | State on 2026-11-04 |
|---|---|---|
| Nigeria Tax Act 2025 | Tier 2, item 12 | In review (run `8bd11152`), 202 of 202 sections |
| Copyright Act 2022 | Tier 3, item 20 | In review (run `470b12cb`), 109 of 109 sections |
| CAMA 2020 | Tier 2, item 11 | Source tested by Codex; page 91 is mirrored in the source; not ingested |

## Tier 2: business, money and family

| # | Law | Notes for the source search |
|---|-----|-----------------------------|
| 11 | Companies and Allied Matters Act (CAMA) 2020 | Large. One mirrored page (91) in the tested source. |
| 12 | Tax laws: Nigeria Tax Act 2025, Nigeria Tax Administration Act 2025, and the revenue-body Acts effective 1 January 2026 | They replaced the old CITA, PITA, VAT and CGT Acts, so **do not ingest the old ones**. The Tax Act (already in review) amends the Cybercrimes Act (s.196(14)) and repeals other Acts; record each in the checklist. |
| 13 | Pension Reform Act 2014 | |
| 14 | Matrimonial Causes Act and Marriage Act | Cap M7 and M6 LFN 2004. Both are 2004 compilations. |
| 15 | Freedom of Information Act 2011 | |
| 16 | Money Laundering (Prevention and Prohibition) Act 2022 and Terrorism (Prevention and Prohibition) Act 2022 | Two separate Acts. |
| 17 | Electoral Act | Believed to have been replaced in 2026. Confirm which Act is current before sourcing; Electoral Act 2022 may now be historical. |
| 18 | Banks and Other Financial Institutions Act (BOFIA) 2020 and Investments and Securities Act 2025 | Two separate Acts. |

## Tier 3: specialist and procedural

| # | Law | Notes |
|---|-----|-------|
| 19 | Immigration Act 2015 | |
| 20 | Copyright Act 2022, Trade Marks Act, Patents and Designs Act | Copyright is already in review. Section 106(2) of the Copyright Act repeals Criminal Code sections 491-493 and Penal Code sections 426-427. |
| 21 | Arbitration and Mediation Act 2023 | |
| 22 | Sheriffs and Civil Process Act, Legal Practitioners Act, Federal High Court (Civil Procedure) Rules | Rules are court instruments, not Acts. |
| 23 | EFCC Act 2004, ICPC Act 2000, Public Procurement Act 2007 | |
| 24 | Petroleum Industry Act 2021, Electricity Act 2023 | |
| 25 | Firearms Act, Armed Forces Act, Anti-Torture Act 2017, Discrimination Against Persons with Disabilities Act 2018 | |

## Tier 4: later

| # | Item | Notes |
|---|------|-------|
| 26 | Constitution alteration Acts | Our Constitution text is as enacted. Folding in the alterations gives "the law as it is today" and is hard. |
| 27 | State laws | Most useful first: Lagos (Tenancy Law 2011, Criminal Law 2011, Land laws), then Abuja and other large states. |
| 28 | Case law | A separate and much larger project. |

## UI honesty rules

- Say plainly what is not covered: state laws and case law are out of scope for now.
- Nothing is "current consolidated law" unless checked against the latest amendments.
- Tax law: only the 2025 Acts, never the old CITA, PITA, VAT or CGT Acts.

## Prompt for Codex (Tiers 2 and 3 source discovery)

Ask Codex to cover one tier at a time. Paste the block below as is, then say which tier. Keep Tier 1 laws off its list because Claude is still processing them.

```
Round 5: statute source discovery for Tier 2, then Tier 3, from
docs/statute-tiers-2-to-4-coverage-plan-2026-11-04.md. Same rules as rounds 1 to
4: no database, no Docker containers or `docker compose`, no edits to existing
files, no commits or branch changes, no marking anything verified. Ask me before
each download (filename, source, size). Every download goes straight into its own
new empty folder under backend/storage/statute-review/source-tests/round5-<law>/:
change the browser download location first, and if a route can only save to
Downloads, stop and ask me instead of moving it afterwards. Run Python on
downloaded files with -I from outside their folder. Evidence only, raw values
retained and labelled, no OCR number repaired to fit a sequence.

Do NOT touch any Tier 1 material or the Nigeria Tax Act 2025 and Copyright Act
2022 runs. Claude is still processing them.

SCOPE: Tier 2 items 11 to 18 first, in that order. Do not start Tier 3 until I
say so. Item 12: do not source the old CITA, PITA, VAT or CGT Acts. Item 17: first
establish which Electoral Act is current in 2026 and tell me before downloading
anything. Every currency claim in the plan is from memory with a June 2026 cutoff,
so check each law's current status yourself and report where it differs.

For EACH law:
1. Find the best source, in this order: official gazette, National Assembly or the
   issuing agency, then PLAC (lawsofnigeria.placng.org) as trusted_secondary.
   Record URL, publisher, official or secondary, and whether it is a bill or the
   assented Act. Show assent evidence if the file has any.
2. Ask me, then download and test it: pages, size, SHA-256, words per page, text
   layer yes or no. Without a text layer, run offline Apple Vision as in earlier
   rounds.
3. Report section labels in the arrangement versus the body with raw readings and
   pages. Keep every discrepancy as an alternative. Repair nothing.
4. Say whether it is as-enacted or consolidated, and name any later amendment,
   repeal or replacement. Flag overlaps with laws already on our list.
5. Create backend/app/legal/data/<law-slug>-section-titles.json in the existing
   catalogue style ONLY if every arrangement title is legible and the count
   matches the body. Otherwise create nothing and list the missing rows.
6. Rate it: ready to ingest, needs OCR route, or blocked (say what is missing and,
   if I can fix it, what to save from my browser).

Finish the first three laws fully before starting the rest.

DELIVERABLE
One new report: docs/ocr-and-source-tests-round5-2026-11-04.md with a section per
law, a one-line ready/OCR/blocked rating at the top for each, a list of every file
you created, and a clear statement of what you did not verify. Stop when done.
```
