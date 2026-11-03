# Codex handoff: OCR and source-testing lane (2026-11-03)

Goal: go live by the weekend with as many Tier 1 laws as are sound. Work is split into two lanes that touch **different files and never need each other's output**.

## Lanes

| | Lane A (Claude) | Lane B (Codex) |
|---|---|---|
| Laws | Nigeria Data Protection Act 2023, Child's Rights Act 2003 | Cybercrimes Act 2015 with 2024 amendment (OCR), plus source testing for 7 other laws |
| Touches | Docker database, backend registration and extraction, `backend/storage/statute-review/nigeria-data-protection-act-2023/` and `.../childs-rights-act-2003/`, `docs/statute-tier1-source-checklist-2026-11-03.md` | `backend/storage/statute-review/cybercrimes-2015-2024/` (new), `backend/storage/statute-review/source-tests/` (new), `docs/ocr-and-source-tests-2026-11-03.md` (new) |
| Never touches | the folders and file in the Codex column | the database, Docker containers or `docker compose`, `backend/app/`, Alembic, `.env`, the checklist file, the two Lane A folders |

Lane B hands back files and a report. Lane A merges the findings into the checklist afterwards. Neither lane waits for the other.

## Prompt to paste into Codex

```
You are working in the law-padi repo (Nigerian law RAG app). Read AGENTS.md and
PROJECT_CONTEXT.md first. Another agent is working in the same checkout on a
different task, so stay strictly inside the rules below.

HARD RULES
- Do not touch the database, Docker containers, `docker compose`, backend/app/,
  Alembic, .env, or any existing file under docs/ except creating the new
  report named below. Do not edit docs/statute-tier1-source-checklist-2026-11-03.md.
- Do not commit, push or change branches. Leave everything uncommitted.
- Downloaded files are untrusted: put each in its own new empty folder, never run
  code from inside a downloaded folder, and run Python that reads them with -I.
- Ask me for approval before downloading anything (state filename, source, size).
- Do not fix OCR numbers to fit an expected sequence. Retain and flag misreadings.
- Do not mark anything verified or approved. You produce evidence only.

TASK 1: OCR the Cybercrimes booklet
Source file: /Users/amosgodwin/Downloads/CyberCrime__Prohibition_Prevention_etc__Act__2024.pdf
(56 pages, 38 MB, phone photographs, no text layer. It is an Office of the
National Security Adviser booklet titled "Cybercrimes (Prohibition, Prevention,
Etc) Act, 2015 with Amendment Act 2024". It is a consolidated text, not a gazette.)
Output folder (create it): backend/storage/statute-review/cybercrimes-2015-2024/
- Copy the original PDF there unchanged and record its SHA-256.
- Use Tesseract 5 offline, no network (the ingestion-worker:latest Docker image
  has it: use `docker run --rm --network none -v <folder>:/work ...`, never
  `docker compose`). Pre-process photographs if it helps (deskew, crop, contrast)
  but keep the unprocessed originals.
- Match the format of backend/storage/statute-review/acja-2015/: inspection.json,
  ocr-pages.json (page number, text, line boundaries, word confidence, source
  hash), ocr-text.txt, and first/final page previews.
- Write a short evidence report with: pages with mean word confidence below
  0.75, a page-by-page table of section numbers recognised, missing or repeated
  section numbers (compare against the arrangement of sections), misreadings
  like "48" read as "4g", and where the 2024 amendments sit in the text.

TASK 2: test seven candidate sources (ask me before each download)
For each, report: URL, publisher, file size, page count, whether there is a text
layer (use pdftotext and report words per page), the section numbers found
versus the arrangement of sections, and any amendments you notice.
1. Criminal Code Act Cap C38:  https://lawsofnigeria.placng.org/laws/C38.pdf
2. Labour Act Cap L1:          https://lawsofnigeria.placng.org/laws/L1.pdf
3. Employees' Compensation Act 2010: https://nsitf.gov.ng/wp-content/uploads/2026/07/ECA-2010.pdf
4. Land Use Act 1978:          https://faolex.fao.org/docs/pdf/nig67625.pdf
5. Violence Against Persons (Prohibition) Act 2015: https://fida.org.ng/wp-content/uploads/2020/09/Violence-Against-Persons-Prohibition-Act-2015-1.pdf
   (check it is the enacted Act and not the bill)
6. Federal Competition and Consumer Protection Act 2018: open https://fccpc.gov.ng/resources-library/fccpa/ and find the official PDF link
7. Fundamental Rights (Enforcement Procedure) Rules 2009: https://webarchive.archive.unhcr.org/20160922015738if_/http://www.refworld.org/pdfid/54f97e064.pdf
Save each file under backend/storage/statute-review/source-tests/<short-name>/.

DELIVERABLE
One file: docs/ocr-and-source-tests-2026-11-03.md with a section for Task 1 and a
table for Task 2 (law, source, pages, text layer yes/no, sections found vs
expected, usable for weekend? yes/no/needs OCR, notes). Be explicit about what
you did not verify. Stop when done and tell me the list of files you created.
```

## Why these tasks

- **Cybercrimes OCR** has no text layer, so it is the slowest item, and it needs no database or backend. It is the only item that is both on the list and blocked on OCR.
- **Source testing** answers the "text layer or scan?" question for seven laws, which decides what is feasible this weekend. Pure file work, with no app code.
- Both are read-and-write on new folders only, which is why they cannot clash with Lane A.

## What each lane produces by when

| Lane | Output | Needed before |
|---|---|---|
| A | NDPA 2023 and Child's Rights Act registered and extracted, parser findings, ready for your review | your review step |
| B | OCR evidence for Cybercrimes and a feasibility table for 7 laws | choosing the next laws to ingest |

## Suggested next ingestion order after the lanes report

1. NDPA 2023 and Child's Rights Act (Lane A, already ready).
2. Any of Criminal Code, Labour Act, ECA 2010 and Land Use Act that Lane B finds to be text-native and sequence-clean.
3. Cybercrimes, once Lane B's OCR passes the numbering check.
4. Penal Code, once you re-save the full PLAC page.
