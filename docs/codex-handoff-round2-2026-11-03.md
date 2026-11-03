# Codex handoff, round 2 (2026-11-03)

Review of round 1: the report's hashes, page counts and word counts match the saved files, and Codex stayed inside its lane (no database, backend, Compose or existing docs changed). Round 2 keeps the same lane rules and adds a narrow exception for new data files.

## Prompt to paste into Codex

```
Round 2. Same rules as round 1: no database, no Docker containers or
`docker compose`, no edits to existing files, no commits or branch changes, no
marking anything verified. Ask me before each download (filename, source, size).
Downloaded files go in their own new empty folder; run Python on them with -I
from outside that folder. Evidence only, with raw values retained and labelled.

Round 1 results I accepted: Land Use Act (22 pp, 52/52) and Labour Act (92/92)
are the best candidates. Do NOT touch the Nigeria Data Protection Act or the
Child's Rights Act; another agent is ingesting those.

TASK A: find replacement sources for the five gaps
Find the best candidate PDF for each and test it as in round 1 (size, pages,
words per page, section labels vs arrangement). For each, give the exact URL and
publisher, and say whether it is official (gazette, National Assembly, agency)
or secondary.
1. Employees' Compensation Act 2010 (the NSITF link was a 404).
2. Fundamental Rights (Enforcement Procedure) Rules 2009 (archive link was a
   bot-check page). Try the gazette copy at archive.gazettes.africa, Gazette
   No. 74 of 17 November 2009, and any court or NJC copy.
3. Penal Code (Northern States) Federal Provisions Act, Cap P3: the full text
   (the PLAC print page I saved only had sections 1-6 and 410-477). Try
   https://lawsofnigeria.placng.org/laws/P3.pdf and report whether it is complete
   (check that sections 7-409 exist, for example murder).
4. National Minimum Wage Act 2019 and the National Minimum Wage (Amendment)
   Act 2024: the signed texts, not the bill.
5. Evidence Act 2011 as a PDF with a text layer (the gazette copy is a scan), and
   the Evidence (Amendment) Act 2023.
Save into backend/storage/statute-review/source-tests/<short-name>/ with a
download.json as before.

TASK B: currency and amendment research (no downloads needed)
For each of these laws, list every amendment, repeal or replacement you can
find with a primary or near-primary source link (National Assembly, gazette,
agency, PLAC, Ministry of Justice): Land Use Act, Labour Act, Criminal Code Act,
Child's Rights Act 2003, Data Protection Act 2023, VAPP Act 2015, FCCPA 2018,
Cybercrimes Act 2015 (2024 amendment), Evidence Act 2011. For each state: what
you found, the source link, and your confidence. Say "none found" rather than
"none exist". Flag anything enacted or signed in 2025 or 2026.

TASK C: section-title catalogues for two Acts
Read backend/app/legal/data/police-act-2020-section-titles.json and
backend/app/legal/titles.py to learn the format, then create exactly two new
files in backend/app/legal/data/:
  land-use-act-1978-section-titles.json
  labour-act-section-titles.json
Take titles only from each source's own arrangement of sections. Include the
expected section count. Copy titles as printed; flag glitches (like "7 4.")
in a separate notes field without correcting them. Do not edit any other file in
backend/app/.

DELIVERABLE
Append one new report, docs/ocr-and-source-tests-round2-2026-11-03.md, with a
section per task. List every file you created at the end.
```

## What the lanes look like now

| Lane | Work | Touches |
|---|---|---|
| Claude | NDPA and Child's Rights Act review gates, then ingestion | database, admin, `backend/app/legal/act_parser.py`, checklist |
| Codex round 2 | A: replacement sources; B: amendment research; C: two title catalogues | `source-tests/` folders, new round 2 report, two new data files |

No overlap: Codex's only write inside `backend/app/` is two new files that neither the parser nor my runs read until a run is re-parsed.
