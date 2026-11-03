# Codex handoff, round 3 (2026-11-03)

Round 2 review: the report's findings hold up (see the review notes in the chat). Its title catalogues for Land Use and Labour matched the parses (52 of 52 and 92 of 92) and are committed. Round 3 prepares the next ingestions and closes the biggest evidence gaps.

## Lanes

| | Claude | Codex |
|---|---|---|
| Works on | Registering and ingesting the Employees' Compensation Act 2010 from the retained iGuides PDF (`round2-eca-2010-iguides`), parser fixes, `backend/app/`, database and Docker | New files only: title catalogues, evidence folders, one report |
| Never touches | Anything Codex creates this round until Codex hands it back | The database, Docker or `docker compose`, `backend/app/` code, tests, existing docs, existing catalogues, `.env`, commits and branches |

Task A is the only task Claude is waiting for. Do it first.

## Prompt to paste into Codex

```
Round 3. Same rules as rounds 1 and 2: no database, no Docker containers or
`docker compose`, no edits to existing files, no commits or branch changes, no
marking anything verified. Ask me before each download (filename, source, size).
Downloaded files go in their own new empty folder; run Python on them with -I
from outside that folder. Evidence only, raw values retained and labelled, no
OCR number repaired to fit a sequence.

Do NOT touch the NDPA, Child's Rights Act, Land Use or Labour material.

TASK A (do first; another agent is waiting for it): title catalogue for the
Employees' Compensation Act 2010
Create exactly one new file:
backend/app/legal/data/employees-compensation-act-2010-section-titles.json
Use the retained PDF in
backend/storage/statute-review/source-tests/round2-eca-2010-iguides/ (its own
arrangement is PDF pages 3-6, 74 sections). Follow the same contract and style
as backend/app/legal/data/labour-act-section-titles.json (source,
expected_section_count, chapters, parts, sections, review_status: needs_review,
notes). Record the source SHA-256. The instrument slug will be
employees-compensation-act-2010. Validate by loading it through the existing
catalogue_titles function read-only, as in round 2. Tell me as soon as it is
written; do not wait for the other tasks.

TASK B: title catalogues for other usable Acts
For each of the Criminal Code Act (Cap C38), the Violence Against Persons
(Prohibition) Act 2015 and the Federal Competition and Consumer Protection Act
2018 that your round 1 report rated usable, create a catalogue the same way, in
backend/app/legal/data/. Slugs: criminal-code-act, violence-against-persons-prohibition-act-2015,
federal-competition-and-consumer-protection-act-2018. For any that you rated
not usable (wrong edition, a bill, text layer unreliable), create nothing and
say why in the report. Part and chapter titles go in the parts/chapters maps
only if they are printed in that source's arrangement.

TASK C: Evidence Act 2011 extraction evidence
The retained PLAC copy has a text layer with heavy OCR damage (215 of 259
arrangement labels and 222 of 259 body labels captured). Re-extract it with the
offline tools you used before (Apple Vision, and Tesseract only if it can run
without Docker or network), keep the originals, and report for each of the 259
sections: arrangement label found, body label found, and the raw reading when it
differs (for example `1O3` or `l5`). List only labels you could not read at
all. Do not decide which reading is right.

TASK D: Cybercrimes Act amendment map
From the retained round 1 OCR of the ONSA booklet, list each of the 2024
amendment clauses (sections 17, 21, 22, 24, 27, 30, 37, 38, 41, 44, 48) with
the booklet page, the raw OCR text of the clause, and which principal-Act
section it changes. Also report where the principal Act's own arrangement of
sections sits in the booklet (page range) and whether it is legible. Do not
produce a consolidated text.

TASK E: signed minimum wage text
Find a signed or gazetted copy of the National Minimum Wage Act 2019 and of the
National Minimum Wage (Amendment) Act 2024. Candidates: the Federal Government
Printer or gazette sites, the National Assembly website, the Federal Ministry of
Labour, the ILO NATLEX record (it returned 403; find another route), and
LawNigeria. For each candidate give the exact URL, publisher, official or
secondary, and whether it shows assent. Ask before downloading any of them.

DELIVERABLE
One new report: docs/ocr-and-source-tests-round3-2026-11-03.md, with a section
per task, a list of every file you created, and a clear statement of what you
did not verify. Stop when done.
```

## What each task unlocks

| Task | Unlocks |
|---|---|
| A | ECA ingestion (Claude starts as soon as the file exists) |
| B | Ingesting Criminal Code, VAPP and FCCPA with proper headings |
| C | Deciding whether the Evidence Act can be ingested or needs OCR review |
| D | Handling the Cybercrimes amendment without guessing |
| E | A real source for the minimum wage laws |
