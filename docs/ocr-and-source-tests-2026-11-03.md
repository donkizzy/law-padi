# OCR and source-test evidence - 3 November 2026

Evidence only; every artifact remains `needs_review`. Follow-up offline evidence was added on 3 November 2026; the follow-up section below supersedes preliminary numbering limitations where stated. Nothing was marked verified or approved. Page numbers below are 1-based PDF pages, not printed booklet/gazette pagination. “Usable for weekend” means extraction feasibility for the next review step, never permission to ingest or publish.

## Task 1 - Cybercrimes booklet

Original copied byte-for-byte from the supplied Downloads path to `backend/storage/statute-review/cybercrimes-2015-2024/CyberCrime__Prohibition_Prevention_etc__Act__2024.pdf`.

- Size: **40,061,321 bytes**; **56 pages**; unencrypted; `pdftotext` yields **0 words on every page**.
- SHA-256: `71aa33defe3507417db01270e6e94afe6c8f982c1c37567f43b51bea71ebd65f` (source and copied bytes match).
- Offline Tesseract **5.5.0**, English, PSM 1, automatic layout/orientation, full-page grayscale rasters with long edge 3,200 pixels. No cropping, contrast changes, deskew edits or text/number substitutions. `--dpi 300` is Tesseract's analysis hint, not a claim about photographic resolution. Original PDF and all unprocessed page rasters retained.
- Disposable `docker run --rm --pull never --network none --read-only --tmpfs /tmp`, mounting only the new evidence folder; Python invoked with `-I` from `/tmp`. Image ID: `sha256:7c4baa3488234c19cb67136cb45da8be86bd06d2f9adc0fc5bb7da1e912ae730`. No existing containers or database accessed.
- `ocr-pages.json` follows the reference's page-array form, adding source SHA-256 on every page, raw word confidences (0–1), word boxes/reading order, line text/boxes and character boundaries. `ocr-text.txt` retains raw OCR with page delimiters. Raw TSVs and full-page rasters allow independent inspection.

### Confidence and numbering findings

**Pages below 0.75 mean word confidence: none among pages with words.** Pages **3 and 47** contain no recognized words, so confidence is **null**, not zero or a pass. Visual inspection shows blank separators with small printed page numerals that OCR missed. Lowest non-empty pages: **31 = 0.7882**, **4 = 0.7952**. Mean confidence is an unweighted arithmetic mean over non-empty Tesseract word tokens; it is not a legal accuracy score.

**Packaging finding:** this is an ONSA compilation containing a reproduced 2015 gazette/text followed by a **separate 2024 amendment Act**. It is not an integrated amended text. The original 2015 section 24 remains on PDF p16; the replacement operation is separately printed on p52. The cover alone must not be used to label the earlier wording as consolidated/current.

**Arrangement limitation:** PDF p5 visually lists 2015 sections **1–24**; p6 immediately starts the substantive Act (gazette A621). There is no retained continuation of the principal arrangement listing 25–59. OCR on p5 captures only the first two numeric labels and drops most of the number column. Thus the visible 1–24 can be compared to body labels, but **25–59 cannot be independently reconciled against an arrangement in this file**. Do not manufacture missing arrangement pages or infer a complete contents list from body numbering.

The principal body contains recognized labels **1–59, each once**, selecting actual headings rather than printed page numbers, cross-references or schedule items. The 2024 amendment body contains **1–13, each once**, including raw `7,` on p53. The amendment arrangement on p51 visibly contains 1–13, but raw OCR loses labels 5–7. Its own numbering restart is not a duplicate in the principal Act. Repetition between an arrangement, its body and an amendment's target reference is expected; no repeated substantive heading was observed within either body's selected headings. This is a numbering observation, not a full wording/completeness check.

Actual OCR defects retained without correction:

- p5: `ARRANGEMEAT UF SECTIONS`; most section-label column lost, including a raw `wo` fragment.
- p6: printed commencement date “15th” rendered `151`; do not use raw OCR dates without image review.
- p19: `27,—(1)`; p43: `Citation. 59,`; p53: `7, Section 30...` - punctuation can defeat a full-stop-only parser.
- p31: label **48 is recognized as 48**, but text is degraded (`48.—11)`, `mnposing`, etc.). **No `4g`/`4G` token was found** in this OCR run; the example in the request was not assumed to occur.
- p51: year **2024** is rendered **299 4**; target **41** becomes **4]**. Raw labels 5–7 are absent despite being visible on the image.
- p56: handwritten assent date is badly recognized (`QB ... 20A`). The image appears dated 28 February 2024; that visual reading is an observation only, not authenticated enactment evidence.

### Page-by-page recognized section headings

A dash means no new substantive heading selected, not a missing page. Arrangement labels and cross-references are described separately. Every confidence below uses raw OCR.

| PDF page | Instrument / recognized heading labels | Mean word confidence | Note |
|---:|---|---:|---|
| 1 | 2015: - | 0.9387 | ONSA cover |
| 2 | 2015: - | 0.8575 | Booklet contents |
| 3 | 2015: - | null (no words) | Numbered blank separator |
| 4 | 2015: - | 0.7952 | Reproduced 2015 gazette cover; Act No. 17 is not a section |
| 5 | 2015: - | 0.8631 | 2015 arrangement: visually 1–24; raw numeric OCR only 1., 2.; remaining labels lost |
| 6 | 2015: 1, 2, 3 | 0.9067 |  |
| 7 | 2015: 4, 5, 6 | 0.9139 |  |
| 8 | 2015: 7, 8 | 0.9509 |  |
| 9 | 2015: 9, 10, 11, 12 | 0.9528 |  |
| 10 | 2015: 13, 14 | 0.9608 |  |
| 11 | 2015: 15, 16 | 0.9447 |  |
| 12 | 2015: 17 | 0.9496 |  |
| 13 | 2015: 18, 19, 20, 21 | 0.9503 |  |
| 14 | 2015: 22, 23 | 0.9337 |  |
| 15 | 2015: - | 0.9462 | Continuation of s23 |
| 16 | 2015: 24 | 0.9507 |  |
| 17 | 2015: 25, 26 | 0.9500 |  |
| 18 | 2015: - | 0.9505 | Continuation of s26 |
| 19 | 2015: 27, 28 | 0.9388 |  |
| 20 | 2015: 29 | 0.9547 |  |
| 21 | 2015: 30, 31, 32, 33 | 0.9484 |  |
| 22 | 2015: - | 0.9399 | Continuation of s33 |
| 23 | 2015: - | 0.9341 | Continuation of s33 |
| 24 | 2015: 34, 35, 36 | 0.9460 |  |
| 25 | 2015: 37, 38 | 0.9395 |  |
| 26 | 2015: 39, 40 | 0.9575 |  |
| 27 | 2015: 41 | 0.9319 |  |
| 28 | 2015: 42, 43 | 0.8884 |  |
| 29 | 2015: 44 | 0.9367 |  |
| 30 | 2015: 45 | 0.9430 |  |
| 31 | 2015: 46, 47, 48 | 0.7882 |  |
| 32 | 2015: 49, 50 | 0.9474 |  |
| 33 | 2015: 51, 52, 53 | 0.9421 |  |
| 34 | 2015: 54 | 0.9462 |  |
| 35 | 2015: 55 | 0.9465 |  |
| 36 | 2015: 56, 57 | 0.9448 |  |
| 37 | 2015: 58 | 0.9359 |  |
| 38 | 2015: - | 0.9443 | Continuation of s58 |
| 39 | 2015: - | 0.9137 | Continuation of s58 |
| 40 | 2015: - | 0.9264 | Continuation of s58 |
| 41 | 2015: - | 0.9269 | Continuation of s58 |
| 42 | 2015: - | 0.9455 | Continuation of s58 |
| 43 | 2015: 59 | 0.9193 |  |
| 44 | 2015: - | 0.9084 | First Schedule; reference to s42(1) |
| 45 | 2015: - | 0.9384 | Schedules/authentication; references to s44(2)(a) |
| 46 | 2015: - | 0.9372 | 2015 authentication/assent schedule |
| 47 | 2015: - | null (no words) | Numbered blank separator |
| 48 | 2024: - | 0.8342 | 2024 amendment title leaf |
| 49 | 2024: - | 0.9643 | Number-only separator: raw 48 is a page number |
| 50 | 2024: - | 0.9490 | 2024 explanatory memorandum |
| 51 | 2024: - | 0.9336 | 2024 arrangement: OCR labels 1–4, 8–13; 5–7 lost |
| 52 | 2024: 1, 2, 3, 4, 5 | 0.9457 |  |
| 53 | 2024: 6, 7, 8, 9, 10 | 0.9255 |  |
| 54 | 2024: 11, 12, 13 | 0.9472 |  |
| 55 | 2024: - | 0.8565 | 2024 authentication certificate |
| 56 | 2024: - | 0.8431 | 2024 authentication/assent schedule |

### Location of the 2024 amendment operations

PDF pp48–56 are the amendment package: title p48, number-only separator p49, memorandum p50, arrangement p51, operative text pp52–54, authentication pp55–56. These operations are transcribed as observed targets; they have not been applied or assessed for current legal effect.

| Amendment section | Principal target | PDF page |
|---:|---|---:|
| 1 | Introductory amendment provision | 52 |
| 2 | 17 (electronic signatures) | 52 |
| 3 | 21 (incident reporting) | 52 |
| 4 | 22 | 52 |
| 5 | 24 (cyberstalking/message provision) | 52 |
| 6 | 27(2) | 53 |
| 7 | 30 | 53 |
| 8 | 37(1)(a) | 53 |
| 9 | 38(1) | 53 |
| 10 | 41(1), continuing onto p54 | 53–54 |
| 11 | 44; raw wording includes “Section of 44” | 54 |
| 12 | 48(4), deletion operation | 54 |
| 13 | Citation | 54 |

## Task 2 - Seven candidate sources

All seven downloads were individually authorized in chat after sizes or size limits were disclosed. Each attempted source received its own newly created empty folder. PDFs were never executed; all Python readers used `-I` outside their folders. No alternative source was downloaded. Exact retrieval URLs, response headers, byte counts/hashes or failure details are retained in each `download.json`.

| Law | Source / hosting publisher | Bytes | Pages | Text layer | Sections found vs expected | Usable for weekend? | Notes |
|---|---|---:|---:|---|---|---|---|
| Criminal Code Act Cap C38 | [C38.pdf](https://lawsofnigeria.placng.org/laws/C38.pdf), Policy and Legal Advocacy Centre (PLAC), secondary host | 1,159,389 | 214 | Yes; 214/214 non-empty | Enabling Act 1–7 + 1A; scheduled Code integer range 1–521 plus lettered provisions. Strict body headings 518/521 integers + 50 distinct lettered labels; 307/367 are inline, 453 is starred. All three numbers are present. Arrangement: 515/521 strict integers; missing numeric candidates have punctuation/layout defects. Follow-up: 572 candidate rows on each side; four raw label discrepancies remain (see follow-up). | no | Readable text, but namespace/numbering review needed; do not flatten Act, Code and subsidiary instruments into one sequence. Amendment/repeal notes embedded. |
| Labour Act Cap L1 | [L1.pdf](https://lawsofnigeria.placng.org/laws/L1.pdf), PLAC, secondary host | 2,257,341 | 80 | Yes; 80/80 non-empty | Arrangement endpoint 92. Strict arrangement labels 91/92 (`4 7_` at p2); body 90/92 (`7 4.` at p41; `87,` at p49). Raw evidence accounts for these candidate gaps without changing text. Subsidiary rules restart numbering after main Act. | yes | Follow-up: 92 arrangement/body heading rows accounted for with separate image observations; feasible for extraction review after explicit numbering handling. Main Act through p54; schedule/subsidiary material follows. Not ingestion-ready certification. |
| Employees' Compensation Act 2010 | [ECA-2010.pdf](https://nsitf.gov.ng/wp-content/uploads/2026/07/ECA-2010.pdf), Nigeria Social Insurance Trust Fund (NSITF) | unavailable | unavailable | Unknown | Not tested: HEAD and approved GET both returned HTTP 404. | no | No PDF saved; page count, wording, sections and amendments unknown. |
| Land Use Act 1978 | [nig67625.pdf](https://faolex.fao.org/docs/pdf/nig67625.pdf), FAO FAOLEX, secondary legal repository | 233,254 | 22 | Yes; 22/22 non-empty | Arrangement and body each yield all 52 labels, 1–52; no numeric candidate gap. | yes | Best extraction candidate in this set. Includes 1978 No. 6 and 29 March 1978 commencement notation; present legal status/amendments not established. |
| Violence Against Persons (Prohibition) Act 2015 | [FIDA PDF](https://fida.org.ng/wp-content/uploads/2020/09/Violence-Against-Persons-Prohibition-Act-2015-1.pdf), FIDA Nigeria, secondary host | 17,642,446 | 33 | No; 0 words on every page | No arrangement in this copy. Visual endpoint is s48 (citation), p27; s47 application also visible. Follow-up PSM6 retains all 48 body labels once; independent arrangement still absent. | no | OCR complete for review; source identity/arrangement and full wording remain blockers. Enacted-copy evidence and Bill ambiguity discussed below. |
| Federal Competition and Consumer Protection Act 2018 | [Official FCCPC PDF](https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf), linked by [FCCPC library](https://fccpc.gov.ng/resources-library/fccpa/) | 7,842,477 | 99 | Yes, but substantially corrupted; 99/99 non-empty | Arrangement endpoint 168; strict numeric arrangement labels 97/168; body 66/168. These are extraction failures/candidates, not 102 proven absent provisions. Full raw sets/page locations in `section-audit.json`. Follow-up: two 99-page OCR passes; 157 raw body candidate labels plus 11 image annotations; duplicated A23. | no | Existing layer behaves like error-prone OCR: `l`, `r6E`, `t@`, `5J`, etc. Follow-up OCR is retained separately; numbering, duplicated-page handling and full wording review remain unresolved. |
| Fundamental Rights (Enforcement Procedure) Rules 2009 | [UNHCR archive URL](https://webarchive.archive.unhcr.org/20160922015738if_/http://www.refworld.org/pdfid/54f97e064.pdf), archived Refworld/UNHCR host | No PDF; 3,760-byte HTML response | unavailable | Unknown | No PDF available to examine orders/rules or arrangement. | no | HEAD 405; GET redirected to `__mw_turnstile`, HTTP 200 HTML. Non-PDF response rejected and not saved as a PDF. No challenge bypass attempted. |

### Source-specific observations and limits

- **Criminal Code:** body begins p32, scheduled Code p34, final Code s521 p207; federal-section table and subsidiary instruments follow. Raw arrangement tokens include `l2A`, `l4A`, `149Clipping.` and unpunctuated 75/121/122/151/195. Body `l0A` at p42 does not exactly match arrangement `10A`; body `190A` p100 has no exact `190A` counterpart in the arrangement. The report does not resolve whether this is an omitted contents entry, source typographic error or provision identity issue. `307` p135 and `367` p148 are merged into preceding prose; `*453` p180 has a star. Dates/amendment notes on p32 include 1958–1972 instruments; p85 marks 140–142 repealed by 1972 No. 9. These notes are historical source observations; later amendments, federal/state application and current offences were not researched.
- **Labour:** p4 records 1974 No. 21 and commencement 1 August 1971. Main text ends with s92 at p54, followed by transitional schedule and subsidiary legislation. No separate post-compilation amending Act was identified; embedded statutory references and old subsidiary rules do not establish current consolidation. `7 4.` and `4 7_` are preserved, not silently converted into sequence values.
- **Land Use:** arrangement pp1–3 and main text pp3–22 align on all 52 numeric heading labels. Some extracted words and brackets are imperfect. No standalone amendment text was identified in this 22-page candidate; absence of an amendment annotation is not evidence that no amendment exists.
- **VAPP enacted-copy question:** p2 literally says **“A Bill”**, has an empty commencement bracket, and also says **“ENACTED”**. The last page p33 has signed authentication and **“I ASSENT”** with President Goodluck Ebele Jonathan and a visible **25 May 2015** date. Those are positive visual indicators of an assented-copy candidate, rather than an unsigned proposal alone. Because the body retains Bill formatting and the commencement field is blank, authenticity and identity against an official enrolled/gazetted Act remain unresolved. It must not be marked as authenticated enactment. No independent arrangement appears in this file; no later amendment material was noticed. The initial supplemental OCR omits visible labels, including 47/48 on p27; the follow-up PSM6 run retains all 48 labels with word/line evidence. The source's own s47 visibly limits application to the FCT; no conclusion about state adoption was made.
- **FCCPA:** the official host links this exact PDF. Cover is a reproduced Gazette, No. 18, 1 February 2019; p8 states a 30 January 2019 commencement and Act No. 1. Citation s168 appears p94; schedules/authentication follow. Text is heavily corrupted, including the arrangement's final raw `r6E`. Repeal/savings provisions include CPC Act Cap C25 and references to portions of CAMA; this is not proof of any later amendment to FCCPA. No later amending instrument was identified in this file. Publisher authenticity/current legal status were not certified.

### pdftotext words per page

Counts use Poppler `pdftotext -layout -enc UTF-8`, split on form-feed page boundaries; whitespace-delimited token count. These counts describe the **existing text layer**, including headers, footers and OCR debris, not substantive legal words. Full page-indexed records and candidate headings are retained in each `text-pages.json`; the lists below are in PDF-page order beginning at 1.

**criminal-code**: 76,576 total words; mean 357.83/page; range 41–569.

`113, 142, 121, 153, 162, 137, 174, 127, 134, 176, 167, 150, 188, 120, 162, 152, 189, 157, 132, 125, 103, 130, 133, 159, 174, 108, 111, 148, 147, 110, 135, 326, 450, 268, 397, 405, 400, 460, 419, 413, 397, 374, 525, 529, 463, 349, 438, 390, 487, 383, 369, 342, 360, 424, 276, 401, 348, 434, 415, 488, 402, 328, 474, 391, 421, 421, 355, 373, 444, 296, 385, 412, 364, 312, 469, 417, 409, 351, 363, 382, 375, 409, 386, 368, 304, 446, 442, 397, 362, 361, 400, 356, 412, 332, 446, 411, 434, 360, 371, 365, 397, 450, 329, 425, 402, 300, 422, 466, 364, 460, 433, 391, 383, 516, 412, 458, 514, 398, 385, 413, 386, 278, 399, 378, 539, 383, 474, 509, 495, 501, 534, 459, 474, 454, 416, 355, 344, 322, 447, 358, 374, 437, 413, 452, 305, 354, 348, 418, 401, 392, 399, 473, 520, 338, 421, 539, 488, 377, 368, 388, 389, 356, 386, 408, 397, 383, 349, 364, 436, 424, 559, 488, 358, 384, 274, 318, 362, 411, 438, 367, 376, 415, 420, 569, 399, 419, 411, 370, 443, 420, 422, 441, 477, 463, 314, 406, 361, 478, 418, 423, 486, 269, 276, 429, 442, 381, 275, 59, 196, 155, 154, 217, 197, 41`

**labour-act**: 32,672 total words; mean 408.40/page; range 82–578.

`159, 158, 120, 130, 524, 501, 486, 409, 442, 493, 448, 502, 400, 369, 346, 448, 438, 503, 437, 402, 428, 440, 463, 466, 362, 510, 470, 468, 428, 473, 453, 393, 463, 427, 455, 432, 388, 446, 426, 417, 529, 418, 384, 517, 493, 478, 537, 485, 517, 427, 319, 409, 343, 445, 263, 256, 578, 496, 495, 423, 561, 439, 383, 317, 267, 343, 377, 321, 193, 225, 180, 329, 475, 458, 491, 539, 484, 532, 341, 82`

**land-use**: 10,350 total words; mean 470.45/page; range 184–698.

`212, 246, 315, 464, 500, 487, 546, 503, 591, 500, 472, 509, 515, 495, 652, 698, 527, 531, 404, 516, 483, 184`

**vapp**: 0 total words; mean 0.00/page; range 0–0.

All 33 pages: 0.

**fccpa**: 35,813 total words; mean 361.75/page; range 101–454.

`103, 141, 236, 273, 232, 271, 101, 303, 316, 314, 351, 376, 378, 324, 340, 317, 393, 372, 376, 399, 397, 351, 407, 387, 391, 432, 326, 402, 378, 365, 300, 388, 387, 401, 449, 390, 398, 387, 396, 330, 453, 386, 417, 411, 397, 350, 426, 410, 390, 353, 386, 375, 349, 376, 394, 384, 399, 341, 393, 342, 343, 406, 390, 357, 412, 410, 397, 357, 435, 355, 395, 408, 383, 444, 441, 432, 369, 362, 343, 391, 454, 449, 409, 431, 344, 441, 371, 374, 306, 315, 339, 386, 390, 207, 285, 383, 335, 180, 274`

ECA and Fundamental Rights: no PDF obtained, so words/page unavailable. Cybercrimes: all 56 pages have 0 native words/page (OCR words are a separate measurement).

## Follow-up offline evidence - 3 November 2026

The authorized follow-up used only retained PDFs and local rasters; **no downloads or network requests** were made. Raw PDFs, native text, initial OCR and initial audits remain unchanged. The new `numbering-followup-v2/reconciliation.json` files supersede preliminary heuristic counts for the questions they address. The earlier broad audits remain diagnostic evidence: their arrangement/body boundaries were not sufficiently narrow to support identity decisions (for example, the Code arrangement boundary could include enabling-Act entries, and Labour p54 also contains schedule paragraphs). The follow-up explicitly separates those namespaces.

### Labour: heading presence accounted for, wording still unreviewed

There are **92 arrangement heading rows and 92 principal-body heading rows**, with no unexplained repeated heading in those bounded selections. The retained raw forms `4 7_` (arrangement p2), `7 4.` (body p41) and `87,` (body p49) have separate image observations showing printed **47**, **74**, **87**. No replacement was made in native text or OCR. This accounts for the initial numbering candidate gaps; it does not establish the accuracy of every subsection, amount or exception.

Namespaces are now recorded explicitly: principal arrangement pp1–4; principal body p4 after commencement through p54 before `SCHEDULE`; transitional paragraphs pp54–55; subsidiary index/regulations pp55–71; Dock Labour Rules arrangement/body pp71–79; Application Declaration p80. Schedule paragraphs or subsidiary rules restarting at 1 must not become duplicate principal sections.

### Criminal Code: 572 candidate rows, four label discrepancies

The enabling Act has a separate **8-heading** sequence (1, 1A, 2–7), both in its arrangement and body. The scheduled Code has **572 candidate heading rows in its arrangement and 572 in its body** after accounting for explicit unpunctuated/inline/starred headings. These are observed row counts, not a declared canonical provision count. The body row selection has 572 distinct raw labels; the arrangement has 571 distinct raw labels because **190 is repeated**.

| Arrangement raw label / page | Body raw label / page | Evidence and disposition |
|---|---|---|
| `10A` / p2 | `l0A` / p42 | Interpretation heading; retain l/1 glyph ambiguity. No canonical identity assigned. |
| `l2A` / p2 | `12A` / p43 | Same heading topic; raw label discrepancy retained. |
| `l4A` / p2 | `14A` / p45 | Same heading topic; raw label discrepancy retained. |
| `190` / p12 | `190A` / p100 | Passport provision. Arrangement image itself prints 190, while p11 already uses 190 for a different heading. Body image prints 190A. This is a source arrangement mismatch, not merely a regex omission. |

The scheduled Code's plain numeric headings 1–521 are present in the bounded body selections, including **307** p135 and **367** p148 merged into preceding prose, and **`*453`** p180. The six unpunctuated arrangement entries remain in their original form. Cross-reference continuations on p112 (`219, 222A...`) and p120 (`225B, 236...`) were excluded from repeated-heading counts, with their text retained in the audit.

The Code begins within p34 after `SCHEDULE` and ends within p207 before the federal-section table. The table spans pp207–208; subsidiary texts occupy pp209–214 and are separate instruments. **Still blocked:** four label-identity/typography discrepancies, source wording/subsection review and any current-law/amendment decisions. No arrangement number was silently changed to match the body.

### FCCPA: two complete OCR passes, duplicate scan and unresolved text

Both **99-page** raw OCR passes are retained. Tesseract 5.5.0, English, 2,800-pixel long-edge full-page grayscale rasters: `offline-ocr-v2` uses PSM1, `line-ocr-v3` uses PSM6 on the same rasters. Every output page has source SHA-256, word confidence and boxes, line text/boxes and character boundaries. No deskew, crop or text replacement was applied to those OCR inputs. Evidence crops are separate review aids. The initial `offline-ocr-v1` renderer exited 99 before OCR; its failure metadata remains, and the retry used a new folder.

**Source duplication:** PDF **pp24 and 25 both reproduce gazette page A23**, repeating the end of s32 and headings s33–34. Images were inspected side by side: they have different scan artefacts but repeat the same substantive page. Neither page was removed or deduplicated. This source issue existed before the OCR pass.

A word-position candidate search over body pp8–94 finds **157 distinct exact numeric labels in 1–168** across the two passes. This is a candidate measure, not proof of 157 validated provisions: cross-references and wrong numeric readings are retained and explicitly flagged. The eleven labels not recognized exactly were inspected against page-image crops:

| PDF page | Raw PSM1 anchor | Separate visual observation |
|---:|---|---:|
| 31 | `S1.` | 51 |
| 32 | `$4.` | 54 |
| 32 | `§8.` | 58 |
| 42 | `806.` | 80 |
| 44 | `£6,` | 86 |
| 46 | `&7,` | 87 |
| 61 | `Nt—` | 111 |
| 62 | `312.` | 112 |
| 76 | `i44.` | 144 |
| 79 | `18).` | 151 |
| 80 | `1§2.` | 152 |

These observations do **not** replace the raw values. For example, raw `806` remains `806` in the OCR files. PSM6 also reads the s52 heading as `32` on p31; PSM1 reads 52. Both are retained rather than selecting a version to fit the sequence.

The arrangement still contains malformed labels and false repetitions: PSM6 has `30` on the Procedural Rules line associated with 50, `58` on the restraint-of-competition line associated with 59, and `13` on the Failure-to-attend line associated with 113. These are unresolved OCR observations pending a full image/arrangement audit; they have not been corrected. Raw arrangement lines and coordinates from both passes are in the reconciliation JSON.

Mean word confidence below 0.75: **PSM1 p1 0.7471, p88 0.7137**; **PSM6 p1 0.6687, p88 0.7030**. All other pages have non-null means at or above 0.75. High mean confidence does not resolve the observed section-number errors or accuracy of wording. **Still blocked:** arrangement reconciliation, duplicate-page handling and full text review, especially definitions on p88. OCR completion is not OCR acceptance.

### VAPP: all 48 body labels retained; identity question remains

The new `line-ocr-v2` uses PSM6 on pp1–32 and PSM1 on the rotated authentication page p33, with the original 2,000-pixel rasters. It retains **body labels 1–48, each once**, including p27 labels 47–48 that the first pass omitted. Each has raw line text, character boundaries, boxes, word confidences and source hash. The native text-layer measurement remains **zero words per page**; an OCR sidecar does not make the original PDF text-native.

All means for substantive-body pp2–27 exceed 0.75. Lower-confidence pages are **p28 0.7467 and p29 0.6102** in the forms material; those forms still need careful review. The original copy contains no arrangement, so the observed 48 body labels cannot be independently compared with one.

The title-page evidence remains mixed: p2 says `A Bill`, has blank commencement brackets and says `ENACTED`; p33 bears signed authentication and an `I ASSENT` block with the observed 25 May 2015 date. This supports retaining an assented-copy candidate for review but does not settle authenticity or identity against the enrolled/gazetted Act. **Still blocked:** identity/authenticity decision, independent arrangement or equivalent completeness evidence, and full wording/subsection/form review. No legal status was assigned.

### Remaining review blockers by candidate

| Candidate | Evidence now available | Remaining blocker |
|---|---|---|
| Land Use | Existing text layer; 52 arrangement/body labels | Source/current-amendment and full wording review; no new work on this source in follow-up |
| Labour | Bounded 92/92 heading rows; flagged labels visually accounted for | Full wording review and namespace-aware parser decisions |
| Criminal Code | Separate enabling Act/Code; 572/572 candidate rows; image-backed mismatch evidence | Four label discrepancies, especially duplicated arrangement 190; wording and identity decisions |
| VAPP | Full line/word OCR; 48 body labels | Assented-copy identity, independent completeness evidence, wording/forms review |
| FCCPA | Two 99-page OCR passes; number-error crops and duplicate A23 evidence | Full arrangement and text audit; evidence-preserving duplicate-page decision |
| ECA | Retained 404 attempt metadata | A usable source; no further download attempted |
| Fundamental Rights Rules | Retained non-PDF/challenge metadata | A usable PDF source; no further download attempted |
| Cybercrimes | Previous 56-page OCR retained unchanged | Missing principal arrangement continuation, separate amendment application/identity and full OCR wording review |

The follow-up did not authenticate documents, choose canonical wording, apply amendments, change review statuses, or access the database/application. All original PDFs and first-pass native/OCR evidence hashes remain unchanged. The designated report and file inventory are the only pre-existing lane files updated. A pass-one report and manifest snapshot are retained under `source-tests/followup-evidence-v1/`.

## What was not established

No source or text was marked verified/approved; no legal authenticity, current-law status, comprehensive amendment history, signature validity, hash provenance prior to the user-supplied file/download, full textual identity against an official gazette, OCR acceptance, parser compatibility, ingestion, retrieval quality or publication readiness was established. Number-label presence is not proof that all subsection text is complete. VAPP has no independent arrangement; the principal Cybercrimes arrangement is incomplete in the retained booklet; FCCPA's corrupted layer prevents a clean comparison. Download failures were not substituted with unapproved alternatives.

Only the two new evidence directories and this new report were written in the checkout. No database, existing container, Compose command, backend application, Alembic, environment file, branch, commit, push, existing docs file or the other agent's evidence folder was changed. Application tests were not run because this lane produced files only.

## Files created

All paths below are relative to the repo; the exact per-file inventory is retained as `backend/storage/statute-review/source-tests/created-files.json`.

- `docs/ocr-and-source-tests-2026-11-03.md` (this report).
- `backend/storage/statute-review/cybercrimes-2015-2024/`: original PDF, `inspection.json`, `pdfinfo.txt`, `extracted-text.txt`, `ocr-pages.json`, `ocr-text.txt`, `section-audit.json`, `cover.png`, `final.png`, `original-pages/page-01.png` through `page-56.png`, and `ocr-tsv/page-01.tsv` through `page-56.tsv`.
- `backend/storage/statute-review/source-tests/`: one folder each for `criminal-code`, `labour-act`, `employees-compensation`, `land-use`, `vapp`, `fccpa`, `fundamental-rights`. Every folder has `download.json`. The five successful sources additionally have the original PDF, `inspection.json`, `pdfinfo.txt`, `extracted-text.txt`, `text-pages.json`, `cover.png`, `final.png`. The four non-VAPP PDFs also have `section-audit.json`.
- `source-tests/vapp/` additionally has `supplemental-ocr.json`, `supplemental-ocr.txt`, and `supplemental-ocr-pages/page-01.png` through `page-33.png` (not a replacement PDF text layer).
- `source-tests/created-files.json` contains the exact inventory and file hashes, excluding its own recursive hash.

### Additional files from the follow-up

- `source-tests/labour-act/numbering-followup-v2/`: reconciliation JSON and three targeted page previews.
- `source-tests/criminal-code/numbering-followup-v2/`: reconciliation JSON and targeted page previews, preserving inline/starred headings and label discrepancies.
- `source-tests/fccpa/offline-ocr-v1/`: failed renderer metadata. `offline-ocr-v2/`: original rasters, raw TSVs, per-page JSON, complete OCR JSON/text and run metadata. `line-ocr-v3/`: alternate raw TSVs, per-page JSON, complete OCR JSON/text and run metadata. `numbering-followup-v2/`: reconciliation JSON, eleven label crops and duplicate/low-confidence page previews.
- `source-tests/vapp/line-ocr-v2/`: raw TSVs, per-page JSON, complete OCR JSON/text and run metadata. `numbering-followup-v2/`: reconciliation JSON and identity/application/citation page previews.
- `source-tests/followup-evidence-v1/`: pass-one report/manifest snapshots, evidence-preservation check and follow-up file inventory.
- `source-tests/created-files.json`: refreshed complete inventory with current report hash. All paths are relative to `backend/storage/statute-review/` in the entries above.
