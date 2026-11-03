# Tier 1 statute source checklist (2026-11-03)

Candidate laws to ingest after the Constitution, ACJA 2015 and Police Act 2020. Source links were found by web search on 2026-11-03. **No PDF has been downloaded or opened, so "text-native?" is untested for every row, and no link has been checked against an official copy.** Currency notes come from general knowledge with a June 2026 cutoff.

Source order of preference: official gazette, National Assembly (NASS) or the issuing agency, then PLAC (`lawsofnigeria.placng.org`) as `trusted_secondary`, matching how ACJA and the Police Act were recorded.

Lesson from ACJA and the Police Act: scanned PDFs needed OCR and failed section-number reconciliation (`48` read as `4g`). Run `pdftotext` on each file before committing to an Act. A scan returns little or no text and will cost days.

## Checklist

"LFN 2004" copies are as-enacted in 2004 and omit later amendments. Mark them historical.

| # | Law | Best source found | Fallback | Currency / caveat | Text-native? |
|---|-----|-------------------|----------|-------------------|--------------|
| 1a | Criminal Code Act (Cap C38 LFN 2004) | [PLAC C38.pdf](https://lawsofnigeria.placng.org/laws/C38.pdf) | [LawNigeria mirror](https://lawnigeria.com/2025/01/28/criminal-code-act/) | 2004 numbering. Older 1990 edition (Cap 77) numbers differently, so avoid it. | untested |
| 1b | Penal Code (northern states) | not found | try PLAC for the federal Penal Code Act (likely Cap P3) | Applies by state adoption. Needs a separate search and a labelling decision. | n/a |
| 2 | Evidence Act 2011 | [Gazette No. 80, 21 Jun 2011](https://archive.gazettes.africa/archive/ng/2011/ng-government-gazette-dated-2011-06-21-no-80.pdf) | [Refworld](https://www.refworld.org/node/104226), [judy.legal](https://www.judy.legal/legislation/akn/ng/act/2011/18) | Gazette is a scan, so likely needs OCR. An Evidence (Amendment) Act 2023 exists. | probably no |
| 3a | Labour Act (Cap L1 LFN 2004) | [PLAC L1.pdf](https://lawsofnigeria.placng.org/laws/L1.pdf) | [National Library repository](https://nigeriareposit.nln.gov.ng/bitstreams/3fe91e63-2ec7-43ea-a8e0-f72b49f9ef7f/download) (scan) | Snippet showed the arrangement only. A 2024 amendment bill is pending. | untested |
| 3b | National Minimum Wage Act 2019, amended 2024 | [PLAC bill PDF](https://placng.org/i/wp-content/uploads/2024/07/National-Minimum-Wage-Amendment-Bill-2024.pdf) is the **bill**, not the Act | [LawNigeria](https://lawnigeria.com/2025/10/06/national-minimum-wage-amendment-act-2024/) (paid, ₦1,500) | Signed 29 Jul 2024. Wage reportedly ₦70,000 and review every 3 years, from secondary sources. **No free signed text found.** | n/a |
| 3c | Employees' Compensation Act 2010 | [NSITF ECA-2010.pdf](https://nsitf.gov.ng/wp-content/uploads/2026/07/ECA-2010.pdf) (agency-hosted gazette text) | [judy.legal](https://www.judy.legal/legislation/akn/ng/act/2019/eca) | Assented 17 Dec 2010. | untested |
| 4 | Land Use Act 1978 | [PLAC view2.php?sn=228](https://placng.org/lawsofnigeria/view2.php?sn=228) (HTML) | [FAOLEX PDF](https://faolex.fao.org/docs/pdf/nig67625.pdf) | Not confirmed whether either includes amendments. Repeal is being debated, so recheck before release. | untested |
| 5 | Fundamental Rights (Enforcement Procedure) Rules 2009 | [Refworld archive PDF](https://webarchive.archive.unhcr.org/20160922015738if_/http://www.refworld.org/pdfid/54f97e064.pdf) | [Gazette No. 74](https://archive.gazettes.africa/archive/ng/2009/ng-government-gazette-dated-2009-11-17-no-74.pdf) (scan, S.I. 1 of 2009) | Court rules, not an Act. Check whether it is still unamended. | archive copy maybe |
| 6 | Nigeria Data Protection Act 2023 | [KPMG-hosted PDF](https://assets.kpmg.com/content/dam/kpmg/ng/pdf/nigeria-data-protection-act2023.pdf) | none official found; check the NDPC website | **Labelled a Bill**, so confirm it matches the signed Act. Signed June 2023 (12 or 14 June, sources disagree). GAID 2025 is a directive and a separate document. | likely yes |
| 7 | Cybercrimes Act 2015, amended 2024 | [judy.legal 2015 Act](https://www.judy.legal/legislation/akn/ng/act/2015/17) and [2024 amendment](https://www.judy.legal/legislation/akn/ng/act/2024/cppa) | none | Amendment assented 28 Feb 2024 and changes 12 sections. Need the amendment folded in. No free PDF found. | web page |
| 8a | Violence Against Persons (Prohibition) Act 2015 | [FIDA PDF](https://fida.org.ng/wp-content/uploads/2020/09/Violence-Against-Persons-Prohibition-Act-2015-1.pdf) | [Refworld](https://www.refworld.org/docid/556d5eb14.html) | Check the FIDA file is the enacted Act, not the bill. Assented 25 May 2015. | untested |
| 8b | Child's Rights Act 2003 | not found | try PLAC (likely Cap C50) | Federal. States must adopt it separately. | n/a |
| 9 | Federal Competition and Consumer Protection Act 2018 | [FCCPC resources page](https://fccpc.gov.ng/resources-library/fccpa/) | none | Open the page for a download link, since none was visible in the search result. Official source. | untested |
| 10 | FRSC (Establishment) Act 2007 | [FRSC-hosted PDF](https://old.frsc.gov.ng/FRSCACT2007.pdf) | [judy.legal](https://www.judy.legal/legislation/akn/ng/act/2007/22) | Official title is "Federal Road Safety **Commission** (Establishment) Act". The snippet showed OCR-garbled text, so this is likely a scan. The Traffic Regulations are a separate document and not found. | probably no |

## Files supplied and tested (2026-11-03)

Tested with `pdfinfo` and `pdftotext` on the PDFs in `~/Downloads`. Section-continuity checks are rough text heuristics, not the ingestion reconciliation.

| Law | File | Result |
|-----|------|--------|
| NDPA 2023 | `Nigeria_Data_Protection_Act_2023.pdf` from [cert.gov.ng](https://cert.gov.ng/ngcert/resources/Nigeria_Data_Protection_Act_2023.pdf) | **Usable.** Text-native, 43 pages, about 14,500 words. It is the Federal Government Extraordinary Gazette No. 119 of 1 July 2023 (Act No. 37, pages A719–758), with assent on 5 June 2023. That settles the 12 vs 14 June question and replaces the KPMG copy as the source. The PDF was made with "Print To PDF", so layout is two-column in places and section reconciliation is untested. The gazette header misprints "2022 No. 37". Status: `official` source, hosted by a government site. |
| Minimum Wage 2024 amendment | `National-Minimum-Wage-Amendment-Bill-2024.pdf` from PLAC | **Not ingestible as law.** It is a 3-page, 258-word **bill** (explanatory memorandum plus 3 clauses), not the signed Act, and it does not contain the 2019 principal Act. The file's internal title says "Nigeria Police Act, 2020 Act (Amendment) Bill", a leftover from a template. Treat as a note only. Still need the signed 2024 Act and the 2019 Act. |
| Cybercrimes Act 2015 with 2024 amendment | `CyberCrime__Prohibition_Prevention_etc__Act__2024.pdf` from [cert.gov.ng](https://cert.gov.ng/ngcert/resources/CyberCrime__Prohibition_Prevention_etc__Act__2024.pdf) | **Needs OCR.** 56 pages, 38 MB, no text layer, and the pages are phone photographs. Page 1 shows an Office of the National Security Adviser (ONSA) booklet titled "Cybercrimes (Prohibition, Prevention, Etc) Act, 2015 with Amendment Act 2024". Good news: it is consolidated (principal Act plus amendment) and from a government source. Bad news: it is a booklet, not a gazette, so it is not a certified text, and camera photos will have the same OCR number-misreading risk as ACJA and the Police Act. Tesseract is not installed in this shell. |
| Penal Code (Northern States) Federal Provisions Act, Cap P3 | `penal Code.pdf` from [PLAC print.php?sn=432](https://lawsofnigeria.placng.org/print.php?sn=432) | **Incomplete, do not ingest this file.** Text-native, but it contains only sections 1–6 of the Act and sections 410–477 of the Schedule. Sections 7–409 are missing (the word "murder" does not appear once). The PLAC print page evidently did not load fully when it was saved. Re-save it, or try the PLAC `laws/P3.pdf` pattern. |
| Child's Rights Act 2003 | `the Child’s Rights Act.pdf` from [PLAC C50.pdf](https://placng.org/lawsofnigeria/laws/C50.pdf) | **Usable.** Text-native, 265 pages, about 90,000 words. All 278 sections are present in order in my rough check, plus 11 schedules and forms. The arrangement of sections is repeated before the body, and one Part heading in the arrangement is misprinted ("PART V" where X is expected), so use the body. Federal Act only. Each state must adopt it separately, and the UI should say that. Source is PLAC, so `trusted_secondary`. |

| Nigeria Highway Code (your Source 6) | `nigeria-highway-code.pdf` from [highwaycode.com.ng](https://www.highwaycode.com.ng/uploads/3/2/9/2/3292309/nigeria-highway-code.pdf) | **Text-native but not an official source. Do not ingest as law.** 95 pages, about 19,000 words, made in Word 2013. The cover credits an individual, "Arowolo Philip Olakunle", of a church group (Royal Shepherds, Kwara Command), not the FRSC. The text has typos (for example "S.1D(4)" for "S.10(4)") and calls the Act "cap 141". It is a study guide that cites FRSC Act section numbers. The official FRSC Highway Code, or the FRSC Act and Traffic Regulations, are the sources to use. |

### Section reconciliation (2026-11-03, text heuristics on `pdftotext` output)

- **NDPA 2023:** 66 of 66 sections found in the body, in order, with the Schedule present. The arrangement lists 66 sections. My first pass reported 18 missing; that was a regex miss on the margin-note layout, and a looser match found all 66.
- **Child's Rights Act 2003:** 278 of 278 sections found in the body before the schedules, with none missing. The same section-number layouts appear in the arrangement and the body, so the body is the reference.
- Not yet checked: section titles against the arrangement, subsection and paragraph structure, and page-boundary breaks. Those happen in the project's ingestion run, not in this script.

### Source tests by Codex (2026-11-03; full evidence in `docs/ocr-and-source-tests-2026-11-03.md`)

I spot-checked these against the saved files: SHA-256 hashes, page counts and word counts for Land Use, Labour, Criminal Code and FCCPA match the report. Nothing here is verified legal text.

| Law | Result | Usable for weekend? |
|-----|--------|---------------------|
| Land Use Act (FAOLEX) | 22 pages, text layer, all 52 sections in the arrangement and the body | **Yes, best candidate** |
| Labour Act (PLAC L1) | 80 pages, text layer, 92 of 92 headings in arrangement and body (three label glitches such as `7 4.` for 74, retained) | **Yes** |
| Criminal Code (PLAC C38) | 214 pages, text layer, 572 headings each in arrangement and body, four label discrepancies (arrangement `190` vs body `190A` is a source mismatch) | Needs review decisions; large |
| FCCPA | Official FCCPC PDF at `fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf`. 99 pages, but the text layer is badly corrupted. OCR found 157 of 168 section labels; pages 24 and 25 repeat the same gazette page | No: heavy OCR and review |
| VAPP 2015 (FIDA) | Scan, no text layer. 48 body labels found by OCR. The copy says "A Bill" but has a signed assent block dated 25 May 2015 | Not yet: identity question |
| Employees' Compensation Act | NSITF link returned HTTP 404 | No: need a new source |
| FREP Rules 2009 | Archive link returned a bot-check page, not a PDF | No: need a new source |
| Cybercrimes 2015 + 2024 | OCR done. It is the 2015 Act plus a **separate** 2024 amendment Act (pages 48–56), **not** an integrated text, so my earlier "consolidated" was wrong. The principal arrangement beyond section 24 is missing | Not yet |

### Ingestion status (2026-11-03, local Docker database)

Earlier attempts (runs `3df501f5`, `f420d6be`, `04f9665d`, `2cd8f736`) were cancelled: the first excluded the arrangement pages the Act parser needs, and the next two ran on the old parser. The parser was then fixed (`act-hierarchy-v3`, see below) and both Acts were re-run. Pages were confirmed through the page-selection service as the superuser.

| Act | Run | Pages included | Sections parsed | Expected | Arrangement vs body |
|-----|-----|----------------|-----------------|----------|---------------------|
| Nigeria Data Protection Act 2023 | `6b19c8cb-51d4-4330-be73-35f70c456525` | 3–42 (1–2 and 43 excluded) | 66 (+ 161 subsections, 258 paragraphs, 11 parts, 18 schedule items) | 66 | no missing, no unexpected |
| Child's Rights Act 2003 | `a6caf8f1-207f-43ec-827e-4eb8226c9701` | 1–265 (all) | 278 (+ 881 subsections, 1,065 paragraphs, 43 parts, 11 schedules, 139 schedule items) | 278 | no missing, no unexpected |

Land Use Act and Labour Act (registered from Codex's saved PDFs, copied to a clean folder first):

| Act | Run | Result |
|-----|-----|--------|
| Land Use Act 1978 | `f1b8147d-9c41-430c-997b-5844b1e26eea` | **No blocking issues.** All 52 sections parsed (93 subsections, 96 paragraphs, 8 parts); arrangement and body match; 6 non-blocking low-confidence flags. Source defect for the reviewer: the FAOLEX text layer repeats a line in section 51 ("includes the planting of any crops of economic value;"). Source is a secondary copy of Cap. L5 LFN 2004, so the text is as compiled in 2004. A first Land Use run exposed two more parser faults (the title block after the arrangement was read into section 52's heading; "SUBSIDIARY LEGISLATION" trailer was in the section text), fixed in the working tree, not yet committed. |
| Labour Act (Cap L1) | `3f456d7c-3caf-4870-ac9f-a6692a69576f` (pages 1-55 included, 56-80 subsidiary legislation excluded) | **Waiting for review, 92 of 92 sections**, 4 parts, 6 schedule items, arrangement and body match. First attempt `c8aebfab` failed the static scanner on a false positive: `/AA` bytes inside compressed stream data (`/AA` then `0xB2`). The scanner now requires a whole PDF name (`pdf-static-safety-v1`, boundary rule; tests added), and the file passes. A second run `4a5db45a` was cancelled because the parser started the body late (the text layer prints section 1's first subsection as `(I)`, so sections 1-5 were read as arrangement repeats) and skipped `7 4.` for section 74. Parser now accepts `(I)`/`(l)` only to find the body start and reads a split two-digit number only when it is the next section in sequence; each reading is listed as a parser note (`1 6.`, `4 7 _`, `7 4.`). Blocking issues still open: 42 source_span_coverage, 17 unbalanced_punctuation, arrangement gate (open because those 3 notes are listed). Subsection `(I)` in sections where it is printed is not split; text kept whole. Edition is Cap. L1 LFN 2004, not checked for later amendments. |

Both runs are `waiting_for_review`. Nothing is approved, embedded or published, and both sources are still `needs_review`. Open blocking review issues for a person to resolve against the PDFs:
- **NDPA:** 16 "source span coverage" issues (text coverage is 1.0 but precision is about 0.4–0.5, because margin notes sit in the coordinate spans), plus the arrangement-reconciliation gate, which stays open while the parser reports "Repeated section/item marker on page 42: 17" (a wrapped line in the Schedule).
- **Child's Rights Act:** 9 unbalanced-punctuation issues (sections 61, 65 and schedule items; check whether they are source typos) and the arrangement-reconciliation gate, which stays open while the parser reports the notes below.
  - Section "163 (1) (b)" wrapped inside section 173 was kept as text, not read as a new section.
  - Repeated numbering inside schedule forms.
  - The source spells "EIGHT SCHEDULE"; it is read as the eighth schedule and the source heading is retained.

Parser changes (`backend/app/legal/act_parser.py`, `backend/app/legal/parser.py`, regression tests in `backend/tests/legal/test_act_parser.py`):
- Repeated page headers and footers are dropped (first/last page line only, never a provision marker).
- A schedule heading must not be a bracketed margin note ("[First Schedule.]"), a wrapped sentence, or a title-case margin note; "SCHEDULE Section 8(3)" is accepted.
- "SCHEDULES" is only a container title when numbered schedules follow, and ordinals up to FIFTEENTH are recognised.
- A "Part XII of this Act ..." line (lowercase continuation) is text, not a Part heading.
- A numbered line lower than the last section number is kept as text and flagged.
- "1.—(1)" no longer leaves the dash in the section text, so subsections parse.
- The back-matter stop recognises "I, certify" and "EXPLANATORY MEMORANDUM".

Existing backend tests for the parser and ingestion passed (220 passed, 4 skipped).

Environment notes: the `ingestion-worker` Docker image runs Python 3.12 and crashes on the 3.14 syntax in `backend/app/ingestion/quality.py`, so I ran tasks through the `backend` image with the working tree mounted. A Homebrew Postgres 16 on port 5432 shadows the Docker database for host-side scripts; tests used `TEST_DATABASE_URL` pointing at the Docker database on the LAN address with an `app_test` database.

## Takeaways

- **Ready now:** NDPA 2023 (official gazette) and the Child's Rights Act (PLAC). Both are text-native. Section reconciliation is the next check.
- **Ready after a fix:** Penal Code (re-save the full PLAC page) and Cybercrimes (OCR a photographed booklet).
- **Still untested:** Criminal Code and Labour Act (PLAC Cap PDFs), Employees' Compensation Act (NSITF), Land Use Act, VAPP, FCCPA, and the FREP Rules.
- **Probably scanned:** Evidence Act (gazette), FRSC Act, and the FREP Rules gazette copy.
- **No usable text yet:** National Minimum Wage. Only the bill is in hand, so drop it from the weekend list unless the signed Act turns up.
- **Not found:** Road Traffic Regulations.
- **Non-official hosts:** FIDA, Refworld and judy.legal are record-and-review sources, not primary ones. Use `trusted_secondary` for them.

## Per-law acceptance (same gates as ACJA and the Police Act)

1. Source recorded with hash and verification status (`official` or `trusted_secondary`).
2. Arrangement of sections extracted and a `*-section-titles.json` created in `backend/app/legal/data/`.
3. Body reconciles with the arrangement: no missing, unexpected or repeated section numbers.
4. Retrieval benchmark added in `docs/`, plus topic-guide entries in `backend/app/legal/topics.py`.
5. Shown as historical or as-enacted unless every amendment has been folded in and checked. Do not call it "current consolidated law".
6. Added to a new composite release and approved before going public.

## Known gaps to state in the UI

State laws, case law, and Constitution alteration Acts are not covered.

## Next steps

1. Re-save the full Penal Code page and re-test it.
2. Download the remaining untested PDFs, run `pdftotext`, and fill the "Text-native?" column.
3. Install Tesseract (`brew install tesseract`) or use the project's OCR pipeline for the Cybercrimes booklet.
4. Find the signed National Minimum Wage 2024 Act and the 2019 principal Act, and the Road Traffic Regulations.
