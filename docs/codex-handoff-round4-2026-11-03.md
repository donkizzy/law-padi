# Codex handoff, round 4 (2026-11-03)

Round 3 review: the report holds up. Five Acts are now in review (NDPA, Child's Rights, Land Use, Labour, Employees' Compensation), and nothing else in the checklist is clean enough to ingest. Round 4 widens the pool of ingestible sources and turns the damaged ones into reviewable evidence. It needs no new files from the user, though user-saved files (below) will unlock more.

## Lanes

| | Claude | Codex |
|---|---|---|
| Works on | Reviewing the five Acts in the admin UI with the user, parser fixes, `backend/app/`, database, Docker, retrieval benchmarks and topic-guide entries | New files only: evidence folders, title catalogues for sources that pass, one report |
| Never touches | Anything Codex creates this round until Codex hands it back | The database, Docker or `docker compose`, `backend/app/` code, tests, existing docs, existing catalogues, `.env`, commits and branches |

No task depends on another. Order by value: C, A, B, D, E.

## Prompt to paste into Codex

```
Round 4. Same rules as rounds 1 to 3: no database, no Docker containers or
`docker compose`, no edits to existing files, no commits or branch changes, no
marking anything verified. Ask me before each download (filename, source, size).
Every download goes straight into its own new empty folder: change the browser
download location first, and if a route can only save to Downloads, stop and ask
me instead of moving it afterwards. Run Python on downloaded files with -I from
outside their folder. Evidence only, raw values retained and labelled, no OCR
number repaired to fit a sequence.

Do NOT touch the NDPA, Child's Rights, Land Use, Labour or Employees'
Compensation material.

TASK A: Criminal Code scope map (highest value)
The retained PLAC C38 PDF mixes the enabling Act, the scheduled Code and
subsidiary material. Produce a page-range map: which PDF pages are (1) the Cap.
C38 enabling Act, (2) the Criminal Code proper (the Schedule), (3) Part or
Chapter divisions, (4) subsidiary or other instruments. For the Code proper,
give the printed arrangement pages, the section range, and the label table in
the Evidence-Act style (arrangement label, body label, raw reading, page). Keep
the four unresolved labels (`l0A`/`10A`, `l2A`/`12A`, `l4A`/`14A`, `190` versus
`190A`) as alternatives. If the Code proper has a complete arrangement and body,
create backend/app/legal/data/criminal-code-act-section-titles.json in the
labour-act catalogue style; if not, create nothing and say what is missing.

TASK B: FCCPA 2018 label table
For the official FCCPC 99-page PDF, produce the same 168-row label table
(arrangement label, body label, raw readings, page), using offline Apple Vision
and the native text layer. Record the duplicated page A23 (PDF 24-25) exactly as
printed. Create backend/app/legal/data/federal-competition-and-consumer-protection-act-2018-section-titles.json
only if all 168 arrangement titles are legible; otherwise create nothing and
list the unreadable rows.

TASK C: Minimum Wage Act 2019 OCR (ILO assent-bearing scan)
Run offline Apple Vision on the retained 14-page ILO scan (round 3 folder).
Report the arrangement labels and titles (expected 18), the body section labels,
the Schedule or table content, page by page raw text with line confidence, and
both raw date observations on PDF 14. Do not choose between the date readings.
Do not create a catalogue unless all 18 titles are legible; if they are, create
backend/app/legal/data/national-minimum-wage-act-2019-section-titles.json.

TASK D: VAPP Act 2015 and FRSC Act 2007 sources
1. Find a copy of the Violence Against Persons (Prohibition) Act 2015 that has
   its own arrangement of sections and shows assent (try the official gazette,
   National Assembly, NAPTIP or FIDA alternatives, Refworld, WIPO Lex).
2. Test the FRSC (Establishment) Act 2007 from the FRSC-hosted PDF and the
   judy.legal link in the checklist.
For each give URL, publisher, official or secondary, size, pages, words per
page, section labels versus arrangement, and anything that suggests it is a
bill or a draft. Ask before downloading.

TASK E: three more candidates
Find and test (text layer, section labels versus arrangement, assent
evidence) the best source for each of these: Companies and Allied Matters Act
2020, Copyright Act 2022, Nigeria Tax Act 2025. For Nigeria Tax Act 2025, also
report which older Acts it repeals or replaces and its commencement date, and
flag anything that affects other laws on our list. Ask before downloading.

DELIVERABLE
One new report: docs/ocr-and-source-tests-round4-2026-11-03.md, with a section
per task, a list of every file you created, and a clear statement of what you
did not verify. Stop when done.
```

## Files you can save from your own browser (optional, unlocks more)

These hosts block scripted downloads, so Codex cannot get them, but your browser can. Save each into its own new empty folder and tell Codex or me the path.

| File | Source | Unlocks |
|---|---|---|
| Evidence Act 2011, Gazette No. 80, 21 June 2011 | `archive.gazettes.africa/archive/ng/2011/ng-government-gazette-dated-2011-06-21-no-80.pdf` | A complete Evidence Act (the PLAC copy lacks sections 132-137) |
| 2019 wage Gazette No. 62, 23 April 2019 | `archive.gazettes.africa/archive/ng/2019/ng-government-gazette-supplement-dated-2019-04-23-no-62.pdf` | A gazetted Minimum Wage Act 2019 to compare with the ILO scan |
| Penal Code (Northern States) Federal Provisions Act, full PLAC page | `lawsofnigeria.placng.org` (Cap. P3) | The federal Penal Code |

## What each task unlocks

| Task | Unlocks |
|---|---|
| A | The Criminal Code, our top-priority law, with a defined ingest scope |
| B | The Competition and Consumer Protection Act from an official source |
| C | The Minimum Wage Act 2019 (OCR route), including the signed assent evidence |
| D | A usable VAPP source and a tested FRSC Act |
| E | Three high-demand Acts that may be cleaner than the current candidates |
