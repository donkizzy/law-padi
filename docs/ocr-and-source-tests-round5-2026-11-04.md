# Round 5: statute sources and OCR tests — 2026-11-04

Scope: Tier 2 items 11–18, in plan order. Items 11–13 were completed before starting item14. Item12 excludes the Nigeria Tax Act2025 run and the old CITA, PITA, VAT and CGT Acts. Tier3 was not started; Copyright2022 and all Tier1 material/runs were excluded from source testing.

Results by law: **4 ready to ingest for the stated historical/as-enacted scope, 3 need an OCR route, 6 blocked.** Seven new title catalogues contain780 entries and remain `needs_review`. These ratings concern source usability and structure; nothing was ingested or marked verified. “Ready” does not mean current consolidated law.

Python PDF inspection ran with `-I` from `/private/tmp`, outside every downloaded source folder. Poppler `pdfinfo`, `pdftotext -layout` and reading-order `-raw` outputs were kept separately. Whitespace token counts measure extraction quantity, not accuracy. PDF page references are one-based. Printed gazette pages are stated separately. Body labels are audited within the principal Act, excluding schedules, forms, subsection/cross-reference lines and subsidiary Rules where identified. Every excluded candidate remains documented; missing numbers were never supplied from an expected sequence.

Offline Apple Vision used accurate recognition, `en-US`, language correction disabled and no custom words. NRS used1800×2500 PDFKit thumbnails; the other retained Vision passes used3600×5000. Selected-page passes are explicitly limited. Vision page numbers are PDFKit indices and are not silently substituted for Poppler indices. The NRS raw Vision file contains an inherited boilerplate sentence “PDF text layer remains absent.” That sentence is inaccurate for this PDF: native extraction establishes a defective embedded OCR layer. Its raw metadata was left untouched and this report records the correction.

Complete per-page native and OCR token counts, with engine-specific page indices: [round5-per-page-word-counts-2026-11-04.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-per-page-word-counts-2026-11-04.json>). Source-specific `native-pages.json` files also retain every native page’s raw text. No zero-word page was treated as missing legislation without image/source review.

## Currency findings that change or qualify the plan

- NRS and JRB commencement captions say **26June2025**, contrary to item12’s blanket1January2026 revenue-body wording. Their2026 operational rollout is a separate event. NTAA’s own commencement remains untested because no local file was located.
- CAMA2020 and Pension Reform2014 have later Business Facilitation (Miscellaneous Provisions) Act2022 amendments, assented in2023, absent from these original texts. CAMA also has post-June2026 appellate reporting that needs the judgments.
- The current Electoral statute is the **Electoral Act2026**, assented18February2026. This was established and reported before any Electoral download. The downloaded INEC attachment is Bill-form text, so its official host does not establish the assented wording.
- Marriage/Matrimonial sources are historical LFN2004 compilations. Later administrative instruments and2025/26 amendment Bills were located; they do not make these files2026 consolidations.
- Money Laundering amendment activity continued through3–4November2026; the located report concerns parliamentary passage, not presidential assent. Other2026 proposals, circulars, Rules and court reports are distinguished from enacted amendments below.

Currency conclusions are bounded research findings as of4November2026. “No later enacted amendment located” is not proof that none exists.

## 11. Companies and Allied Matters Act2020 (CAMA)

**BLOCKED — mirrored body page91; 870 arrangement labels versus867 readable body labels; no catalogue.**

Source: [CAC notebook PDF](https://news.cac.gov.ng/wp-content/uploads/2026/01/CAMA-NOTE-BOOK-FULL-VERSION.pdf), Corporate Affairs Commission; **official agency host of gazette reproduction**. Gazette No124,10August2020,Vol107. An as-enacted2020 Act reproduction, not a2026 consolidation. Official older CAC and NIPC attachment candidates returned404; no better usable official candidate was selected.

File: `CAMA-NOTE-BOOK-FULL-VERSION.pdf`. **528 PDF pages; 1,269,127 bytes; text layer: yes.** Native whitespace tokens: 211,282; per-page range 10–699. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-cama-2020-cac/native-pages.json>).

SHA-256: `d39745af4eaeceb8dbdc3678bb5d072b48ad5e022ead3b1cec7f94b88b01a2c8`.

Arrangement: PDF3–31; principal body33–440; schedules441–527. The body on PDF91 is horizontally mirrored. Raw readings include `.521`, `.621`, `.721`; they were not reversed into125/126/127. Those three section openings remain unresolved. The audit records870 arrangement numeric positions and867 body positions. Twenty-nine arrangement labels lack the usual dot:269(PDF11),481(18),625–648(23),792–794(28). Body `172.–`(111) and `285.–`(167) and excluded cross-references147(115),299(174),422(240) remain raw alternatives. Arrangement869(PDF31) reads `Repeal and savings.Citation.`; body margin(PDF439) reads `Repeal and savings.`. PDF metadata incorrectly calls the document `ELECTORAL (AMENDMENT) ACT, 2015`; visible contents identify CAMA.

Assent: PDF528 visibly typesets `I ASSENT`, `LS`, Muhammadu Buhari and7August2020; native/visual `7th` and Vision `Tth` are separate retained readings. PDF527 clerk certification names Mohammed Ataba Sani-Omolori,9July2020. Commencement PDF33 is7August2020. The typeset assent is evidence in the file, not signature authentication. [Presidency assent announcement](https://statehouse.gov.ng/after-30-years-president-buhari-signs-amended-companies-and-matters-allied/) corroborates the date.

Later law: the Business Facilitation (Miscellaneous Provisions) Act2022, assented in2023, amends CAMA. [UNCTAD amendment record](https://investmentpolicy.unctad.org/investment-policy-monitor/measures/4752/nigeria-enacted-the-business-facilitation-act-2022) and [official assent announcement](https://fmino.gov.ng/president-muhammadu-buhari-assents-to-the-business-facilitation-miscellaneous-provisions-bill-2022-and-other-bills/) were located; conflicting precise reported February dates were not resolved by choosing one. [Premium Times,2October2026](https://www.premiumtimesng.com/news/top-news/914127-appeal-court-affirms-nullification-of-cama-provisions-on-cac-powers-over-religious-groups-others.html) reports a17September appellate decision affecting839,842–848 and part of851. Judgment not obtained; this is a judicial-effect lead, not a legislative repeal or incorporated correction. No Nigerian CAMA2026 replacement was located.

Overlaps: BOFIA/company governance, ISA/capital markets, BFA’s Pension Reform amendments, and an old Arbitration and Conciliation Act reference in the schedules. The latter is an overlap lead only; Tier3 was not sourced.

Catalogue gate: failed. No catalogue created;125–127 are unresolved body openings. All870 title positions were captured, but title-by-title visual acceptance was not completed once the count gate failed. Browser remedy: an unmirrored official/gazette assented copy with readable disputed body openings, saved directly into a separately approved new empty folder; do not substitute an old Act or Bill.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-cama-2020-cac/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-cama-2020-cac/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-cama-2020-cac/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-cama-2020-cac/source-and-currency-observations.json>).

Offline OCR: [vision-key-pages-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-cama-2020-cac/vision-key-pages-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 12a. Nigeria Tax Administration Act2025 (NTAA)

**BLOCKED — approved NASS file absent locally; all arrangement/body/assent rows untested; no catalogue.**

Preferred candidate: [National Assembly attachment11250](https://nass.gov.ng/documents/download/11250), **official legislature**. The [NASS catalogue](https://nass.gov.ng/documents/magazine_track/) labels it Nigeria Tax Administration Act2025, uploaded13May2026. Successful PDF HEAD supplied no Content-Length; user approved an unknown-size download as `Nigeria-Tax-Administration-Act-2025-NASS.pdf`.

The browser’s separate origin gate denied nass.gov.ng and explicitly barred another route. No HTTP GET bypass was attempted. User reported direct saves, but `round5-nigeria-tax-administration-2025-nass/` remained empty on inspection. Pages, actual size, SHA-256, words/page, text layer, own-file assent, commencement and edition cannot be reported as tested. All section/title rows remain missing evidence, not zero sections.

External status: [Presidency,26June2025](https://statehouse.gov.ng/president-tinubu-new-tax-laws-the-way-forward-for-nigerias-prosperity/) identifies four assented tax Acts. [Fiscal Reforms authorised-gazette release](https://www.fiscalreforms.ng/news/gazetted-tax-reform-acts-authorised-by-national-assembly) and [VON account of NASS releases](https://von.gov.ng/house-of-reps-releases-tax-acts-to-public/) make version comparison material. [Official18June2026 transition guidance](https://fmino.gov.ng/federal-government-issues-transition-guidelines-for-tax-acts-2025/) must not be used to assume all companion Acts share one commencement date. [Official18September2026 Finance Bill2027 drafting report](https://fmino.gov.ng/134-stakeholder-submissions-to-shape-nigerias-next-phase-of-tax-reforms-oyedele/) is not an enacted replacement. No later enacted NTAA replacement was located; own-file wording and amendment/repeal list remain untested.

Overlaps: NRS, JRB/tax appeals and the excluded Nigeria Tax Act2025. No protected run or old CITA/PITA/VAT/CGT source was opened. Remedy: save the already-approved complete NASS11250 PDF, including cover, arrangement, body, schedules and assent, directly into the designated empty folder. No Downloads staging or move. The file must exist before metrics or a catalogue can be accepted.

Evidence: [round5-unavailable-download-observations-2026-11-04.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-unavailable-download-observations-2026-11-04.json>); read alongside [round5-download-routing-addendum-2026-11-04.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-download-routing-addendum-2026-11-04.json>) because the earlier JRB absence statement was subsequently corrected.

## 12b. Nigeria Revenue Service (Establishment) Act2025

**NEEDS OCR ROUTE — all43 arrangement titles legible and43 body labels matched through OCR/image evidence; catalogue created.**

Source: [NRS attachment](https://www.nrs.gov.ng/uploads/NIGERIA_REVENUE_SERVICE_ESTABLISHMENT_ACT_2025_84bc74e1bf.pdf), Nigeria Revenue Service; **official agency host**, Federal Government Printer gazette reproduction. Gazette No117,26June2025,Vol112,Act4. As enacted, not consolidated. NASS11251 was identified but not retrieved under the origin denial; the NILDS2024 Bill candidate was rejected as a Bill.

File: `NIGERIA_REVENUE_SERVICE_ESTABLISHMENT_ACT_2025_84bc74e1bf.pdf`. **30 PDF pages; 8,039,130 bytes; text layer: yes.** Native whitespace tokens: 7,992; per-page range 0–408. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/native-pages.json>).

SHA-256: `3d49f6bb28f76087416a5e2e3c146f37138887bf4c1fdb1eea7c78c086f75af4`.

Arrangement PDF3–4(A231–232), body5–23, schedules24–28, clerk29, assent30. The embedded OCR is defective: native43 arrangement readings versus42 body readings; section40’s opening is garbled. Independent Vision/image evidence locates43/43. Raw omissions/punctuation at arrangement3/4 and body38/39 remain unchanged. Examples: native14 `Establistunent`/`Tectmical Conurittee`, native39 `un-renitted`, and Vision/image `un-remitted` remain alternatives. The catalogue is an independent faithful image-supported transcription; no native numeral was repaired to obtain43.

Assent PDF30: typeset `I ASSENT`, `LS`, Bola Ahmed Tinubu,26June2025; no wet-ink signature observed. Clerk PDF29: visual11June2025 versus native `IIM Day of June, 2025`. Commencement PDF5 raw `[ 26th June. 2025 ]`, visually26June2025: **this differs from the plan’s blanket1January2026 claim**.

Repeal: s40(1),PDF20, FIRS(Establishment) Act13/2007; savings s41,PDF20–22. This was an institutional replacement, not permission to source old substantive tax Acts. No later assented replacement/amendment located in bounded official research. The January2026 authorised-version controversy was not resolved by comparison to a NASS certified true copy; the2027 Finance Bill drafting announcement is not law. See the official tax-status sources in12a.

Overlaps: PRA2014 expressly applied by s20(PDF15); companion tax Acts in Second Schedule(PDF27); confidentiality ss32–33 and FOI/data-protection subject matter. Protected tax source/run excluded.

Catalogue: `nigeria-revenue-service-establishment-act-2025-section-titles.json`,43 titles, `needs_review`. No arrangement rows missing. An OCR ingestion route still needs substantive-text review; a separately approved born-digital NASS certified copy would help compare wording. The raw scan remains untouched.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/source-and-currency-observations.json>).

Offline OCR: [vision-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/vision-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 12c. Joint Revenue Board of Nigeria (Establishment) Act2025

**NEEDS OCR ROUTE —61 legible arrangement titles and61 body labels; catalogue created; approved wrong-folder inspection recorded.**

Source: [Office of the Tax Ombud attachment](https://taxombud.gov.ng/wp-content/uploads/2026/03/Joint-Revenue-Board-Est.-Act-2025.pdf), **official agency host**, Federal Government Printer reproduction. Gazette No117,26June2025,Vol112,Act6; as enacted, not consolidated. This attachment has assent evidence; the separate NASS11247 catalogue’s “BILL” label was not used to classify it.

File: `Joint-Revenue-Board-Est.-Act-2025.pdf`. **35 PDF pages; 9,711,228 bytes; text layer: yes.** Native whitespace tokens: 10,340; per-page range 84–382. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/native-pages.json>).

SHA-256: `808fb7b9d83606a4eea1c9b5f341d9ef260dc6db79a581fefab11e8f593974b0`.

The original PDF remains in the **NRS folder**, under the user’s explicit in-place-inspection exception; all derived JRB evidence is in its separate JRB folder. An unintended duplicate, `Joint-Revenue-Board-Est.-Act-2025 (1).pdf`,9,711,228bytes, also remains in NRS. It was downloaded without fresh per-download approval. It was not opened or hashed to assert content identity.

Arrangement PDF2–3(A349–350); body4–23; schedules24–34; clerk34; assent35. All61 titles are legible. Vision omits arrangement numeral31, but native/image explicitly show31; Vision32 `Lones` versus native/image `Zones` and Vision `PART II` versus image/native `PART III` are retained alternatives. Native punctuation loss, including arrangement38/body32, is not treated as a missing section. Body `. 14.` atPDF9 is retained; a non-section4 cross-reference atPDF22 is excluded and documented. The independent image-supported catalogue does not rewrite raw OCR.

Assent PDF35: typeset `I ASSENT`, `LS`, Bola Ahmed Tinubu,26June2025; clerk11June2025(PDF34–35). Commencement PDF4 is26June2025, **not the plan’s blanket1January2026 date**. The certificate’s Bill language is accompanied by an assent page.

The Act itself amends historical PITA by deleting ss86 and102(s58,PDF21), and repeals FIRS s59/Fifth Schedule(Second Schedule para15,PDF30–31). These are cross-references in this source; the old Acts were not separately sourced. NRS’s whole-FIRS repeal overlaps and is not silently reconciled. [Tax Ombud mandate/status](https://taxombud.gov.ng/about-us/) and [JRB2026 guidelines](https://www.jrb.gov.ng/assets/2026-pit-guidelines-TJG3n9-T.pdf) continue to invoke the2025 Act. No later enacted amendment/repeal located; no comparison against the January2026 NASS authorised copy completed.

Overlaps: NRS/NTAA dispute architecture; PRA2014 s12(PDF8–9); Evidence reference, Second Schedule para8(PDF29); confidentiality ss51–52 versus FOI/data protection. No legal conflict was adjudicated.

Catalogue: `joint-revenue-board-of-nigeria-establishment-act-2025-section-titles.json`,61 titles, `needs_review`; no arrangement title rows missing. OCR review is still needed for substantive ingestion.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/source-and-currency-observations.json>).

Offline OCR: [vision-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/vision-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 13. Pension Reform Act2014

**BLOCKED — clipped arrangement, missing printedA44/body22–23 openings and renderer disagreement; no catalogue.**

Source: [Gazettes.Africa bundle](https://archive.gazettes.africa/archive/ng/2014/ng-government-gazette-dated-2014-05-20-no-62.pdf), **secondary archive of official Federal Government Printer material**, not an official issuing host and not PLAC `trusted_secondary`. The user approved this lower-priority fallback after official/PLAC discovery did not yield a usable copy. PenCom attachment candidates returned404; PTAD403; BPSR’s link pointed at another instrument; NASS9244 was not retrieved under the origin block. Full attempted URLs/results are retained in observations.

File: `ng-government-gazette-dated-2014-05-20-no-62.pdf`. **87 PDF pages; 20,258,173 bytes; text layer: yes.** Native whitespace tokens: 27,990; per-page range 0–447. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/native-pages.json>).

SHA-256: `e9c08882bcdfa2a01502d52d3d9d6f076a3ff08e428baa028a6da2b6b08a7101`.

The PDF remains in the NRS folder under the explicit user exception. Its filename and opening No62/20May2014 identify another part of a mixed bundle. **Pension’s cover is PopplerPDF23: No64,2July2014,Vol101,GovernmentNotice88,Act4,A27–91.** Pension arrangement is24–28, body29–82, schedules83–85, clerk86, assent87. Earlier bundle pages were not used to test other laws.

Arrangement PDF27/A30 is clipped after partial103;104 and105 titles occur in native OCR but are not visible there and were not accepted. Body printedA44 is absent (A43 atPDF39 is followed byA45 at40); section22–23 openings were not located. PrintedA48 precedesA47(PDF42/43). No page was inserted or reordered. The121 comparison addresses in the audit are not an accepted full-body count; candidates and unresolved rows remain visible.

Renderer conflict: PopplerPDF34 is blank while PDFKit/Vision index34 readsA39; PDFKit indices36 and87 are empty while Poppler37/87 containA41/assent. Vision41/42 readA48/A47 versus Poppler42/43. These engine indices were not aligned by guessed offsets. Offline Vision covers PDFKit23–87, not earlier unrelated Acts.

Assent PopplerPDF87 visibly typesets `I ASSENT`, `LS`, Goodluck Ebele Jonathan,1July2014; clerk16June2014(PDF86). Commencement PDF29 is1July2014. As-enacted gazette reproduction, not consolidated. s117 repeals PRA2/2004 as amended. [NGX/SEC/PenCom account](https://ngxgroup.com/sec-pencom-ngx-reiterate-commitment-to-deepening-securities-lending/) identifies the later BFA2022/2023 amendment to PRA s89(2) for securities lending; it is not folded in. [PenCom January2026 circular](https://www.pencom.gov.ng/wp-content/uploads/2026/01/Circular-on-Appointment-of-External-Auditors-and-Actuaries-for-Approved-Existing-Schemes-and-Additional-Benefits-Schemes.pdf) continues invoking2014. [House12March2026 order paper](https://placng.org/i/wp-content/uploads/2026/03/House-of-Reps-order-paper-Thursday-12-March-2026.pdf) and [23July2026 review report](https://www.thecable.ng/pencom-to-increase-employers-pension-contribution-rate-in-ongoing-pra-review/) are amendment/review leads, not evidence of an assented replacement.

Overlaps: NRS/JRB staff pensions; BFA also amends CAMA; ISA investment/pension assets. Historical tax references were retained without sourcing old tax Acts.

Catalogue gate failed: partial103, missing visible104–105 arrangement titles, missing body22–23 openings and complete count unresolved. Remedy: a complete assented PRA2014 official/NASS/PenCom/gazette copy with fullA30 andA44, plus assent, directly saved into a newly approved empty folder.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/source-and-currency-observations.json>).

Offline OCR: [vision-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/vision-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 14a. Matrimonial Causes Act,CapM7 LFN2004

**BLOCKED — printed duplicate41/missing46 in arrangement versus115 body labels; no catalogue.**

Source: [PLAC M7.pdf](https://lawsofnigeria.placng.org/laws/M7.pdf), Policy and Legal Advocacy Centre, **trusted_secondary**. Bounded official gazette/NASS/Justice/agency searches did not locate a usable principal Act; Edo Judiciary’s Matrimonial-Laws attachment is Rules and was not substituted for the Act. Historical LFN2004 statutory compilation/reprint incorporating earlier changes; not a Bill, not an as-enacted1970 original or2026 consolidation.

File: `M7.pdf`. **226 PDF pages; 2,203,291 bytes; text layer: yes.** Native whitespace tokens: 106,675; per-page range 80–753. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/native-pages.json>).

SHA-256: `b816334658362ca37e824cc1859ad95ba546577060f70260ac7fd4fdef6ce936`.

Arrangement PDF1–4; principal body4–37; schedules37–42; separate subsidiary Rules/forms43–226. PDF4 cites1970No18 and commencement17March1970. No assent/signature page found; commencement is not assent authentication.

Arrangement has115 rows but114 distinct numeric labels. PDF2 visibly prints41 twice and no46. The42–45 title assignments consequently differ from body42–46(PDF16–17). The source image confirms the conflict; it is not only OCR. Raw labels and titles remain in the full table, with separate Vision alternatives; nothing was shifted forward or renumbered. Body has115 distinct labels. Catalogue not created; the41–46 mapping requires a faithful source.

No enacted2025/26 replacement was located in bounded research. [Legis360 SB944 record](https://lip.legis360.org/bill?id=3448) calls it a Matrimonial Causes amendment, while [NALTF’s official5November2025 plenary account](https://naltf.gov.ng/senate-plenary-highlights-5-november-2025/) calls SB944 Marriage Act(Amendment). This unresolved Bill metadata is not an enacted amendment. [NASS tracker](https://nass.gov.ng/documents/bill_track/) did not establish assent.

Overlaps: Marriage Act validity/prohibited degrees; Evidence/matrimonial evidence; child custody/protection subject matter. No Tier1 source was tested. Remedy: an official/gazette or better trusted-secondary principal Act with clearly distinguished41–46 arrangement rows, after fresh download approval and direct save.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/source-and-currency-observations.json>).

Offline OCR: [vision-key-pages-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/vision-key-pages-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 14b. Marriage Act,CapM6 LFN2004

**READY TO INGEST — principal Act55 sections only, as a historical compilation with source variants retained; catalogue created.**

Source: [PLAC M6.pdf](https://lawsofnigeria.placng.org/laws/M6.pdf), Policy and Legal Advocacy Centre, **trusted_secondary**, after bounded preferred-source discovery did not yield a usable principal copy. LFN2004 compilation incorporating earlier changes; statutory text, not a Bill. No assent page found. This is not certified current consolidated wording.

File: `M6.pdf`. **41 PDF pages; 453,132 bytes; text layer: yes.** Native whitespace tokens: 9,222; per-page range 0–641. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-marriage-m6-plac/native-pages.json>).

SHA-256: `fec5db238b505dddd0e14f5352af3cc08befe7b0881a1dad3a703b0fae45cee9`.

Arrangement PDF1–2; body2–12; principal schedules12–15; subsidiary instruments15–41. PDF2 commencement31December1914; historical citations include18/1914,18/1916,23/1922,58/1933,1/1958,LN131/1954 and1/1955; later in-file references include1970No18 andLN112/1964. These citations are not independently authenticated assent evidence.

All55 arrangement titles are legible and match55 body labels. Faithful source spellings `Maniage`(3/27/29) and `manied`(46) are retained. Arrangement19 `Signature or consent` versus body `Signature of consent`,35 `Native` versus body `Customary`, and47 `native` versus body `customary` remain alternatives. Arrangement11 includes its(1)–(3) explanations as one section entry. No wording was chosen to hide a conflict.

Subsidiary defects are outside the ready rating: PDF34–36 are native blank and also empty in offline Vision. Delegation Notice appears at33 and41; the latter repeats paragraph1. The bundle was not deduplicated or repaired.

[Ministry of Interior](https://interior.gov.ng/citizenship-and-business/?SE=hit+app) continues invoking CapM6. [Official2020 fee review](https://fmino.gov.ng/fg-reviews-fees-for-the-conduct-of-statutory-marriage-in-nigeria/) and [2021 amended Legal Notices/new registries](https://fmino.gov.ng/fg-announces-establishment-of-20-new-marriage-registries/) postdate the2004 compilation and were not folded in. [NASS2025 Senate tracker](https://nass.gov.ng/documents/billdownload/11207.pdf) lists SB883; [NALTF5November2025](https://naltf.gov.ng/senate-plenary-highlights-5-november-2025/) lists SB944. No assented replacement located. [Radio Nigeria25September2026](https://radionigeriasouthsouth.gov.ng/npc-unfpa-move-to-end-zero-marriage-divorce-data-with-harmonized-protocol/) supplies a later administrative-data lead, not a new Act.

Overlaps: Matrimonial Causes Act, child protection/VAPP/bigamy subjects, separate Same Sex Marriage(Prohibition)Act. These references did not start other source runs.

Catalogue: `marriage-act-section-titles.json`,55 titles, `needs_review`. No missing principal arrangement rows. Ready only for a faithful historical principal-Act import retaining variants; subsidiary instruments and later legal effects need separate work.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-marriage-m6-plac/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-marriage-m6-plac/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-marriage-m6-plac/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-marriage-m6-plac/source-and-currency-observations.json>).

Offline OCR: [vision-key-pages-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-marriage-m6-plac/vision-key-pages-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 15. Freedom of Information Act2011

**BLOCKED — two official-hosted copies retain conflicting/malformed labels; no catalogue.**

SourceA: [Federal Ministry of Justice PDF](https://foia.justice.gov.ng/resources/downloader.php?filename=Freedom_Of_Information_Act.pdf), **official supervising ministry**. SourceB: [Edo State Judiciary PDF](https://edojudiciary.gov.ng/wp-content/uploads/2016/10/Freedom-Of-Information-Act-2011.pdf), **official judicial host**. Both reproduce Act text but are retyped/converted copies, not independently authenticated original gazette editions. Neither establishes a later consolidation. OSGF gazette candidate connection failed; no copy was downloaded from that route.

**A — Ministry.** File: `Freedom_Of_Information_Act.pdf`. **10 PDF pages; 153,279 bytes; text layer: yes.** Native whitespace tokens: 5,119; per-page range 199–680. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-justice/native-pages.json>).

SHA-256: `a2547fabd047b65815143f3a653d80f31f351782cb63f44b01334141f8eeedfd`.

**B — Edo.** File: `Freedom-Of-Information-Act-2011.pdf`. **11 PDF pages; 81,840 bytes; text layer: yes.** Native whitespace tokens: 4,683; per-page range 208–522. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/native-pages.json>).

SHA-256: `72502284ea8c3de2d764d79d24000b1a8cbddf020d0f4815324e0c999d34c854`.

A: arrangement PDF1 in three columns has32 numeric labels; body2–10 has32 numeric readings but31 distinct labels because PDF9 prints **`3. In this Act`**, while arrangement31 says Interpretation and body3 already appears atPDF3. The page image confirms3, not31. Assent PDF10 typesets Goodluck Jonathan,28May2011, with clerk27May and passage24May. Metadata Word/ICFNL2012 conversion was not treated as2011 gazette provenance.

B: arrangement PDF1 visibly reads **`S. Transfer`** and **`3Unterpretation`**; native alternatives include `1O`, `l l`, `l2`, `l3` and a missing dot at20. Vision also retainsS/3U. BodyPDF10 reads **`31. In this Act`**, independently of A’s3. B’s simple numeric body extraction yields29 rows/28 unique labels, which is an incomplete parsing count, not an accepted full section total. Other raw label variants remain in its audit. No `S→5`, `3U→31` or sequence completion occurred. PDF11 has clerk certification but no presidential assent/date; PDF1’s commencement caption is blank. Metadata records a2016 HP/Ghostscript conversion.

The Ministry’s [FOI portal](https://www.justice.gov.ng/freedom-of-information-portal/) externally corroborates28May2011 assent; [Justice FOI reporting](https://justice.gov.ng/category/foi/) continues in2026. No assented replacement was located. [EU-supported2025 reform discussion](https://eusdgn.org/stakeholders-rally-support-for-foi-act-reform-at-eu-backed-abuja-summit/) and [NILDS Official Secrets amendment Bill](https://ir.nilds.gov.ng/handle/123456789/3221?show=full) are proposals, not proof of FOI repeal/amendment. The11April2025 Osakue/EDOSACA state-application ruling(SC/614/2018) is a [secondary judgment lead](https://www.ndr.org.ng/identifying-gaps-in-the-foi-act-possible-areas-for-amendment-2/); judgment not obtained.

Overlaps: Evidence s22; Criminal/Penal/Official Secrets references in s27 (not treated as wholesale repeal); privacy/data protection and NRS/JRB confidentiality. Protected Tier1 sources were not inspected.

Catalogue failed: A’s body31 is labelled3; B’s arrangement Transfer/Interpretation labels and remaining body parsing are unresolved. No hybrid catalogue was assembled by selecting convenient readings across copies. Remedy: a complete assented official gazette with legible arrangement5/31, body31 and assent, saved directly into a newly approved folder.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-justice/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-justice/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-justice/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-justice/source-and-currency-observations.json>).

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/source-and-currency-observations.json>).

Offline OCR: [vision-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/vision-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 16a. Money Laundering (Prevention and Prohibition) Act2022

**READY TO INGEST — as-enacted31-section source; all arrangement titles legible and body labels matched; catalogue created.**

Source: [SCUML/EFCC PDF](https://scuml.efcc.gov.ng/wp-content/uploads/2022/05/MONEY-LAUNDERING-publication.pdf), **official implementing agency hosting Federal Government Printer gazette**; linked from [agency laws page](https://scuml.efcc.gov.ng/laws-regulations/). Gazette No90,13May2022,Vol109,GovernmentNotice67,Act14. As enacted, not consolidated.

File: `MONEY-LAUNDERING-publication.pdf`. **27 PDF pages; 583,529 bytes; text layer: yes.** Native whitespace tokens: 8,173; per-page range 12–437. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/native-pages.json>).

SHA-256: `d8a9646eac258fbfe2c92f1a0d9073ab2170db96bfe18cfbc3f4d60aab443621`.

Arrangement PDF3–4, body5–25, clerk26–27, assent27. All31 titles are visually legible; native reading-order extraction finds31 body labels, while layout-only regex finds16 because marginal headings precede some starts. This is an extraction-layout difference, not15 missing sections. Raw lines from both streams remain. Arrangement14’s singular `Non-financial business and profession` is retained faithfully.

Assent PDF27 typesets `I ASSENT`, `LS`, Muhammadu Buhari,12May2022; commencement PDF5 same date. Clerk certification8May2022, Senate passage16March/House4May. Gazette cover rangeA465–488 omits the assent’s printedA489; discrepancy retained. [Presidency’s three-Bill assent release](https://statehouse.gov.ng/president-buhari-signs-three-bills-into-law/) corroborates assent.

s29(PDF21) repeals Money Laundering(Prohibition)Act11/2011 with savings. Later SCUML2023 NPO and2024 AML/CFT/CPF Regulations are subordinate instruments, not incorporated Act replacements. [NASS2025 House tracker](https://nass.gov.ng/documents/download/11206) has HB2450 first reading23July2025; [Senate tracker](https://nass.gov.ng/documents/billdownload/11207.pdf) includes SB378. A [4November2026 report](https://thesun.ng/state-police-nass-set-to-transmit-bill-to-tinubu-for-assent/) says the Senate passed an amendment Bill on3November for concurrence. **No presidential assent located; no amendment merged or claimed enacted.**

Overlaps: CAMA beneficial ownership; BOFIA/ISA regulated institutions; Terrorism2022 financing/freezing; NFIU/EFCC and Proceeds of Crime2022 references. Those additional laws were not downloaded.

Catalogue: `money-laundering-prevention-and-prohibition-act-2022-section-titles.json`,31 titles, `needs_review`; no missing arrangement rows. Ready for the2022 as-enacted source, with2026 Bill status caveat.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/source-and-currency-observations.json>).

## 16b. Terrorism (Prevention and Prohibition) Act2022

**READY TO INGEST — as-enacted100-section source; all arrangement titles legible and body labels matched; catalogue created.**

Source: [SCUML/EFCC PDF](https://scuml.efcc.gov.ng/wp-content/uploads/2022/05/TERRORISM-PREVENTION-publication.pdf), **official agency-hosted gazette**. Gazette No91,16May2022,Vol109,GovernmentNotice68,Act15. As enacted, not consolidated.

File: `TERRORISM-PREVENTION-publication.pdf`. **89 PDF pages; 960,394 bytes; text layer: yes.** Native whitespace tokens: 30,696; per-page range 11–472. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/native-pages.json>).

SHA-256: `43ca520756f7ce69b026d963d155e63dcced58a0c1801a61fe579980fca07f18`.

Arrangement PDF3–6; body7–78; schedules79–87; clerk88–89; assent89. All100 titles are visibly legible; native reading-order extraction finds100 body labels. Layout-only regex finds55 because marginal headings precede starts; no45 sections were supplied by interpolation. Arrangement41’s source grammar `onboard a ships` is retained. No numeric discrepancy after using the raw reading-order stream.

Assent PDF89 typesets `I ASSENT`, `LS`, Muhammadu Buhari,12May2022; commencement PDF7 same date. Clerk10May2022; Senate passage27April/House4May. Gazette coverA489–574 versus assentA575 is retained. The [Presidency release](https://statehouse.gov.ng/president-buhari-signs-three-bills-into-law/) corroborates assent.

s98(PDF65) repeals Terrorism(Prevention)Act10/2011; ss97–98 preserve relevant matters. The former2013 amendments are a historical link, not a replacement for the2022 source. Targeted Financial Sanctions Regulations2022 are a later instrument, not an Act amendment. [NALTF kidnapping/death-penalty amendment account](https://naltf.gov.ng/senate-declares-kidnapping-terrorism-pushes-death-penalty/) and [Spaces for Change public-hearing account](https://spacesforchange.org/s4c-participates-in-the-public-hearing-on-the-proposed-amendment-to-the-terrorism-prevention-and-prohibition-act-2025/) concern proposals. [18June2026 report](https://www.thisdaylive.com/2026/06/18/bamidele-electoral-act-wont-be-amended-before-2027-polls/) still describes amendment work. [4November2026 government-briefing report](https://punchng.com/renting-properties-to-terrorists-others-attract-prosecution-fg/) continues invoking the2022 Act. No later assented replacement/amendment located.

Overlaps: Money Laundering2022; BOFIA freezing/financial institutions; Evidence/criminal procedure; NCTC/Nigeria Sanctions Committee and victims-fund provisions. No other source runs begun.

Catalogue: `terrorism-prevention-and-prohibition-act-2022-section-titles.json`,100 titles, `needs_review`; no missing arrangement rows. Ready for as-enacted source scope, not a legal-consolidation claim.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/source-and-currency-observations.json>).

## 17. Electoral Act2026

**BLOCKED — current statute established, but local INEC file is Bill-form and approved NASS gazette was not found; no catalogue.**

**Current law established before download:** [Presidency announcement](https://statehouse.gov.ng/president-tinubu-signs-amended-electoral-act-commits-to-strengthening-democracy/) records18February2026 assent (published19February); [INEC Chairman’s25February2026 speech](https://wp1.inecnigeria.org/speech-by-the-chairman-independent-national-electoral-commission-inec-prof-joash-o-amupitan-san-at-the-meeting-with-resident-electoral-commissioners-recs-wednesday-25th-february-2026-and-sw/) explains the new Act after the earlier election notice. The Electoral Act2022 is historical following the2026 repeal. This finding was reported to the user before sourcing.

Downloaded candidate: [INEC Electoral-Act-2026.pdf](https://inecnigeria.org/documents/Electoral-Act-2026.pdf), **official implementing agency**, but **Bill-form attachment**, not accepted as assented text. Better candidate: [NASS gazette11248](https://nass.gov.ng/documents/download/11248), **official legislature**, indexed as Gazette No40,2March2026,Vol113,Act1,A3–120; this is indexed identity, not local inspection.

File: `Electoral-Act-2026.pdf`. **124 PDF pages; 1,456,288 bytes; text layer: yes.** Native whitespace tokens: 39,520; per-page range 0–489. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-electoral-2026-inec/native-pages.json>).

SHA-256: `d051d7ab6b7ae14d94ddc7d9484bad583a09e4dbd82d2d08f030494f97c8c086`.

INEC arrangement PDF2–7 has156 rows; body8–76 has156 distinct labels. Schedules/forms77–122; native blank123–124. PDF8 explicitly says `A Bill`, has a blank commencement caption, and the file has no assent page. Body s154(PDF71) reads repeal of ElectoralAct13/2022; memorandumPDF1 same. That Bill reading alone is not proof of operative repeal; external official evidence establishes the2026 Act. A156/156 match does not cure instrument/version classification, so no catalogue was made. All156 assented arrangement/body rows remain untested.

The user separately approved an unknown-size manual direct save of NASS11248 as `Electoral-Act-2026-NASS-Gazette.pdf` into `round5-electoral-2026-nass-gazette/` and reported it saved. The folder remained empty. On the user’s instruction to find it, filename/size searches covered Round5 folders, Downloads, Desktop, Documents and home Spotlight matches for Electoral/eletoral/11248. No NASS candidate was found; only the existing INEC file was located. Filename-only search results included unrelated task PDFs, whose contents were not opened. No browser History database was queried. No file was moved, and the NASS origin denial was not bypassed. This search finding supersedes the earlier observations file’s “exact path clarification pending” wording; existing evidence files were not edited.

[PLAC18May2026](https://placng.org/Legist/nass-amends-new-electoral-act-raising-constitutional-questions/) reports further amendment Bills passed by House29April/Senate7May; no assent located. [NALTF13October2026](https://naltf.gov.ng/senate-reaffirms-electoral-act-2026-framework-ahead-of-2027-general-elections/) reports no further amendment before2027 and Supreme Court reinstatement of77(5)–(7)/84(2). Judgment not obtained; judicial reporting was not merged into the Bill. PLAC’s separate2026 PDF was discovered but not downloaded or proved equivalent.

Overlaps: constitutional elections framework, Evidence/election petitions, CAMA political funding and BOFIA financial contributions; no protected source/run inspected.

Remedy: the already-approved complete NASS11248 gazette, including cover, arrangement, body, schedules and assent, saved directly into the designated empty folder. Unknown actual size/SHA/pages/text layer for that absent file cannot be supplied. All156 rows need comparison against the assented version before a catalogue.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-electoral-2026-inec/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-electoral-2026-inec/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-electoral-2026-inec/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-electoral-2026-inec/source-and-currency-observations.json>).

## 18a. Banks and Other Financial Institutions Act2020 (BOFIA)

**NEEDS OCR ROUTE — scan has no native text; offline Vision complete;132 legible arrangement titles matched132 body labels; catalogue created.**

Source: [CBN BOFIA2020 PDF](https://www.cbn.gov.ng/out/2021/ccd/bofia%202020.pdf), **official regulator hosting gazette reproduction**. Gazette No183,17November2020,Vol107,GovernmentNotice163,Act5. As enacted, not consolidated. Initial approved Python GET returned403 and created no PDF; standard curl GET of the same approved URL saved one PDF directly in its empty law folder. This was not a NASS-origin retry.

File: `bofia 2020.pdf`. **88 PDF pages; 2,431,760 bytes; text layer: no.** Native whitespace tokens: 0; per-page range 0–0. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/native-pages.json>).

SHA-256: `d1879af57acf0d45113f6c88f4188ffc2b931dd1f97dcc27cc3b5c3dba248204`.

Every native page has0 words. Offline Vision processed all88 PDFKit pages; indices2,8,88 returned no text. Arrangement PDF3–7(A651–655), body9–85(A657–733), clerk86(A734), assent87. All132 arrangement titles are independently legible. Body raw numeric candidates give132 distinct1–132 labels after retaining/excluding six documented non-section references/quantity/header readings: `47 of this Act ;`(PDF13), `10 years...`(32), `37-42 of this Act...`/`12 of this Act.`(38), header `201 No.?.`(51), `81 (3) of the Constitution...`(77).

Vision omits arrangement numerals11(PDF3) and92(PDF6), reads `11l.`(111,PDF6) and `13l.`(131,PDF7). The images independently show11/92/111/131. Raw OCR is unchanged; the catalogue is a separately labelled visual transcription. Other alternatives include Vision `heid`/visual `held`(11), `hoiding`/`holding`(14), `eic.`/`etc.`(18), and `crisis`/visual `crises`(36,PDF4). Section67’s double terminal full stop remains in raw evidence; catalogue convention removes one terminal stop. Duplicate arrangement titles122/126 are retained.

Commencement PDF9 visibly12November2020. Assent PDF87 visibly typesets `I ASSENT`, `LS`, Muhammadu Buhari,12November2020; raw Vision `IASSINT`, `MunAmMAD BulARI`/`121h...` remain alternatives. ClerkPDF86–87 visibly Ojo,O.A.,13October2020; raw Vision `13ih Day of Octoher2020` remains untouched. [Presidency assent release](https://statehouse.gov.ng/president-buhari-assents-to-banks-and-other-financial-institution-act-2020/) corroborates12November2020. s130(PDF83) repeals CapB3 LFN2004 with savings.

[CBN2026 reform material](https://www.cbn.gov.ng/AboutCBN/Reforms.html) continues invoking BOFIA2020. [NASS Finance committee Bill listings](https://www.nass.gov.ng/committee/Finance), [NALTF13March2026 report](https://naltf.gov.ng/house-receives-landmark-report-to-protect-victims-of-banking-fraud/) and [NILDS2025 casual-staff amendment Bill](https://ir.nilds.gov.ng/handle/123456789/3171) do not establish assent. [FCCPC22April2026](https://fccpc.gov.ng/banks-answerable-to-fccpc-court-rules/) reports FHC/ABJ/CS/1972/2025 on banking consumer jurisdiction; judgment not obtained. No later enacted Act amendment/replacement located. Circulars/regulations and litigation effects are not incorporated here.

Overlaps: CAMA(s53), Money Laundering/Terrorism2022(s66), ISA2025, NDIC2023 external reference and tribunal/constitutional procedure.

Catalogue: `banks-and-other-financial-institutions-act-2020-section-titles.json`,132 titles, `needs_review`; no missing visual arrangement rows. Full substantive OCR acceptance is still required for ingestion.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/source-and-currency-observations.json>).

Offline OCR: [vision-raw.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/vision-raw.json>). Raw candidates, confidence and bounding boxes are retained.

## 18b. Investments and Securities Act2025 (ISA)

**READY TO INGEST — alternate SEC as-enacted source has358 legible arrangement titles and358 body labels; first copy remains blocked; catalogue created.**

SourceA: [first SEC attachment1326](https://sec.gov.ng/documents/1326/INVESTMENT-AND-SECURITIES-ACT-NIGERIA-2025_1.pdf). SourceB, preferred tested copy: [alternate SEC attachment1319](https://sec.gov.ng/documents/1319/Investments_and_Securities_Act_2025_x9rSXtI.pdf). Both are **official regulator hosts of gazette reproductions**, separately approved/downloaded into different new empty folders. Gazette No19,2May2025,Vol112,GovernmentNotice16,Act2. As enacted, not consolidated. [SEC Acts catalogue](https://sec.gov.ng/our-mandate/regulation/acts/) lists2025 alongside historical2007; its “1.4MB” label conflicts with A’s2,479,834bytes. B is1,515,300bytes; no identity was inferred from a size label.

**A — first SEC copy.** File: `INVESTMENT-AND-SECURITIES-ACT-NIGERIA-2025_1.pdf`. **196 PDF pages; 2,479,834 bytes; text layer: yes.** Native whitespace tokens: 79,489; per-page range 10–542. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/native-pages.json>).

SHA-256: `a90036ed02613bc34be872767b0f71879edf56f989e653dcba718ef3bf008a0b`.

**B — alternate SEC copy.** File: `Investments_and_Securities_Act_2025_x9rSXtI.pdf`. **196 PDF pages; 1,515,300 bytes; text layer: yes.** Native whitespace tokens: 79,895; per-page range 10–542. Every page count and raw page text: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/native-pages.json>).

SHA-256: `74c6a3ba75a3a283c0605f864aba9151cd6c0355e7098d25d4e4558505fb34c9`.

Both arrangements PDF3–13(A33–43) contain358 labels;14/A44 has only header content. Body15–178; schedules179–195; clerk195; assent196/A226. A’s body PDF127/A157 is horizontally mirrored and yields only10 native words from its header. A has356 readable native body labels, missing252/253, despite358 arrangement labels. It remains blocked and was neither flipped nor replaced.

B’s PDF127/A157 is visibly readable and yields416 native tokens, including raw `252.—(1)`/`253.—(1)`. B has358 distinct native body labels and all358 arrangement titles are visually legible across11 images. Its358-title catalogue is based solely on B, joining line-wrap whitespace, with raw lines retained. No numeral was supplied from A or from the expected sequence. B’s native part heading `PART IIII` atPDF3 versus visual `PART III` is recorded separately; part mappings are left empty. No section-number mismatch found in B. A’s cover/headers use singular `Investment`, and assent heading `IVESTMENTS`; B uses `Investments`. This test does not establish that127 is the only wording difference between the two PDFs.

B’s PDF196 visibly typesets `I ASSENT`, `LS`, Bola Ahmed Tinubu,25March2025; clerk Kamoru Ogunlana,6March2025; Senate4December2024/House12December2024. Commencement PDF15 is25March2025. Gazette coverA33–225 omits assentA226, retained as a range discrepancy. Typeset evidence is not signature authentication. The schedule’s Bill title is accompanied by assent and an Act-numbered body, unlike the unassented INEC attachment.

s356(1),PDF158/A188, repeals ISA29/2007; savings continue on159. [SEC January2026 capital circular](https://sec.gov.ng/for-investors/keep-track-of-circulars/revised-minimum-capital-mc-for-regulated-capital-market-entities/), [May2026 investment notice](https://www.sec.gov.ng/for-investors/keep-track-of-circulars/public-notice-unregistered-online-investment-schemes/) and [September2026 sustainability circular](https://home.sec.gov.ng/for-investors/keep-track-of-circulars/implementation-of-the-ifrs-sustainability-disclosure-standards-in-nigeria/) continue invoking ISA2025. No later enacted replacement/amendment located. Later SEC rules/circulars are not merged into the Act.

Overlaps: CAMA governance/mergers, BOFIA institutions/netting, PRA investment assets, Money Laundering/Terrorism obligations and tax/revenue subject matter. No protected tax run or Tier3 material sourced.

Catalogue: `investments-and-securities-act-2025-section-titles.json`,358 titles, `needs_review`, SHA-bound to B. No missing arrangement/body rows in B. A’s252/253 failure remains independently documented.

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/source-and-currency-observations.json>).

Evidence: [native-pages.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/native-pages.json>), [section-label-audit.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/section-label-audit.json>), [arrangement-body-label-table.md](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/arrangement-body-label-table.md>), [source-and-currency-observations.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/source-and-currency-observations.json>).

## Download permissions, routing and deviations

Each selected source was presented with filename, publisher/URL and HEAD size, or explicit unknown-size disclosure, before permission. Initial CAC/NRS browser saves explicitly selected the intended empty destination in the Save dialog. Browser security blocked access to Chrome download settings; user confirmations of settings did not reliably establish actual routing. No settings/origin workaround was used.

JRB original, its unintended duplicate and the pension bundle landed in the NRS folder. **The duplicate was downloaded without a fresh approval, and those saves broke the requested folder isolation.** The user then explicitly allowed in-place inspection of the original JRB/pension files and separate derived evidence, with deviations recorded. All three remain untouched there; none was moved, deleted or substituted. The duplicate’s size is recorded, but no content/hash comparison was performed.

Later per-file approvals explicitly allowed direct HTTP into new empty folders for M7, M6, both FOI copies, both SCUML Acts, INEC Electoral, CBN BOFIA and both SEC copies. Those exceptions did not authorize a general download policy or a bypass of the NASS origin denial. Unknown-size Ministry FOI was approved and ultimately153,279bytes. NTAA and NASS Electoral unknown-size manual saves were reported by the user but not established locally. No source was staged in Downloads and moved afterwards.

The earlier unavailable-download observations file was retained unchanged; the routing addendum supersedes its JRB absence finding. The final Electoral location-search result is recorded above, superseding its source observation’s pending-path wording. Incidental other-task tabs/UI and unrelated filenames were exposed during browser/state or filename searches; their contents were not used as statute evidence, and no actions were taken on those other runs.

## New title catalogues

All have `source.review_status: needs_review`; none has been marked verified.

- [nigeria-revenue-service-establishment-act-2025-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/nigeria-revenue-service-establishment-act-2025-section-titles.json>) —43 entries.

- [joint-revenue-board-of-nigeria-establishment-act-2025-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/joint-revenue-board-of-nigeria-establishment-act-2025-section-titles.json>) —61 entries.

- [marriage-act-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/marriage-act-section-titles.json>) —55 entries.

- [money-laundering-prevention-and-prohibition-act-2022-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/money-laundering-prevention-and-prohibition-act-2022-section-titles.json>) —31 entries.

- [terrorism-prevention-and-prohibition-act-2022-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/terrorism-prevention-and-prohibition-act-2022-section-titles.json>) —100 entries.

- [banks-and-other-financial-institutions-act-2020-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/banks-and-other-financial-institutions-act-2020-section-titles.json>) —132 entries.

- [investments-and-securities-act-2025-section-titles.json](</Users/amosgodwin/WebstormProjects/law-padi/backend/app/legal/data/investments-and-securities-act-2025-section-titles.json>) —358 entries.

## What was not verified

No statutory text, amount, date, cross-reference or OCR output has been approved as verified law. Source tests and catalogue acceptance gates are evidence only. Full substantive wording was not checked word for word against original gazettes or NASS certified true copies; neither digital/print authenticity nor handwritten signatures were authenticated. No exhaustive amendment/repeal/judgment history or2026 consolidation is claimed. Reported court decisions were not obtained or interpreted as incorporated statutory changes. Parliamentary passage/Bill listings were not treated as presidential assent.

No database, ingestion pipeline, existing verification flags, Docker containers, Compose command, commits or branch changes were used. No existing file was edited to make this report or a catalogue. No protected Nigeria Tax Act2025/Copyright2022 run or Tier1 source was tested. No old CITA/PITA/VAT/CGT Act was sourced. No Tier3 work began. No app imports, build/full-stack tests or database-dependent checks were necessary for this evidence-only work.

Validation is limited to new JSON syntax/catalogue counts, recorded source SHA-256 values, file/reference existence and this report’s inventory. It does not turn any item into verified legal content.

## Every repository file created

The following paths are relative to `/Users/amosgodwin/WebstormProjects/law-padi/`. This inventory includes originals, the unintended duplicate, raw extraction/OCR, images, evidence JSON, new catalogues and this report. Empty NTAA and NASS Electoral folders contain no files. JRB/pension originals are intentionally listed under their actual NRS location.

```text
backend/app/legal/data/banks-and-other-financial-institutions-act-2020-section-titles.json
backend/app/legal/data/investments-and-securities-act-2025-section-titles.json
backend/app/legal/data/joint-revenue-board-of-nigeria-establishment-act-2025-section-titles.json
backend/app/legal/data/marriage-act-section-titles.json
backend/app/legal/data/money-laundering-prevention-and-prohibition-act-2022-section-titles.json
backend/app/legal/data/nigeria-revenue-service-establishment-act-2025-section-titles.json
backend/app/legal/data/terrorism-prevention-and-prohibition-act-2022-section-titles.json
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/bofia 2020.pdf
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/download.json
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/native-pages.json
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page003.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page004.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page005.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page006.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page007.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page009.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page083.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page085.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page086.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/page087.png
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/section-label-audit.json
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-bofia-2020-cbn/vision-raw.json
backend/storage/statute-review/source-tests/round5-cama-2020-cac/CAMA-NOTE-BOOK-FULL-VERSION.pdf
backend/storage/statute-review/source-tests/round5-cama-2020-cac/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-cama-2020-cac/download.json
backend/storage/statute-review/source-tests/round5-cama-2020-cac/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-cama-2020-cac/native-pages.json
backend/storage/statute-review/source-tests/round5-cama-2020-cac/native-reading-order-raw.txt
backend/storage/statute-review/source-tests/round5-cama-2020-cac/page-001.png
backend/storage/statute-review/source-tests/round5-cama-2020-cac/page-007.png
backend/storage/statute-review/source-tests/round5-cama-2020-cac/page-031.png
backend/storage/statute-review/source-tests/round5-cama-2020-cac/page-091.png
backend/storage/statute-review/source-tests/round5-cama-2020-cac/page-527.png
backend/storage/statute-review/source-tests/round5-cama-2020-cac/page-528.png
backend/storage/statute-review/source-tests/round5-cama-2020-cac/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-cama-2020-cac/section-label-audit.json
backend/storage/statute-review/source-tests/round5-cama-2020-cac/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-cama-2020-cac/vision-key-pages-raw.json
backend/storage/statute-review/source-tests/round5-download-routing-addendum-2026-11-04.json
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/Electoral-Act-2026.pdf
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/download.json
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/native-pages.json
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/page008.png
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/page071.png
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/section-label-audit.json
backend/storage/statute-review/source-tests/round5-electoral-2026-inec/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/Freedom-Of-Information-Act-2011.pdf
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/download.json
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/native-pages.json
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/page001.png
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/page010.png
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/page011.png
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/section-label-audit.json
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-foi-2011-edo-judiciary/vision-raw.json
backend/storage/statute-review/source-tests/round5-foi-2011-justice/Freedom_Of_Information_Act.pdf
backend/storage/statute-review/source-tests/round5-foi-2011-justice/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-foi-2011-justice/download.json
backend/storage/statute-review/source-tests/round5-foi-2011-justice/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-foi-2011-justice/native-pages.json
backend/storage/statute-review/source-tests/round5-foi-2011-justice/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-foi-2011-justice/page001.png
backend/storage/statute-review/source-tests/round5-foi-2011-justice/page009.png
backend/storage/statute-review/source-tests/round5-foi-2011-justice/page010.png
backend/storage/statute-review/source-tests/round5-foi-2011-justice/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-foi-2011-justice/section-label-audit.json
backend/storage/statute-review/source-tests/round5-foi-2011-justice/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/INVESTMENT-AND-SECURITIES-ACT-NIGERIA-2025_1.pdf
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/download.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/native-pages.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/page010.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/page015.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/page127.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/page196.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/section-label-audit.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/Investments_and_Securities_Act_2025_x9rSXtI.pdf
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/download.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/native-pages.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page003.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page004.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page005.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page006.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page007.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page008.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page009.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page010.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page011.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page012.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page013.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page127.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/page196.png
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/section-label-audit.json
backend/storage/statute-review/source-tests/round5-investments-securities-2025-sec-alternate/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/native-pages.json
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/page001.png
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/page002.png
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/page003.png
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/page004.png
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/page034.png
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/page035.png
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/section-label-audit.json
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-joint-revenue-board-2025-taxombud/vision-raw.json
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/M6.pdf
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/download.json
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/native-pages.json
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/page001.png
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/page002.png
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/page034.png
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/page035.png
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/page036.png
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/section-label-audit.json
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-marriage-m6-plac/vision-key-pages-raw.json
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/M7.pdf
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/download.json
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/native-pages.json
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/page001.png
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/page002.png
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/page003.png
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/page004.png
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/page017.png
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/section-label-audit.json
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-matrimonial-causes-m7-plac/vision-key-pages-raw.json
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/MONEY-LAUNDERING-publication.pdf
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/download.json
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/native-pages.json
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/page003.png
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/page004.png
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/page027.png
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/section-label-audit.json
backend/storage/statute-review/source-tests/round5-money-laundering-2022-scuml/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/Joint-Revenue-Board-Est.-Act-2025 (1).pdf
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/Joint-Revenue-Board-Est.-Act-2025.pdf
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/NIGERIA_REVENUE_SERVICE_ESTABLISHMENT_ACT_2025_84bc74e1bf.pdf
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/download.json
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/native-pages.json
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/ng-government-gazette-dated-2014-05-20-no-62.pdf
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-001.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-003.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-004.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-005.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-020.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-029.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/page-030.png
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/section-label-audit.json
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-nigeria-revenue-service-2025-nrs/vision-raw.json
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/native-pages.json
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page023.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page024.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page025.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page026.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page027.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page028.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page029.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page034.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page039.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page042.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page043.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/page087.png
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/section-label-audit.json
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-pension-reform-2014-gazette/vision-raw.json
backend/storage/statute-review/source-tests/round5-per-page-word-counts-2026-11-04.json
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/TERRORISM-PREVENTION-publication.pdf
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/arrangement-body-label-table.md
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/download.json
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/native-layout-raw.txt
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/native-pages.json
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/native-raw-raw.txt
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/page003.png
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/page004.png
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/page005.png
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/page006.png
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/page089.png
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/pdfinfo.txt
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/section-label-audit.json
backend/storage/statute-review/source-tests/round5-terrorism-2022-scuml/source-and-currency-observations.json
backend/storage/statute-review/source-tests/round5-unavailable-download-observations-2026-11-04.json
docs/ocr-and-source-tests-round5-2026-11-04.md
```

Operational temporary artifacts: `/private/tmp/law_padi_round5_inspect.py` was created for isolated Poppler inspection. Existing earlier-round Swift helpers were reused, not edited. Swift generated compiler module-cache files beneath `/private/tmp/law-padi-round5-swift-cache/`; they are runtime cache artifacts, not source evidence or catalogue deliverables. No PDF was downloaded into a temporary directory. The report inventory above enumerates every created repository file; no temporary generated output is an alternate legal source.

