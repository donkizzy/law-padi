# Legal admin extraction review — 20 October 2026

This is an in-progress AI-assisted source-extraction audit, not certification by a human lawyer or verification of current consolidated law.

## Authority and scope

The user authorised repairs to the ingestion/review tools and continued review through the admin UI. The user subsequently expressly authorised approval of individually source-checked extraction candidates in the staged Police Act 2020 and ACJA 2015 runs. Source verification and publication are excluded. Uncertain candidates remain on hold.

The active public corpus remains the historical Constitution edition `draft-c8d50d87fae9`. Neither Act has been published in this review.

## Safety and source record

- A database safety dump was created at ignored path `backend/storage/backups/app-before-legal-review-20261020T122401Z.dump` before structural edits. It includes the first section-142 text revision.
- Police review run: `07e6dc81-c9d5-421c-83d5-1cb618a19578`.
- ACJA review run: `7b4b9bc4-0a9c-49d8-acfe-2344a16afe96`.
- Superseded cancelled runs are excluded from this review.
- The retained Police signed PDF has 57 pages. Body pages 5–53 and the statutory Schedule on page 54 are included. The explanatory memorandum and arrangement (1–4), Clerk authentication (55), and authentication/assent table (56–57) are excluded from legal body extraction while retained as provenance.
- The admin recorded boundary confirmation as run event 9. This invalidated earlier candidate approvals, which were subsequently reviewed and recorded again.

## Completed source comparisons and decisions

All 27 candidates under `police-act-2020.part17.` covering sections 135–142, including their existing and recovered children, were individually checked for text, identity, parentage, source pages, and source-span range. A final admin readback found no differences from the checked transcriptions. All 27 were approved under the user's explicit extraction-review authorisation.

The separately recovered `police-act-2020.schedule1` was compared with page 54 and approved. The original printed enumeration jumps from (xix) to (xxi); no item (xx) was invented.

Repairs include:

- Section 142 was separated from the merged Schedule and authentication material. Its wording and source mapping now end on page 53.
- The parser's section 14 near the end of the Act was corrected to section 141, Interpretation, based on pages 52–53.
- Missing section 138(1)(b), section 139(1), section 139(2), and the Schedule were recovered as separate candidates with retained origin evidence and individual review.
- Scan artefacts and marginal headings were removed from the checked provision bodies; child source ranges were narrowed where necessary.

Printed wording anomalies were preserved, including “made under to this Act” in section 135 of the retained signed copy, “Constitution of the Federal of Nigeria” in section 136, “is deem” in section 140(5), and the missing closing quotation mark in the final section-141 definition. They must not be silently harmonised with another source edition.

## Work remaining

Most Police Act candidates and all ACJA candidates remain to be individually checked. This document does not represent completion of the queue.

The Police Act arrangement labels the public-complaints Part XVI, but the retained body page 50 prints Part XV, duplicating the traffic-wardens Part number. The Gazette facsimile also prints XV in the body. A separate bodyless root was recovered as `police-act-2020.part15.source50`, preserving number 15 and documenting the disagreement. Sections 131–134 and their children were moved to that root. Five merged children were recovered: 133(2)(b), 133(2)(c), 133(5), 134(a), and 134(b). All 20 complaints body candidates passed final text/identity/hierarchy/page readback and were approved, together with the new root. The printed comma at the end of 132(2) and “Commissioner of Police a State” in 134 remain preserved.

The Part XVII root mapping was narrowed from a whole page to the five heading boxes and approved. The first checkpoint showed 50 approved Police Act candidates.

Traffic wardens Part XV and sections 120–130 (pages 47–50) have since been individually compared and corrected: 54 existing records plus nine recovered paragraphs, comprising 121(4)(b)–(c) and 126(b)–(h). A final readback explicitly checked all 63 unique candidate identities, text, metadata and full source-span arrays with no differences. All 63 were approved, bringing the recorded total to **113 Police Act candidates**. Printed anomalies remain preserved, including the age60/age55 inconsistency within123, “beyond the following grades” in126, the cross-reference to120 in125(b), and rank ranges in128(2).

Community policing Part XIV and sections113–119 (pages45–47) were subsequently compared and corrected. Section118's OCR identity11g was restored. Subsections115(1)–(3) and paragraphs119(1)(b)–(d) were recovered. All44 distinct candidates passed the full final readback and were approved. The admin confirmed **157 approved Police Act candidates**. The printed115(1) “Sub-Policing” versus115(2) “Policing” variation and references to116(1)(b) are preserved.

Special Constables Part XIII and sections105–112 (pages39–45) were then repaired. OCR missed the Part XIII heading, misread109 as199, merged111 into110, merged106(5)–(8) and108(4)–(9), placed108(5)(a)–(b) under108(3), and merged112(2)(b) into(a). The missing Part and16 provision candidates were recovered;57 original candidates were revised. All74 unique records passed final identity/text/hierarchy/order/page/source-box readback, then were approved. The admin confirmed **231 approved Police Act extraction candidates**. The printed drafting defects in108 and112, section106(4)'s proviso scope,109's introductory semicolon, and statutory cross-references were preserved with audit notes. Section106(8)'s closing parenthesis was checked in an enlarged scan rather than guessed.

Offences Part XII and sections96–104 (pages37–39) were subsequently repaired. The missing Part and19 provision records were recovered, including104 and its children, seven missing lettered paragraphs in96(1), and nine nested Roman items. The25 original offences candidates were corrected and reparented. All45 unique records passed final text/identity/hierarchy/order/page/source-box readback with no blocking issues, then were approved. Penalty figures and minimum terms were checked individually. Source102(1)(b)'s missing liability words and103's “is be construed” are preserved. Nested Roman items follow the printed source indents, with consequence wording retained in full parent text and no interpretation of its legal reach. The Gazette facsimile corroborated the Part XII heading and section96 layout. The admin confirmed **276 approved Police Act extraction candidates**.

Reward fund Part XI and sections91–95 (pages36–37) were then corrected. The two-line Part heading was completed. The false91(2) was restored as paragraph91(1)(e), and the true91(2) was recovered with the other five missing paragraphs. Its existing paragraph(a) was reparented to the correct recovered subsection. All22 unique candidates passed full readback with no blocking issues and were approved. Printed88(7), the lack of terminal punctuation in91(2)(a), “police. and” in(c), and the comma after “determined” in(d) were preserved. The admin confirmed **298 approved Police Act extraction candidates**.

Property and records Part X, sections88–90 (pages34–36), were then recovered and corrected. Only three original records survived: the Part,90 misidentified as99 with an unrelated99 heading, and a merged paragraph(a). Sections88–89 and their complete child records were missing. Thirty-seven candidates were recovered from the retained source scans and original200dpi OCR word boxes, and the three originals were corrected. All40 unique candidates passed final text/identity/hierarchy/order/page/source-box readback with no blocking issues. Each candidate's saved text and metadata were checked again immediately before approval, and the resulting queue count was verified after each decision. The admin confirmed **338 approved Police Act extraction candidates**. Printed wording such as “at least on three consecutive times”,89's singular “witness” heading, and “for everyday” was preserved.

Prevention Part IX and sections84–87 (page34) were then corrected. Section85 was misidentified35,87 as37,84 was omitted, and86 was merged into85. Four missing candidates were recovered and eight originals were corrected, including the complete two-line Part heading. All12 unique records passed full readback with no blocking findings and immediate field rechecks before approval. The admin confirmed **350 approved Police Act extraction candidates**.

Warrants Part VIII and sections71–83 (pages31–34) were then corrected. The Part heading had been misread VII[-, with 71 merged into70,80 into79,82–83 into81,76(2) into76(1), and83(2)(a)–(c) attached under81. The missing Part and11 body records were recovered, and36 original records were corrected. All48 passed final text, identity, parentage, order and source-box readback, then immediate field rechecks before approval. The admin confirmed **398 approved Police Act candidates**. Printed wording, recognizance/recognisance spelling variation, section72(1) introductory semicolon, marginal heading78 and statutory cross-references were preserved.

Section70 (page31) was then repaired separately. Its missing subsection(5), misread(3), was recovered. The root and11 total existing records were cleaned of marginal-heading/scan noise and merged Part VIII/71 text; source spans were narrowed to section70 alone. All12 unique records passed full readback and immediate approval rechecks, bringing the recorded total to **410 approved Police Act extraction candidates**. Printed “a misconduct” is preserved.

Statements, release and miscellaneous provisions60–69 (pages28–31) were subsequently repaired. Forty original candidates were corrected and five missing69(2)–(6) candidates were recovered. Page-crossing continuations in60(3) and64(1) were restored, marginal headings and stray group-heading text removed from provision bodies, and source word boxes narrowed. All45 distinct candidates passed full final readback and immediate pre-approval field checks, then were approved. The admin total is **455 approved Police Act extraction candidates**. Printed61(2) “have been ascertain”, recognisance/recognizance variations,66 cross-references and68 finger-print wording are preserved.

Search record/safeguards/execution sections57–59 (pages27–28) were subsequently repaired. Twenty-four original candidates were corrected and20 missing records recovered, including57(2)(j)–(k),58(5)–(7), four Roman items under58(5)(a), and the separate section59 with its children. The original58(4)(a)–(b) were reparented to58(5), while(c) belongs to59(4). A duplicate-path guard found an older record wrongly labelled59 whose source-page24 text is52. That root and its five existing descendants were relocated to52, remain unapproved and await their full text/hierarchy review. An erroneous intermediate path on the recovered59 was corrected before approval; all recovery/revision history remains audited. All44 source-checked search candidates passed full final readback and immediate decision-time checks, then were approved. The admin total is **499 approved Police Act extraction candidates**.

Search entry/action sections54–56 (pages26–27) were then corrected. The page27 continuation falsely labelled section7 was restored as56(2), with kind/number/path/parent corrected. Five missing subsections were recovered:55(2)–(3) and56(3)–(5). Existing55 paragraphs were reparented from55(1) to55(3). All16 records passed full readback and immediate field checks before approval. The admin total is **515 approved Police Act extraction candidates**. Source54 introductory semicolon and its heading “never exist” are preserved.

Search of arrested suspect section52 (page24), earlier falsely labelled59, was fully repaired. Eight missing records were recovered:52(2)–(7) and52(3)(a)–(b). Its six existing records were corrected; original paragraphs were reparented to52(2) and52(3). All14 passed full readback and immediate field rechecks before approval, bringing the Police total to529.

Intimate-search section53 (pages24–26) was then repaired. Thirteen missing subsections,15 lettered paragraphs and six nested Roman items were recovered, while10 original records were corrected. Merged paragraphs were placed under53(3),53(7) and53(8), with complete page-crossing text and precise source boxes. All44 candidates passed full readback and immediate pre-approval checks. The admin confirmed **573 approved Police Act extraction candidates**. Printed “might so use”, subsection13 cross-reference47 and subsection14’s unparenthesised13 were preserved. The review continued into21 October2026; the original audit filenames are retained.

Search powers/conduct sections48–51 (pages22–23) were then repaired. The false4g identity was corrected to48, while49(2)(e) and two Roman items under49(4)(b) were recovered. Forty-two original candidates were corrected and all45 candidates passed full readback and immediate decision checks. The admin total is **618 approved Police Act extraction candidates**. Printed49(2)(a) semicolon,49(4)(b)(i) “refer”,49(6) mixed quotation marks,50(1) reference51 and51(6) “cloth” were preserved. Enlarged source crops resolved punctuation and scan-noise questions.

Arrest/recording/inventory/reporting sections41–47 (pages20–22) were subsequently repaired. Section44 and its five subsections were recovered from the merged43 extraction, together with four Roman identification items; original lettered records were moved to44(1). Three43 subsections, all seven46 subsections and47(5) were recovered separately. Fourteen originals were corrected. All35 records passed full final readback and immediate decision checks before approval. The admin total is **653 approved Police Act extraction candidates**. Printed43 “reception of suspect”,46(7) “a proceed”, statutory cross-references and the44(2)48-hour limit were preserved. Enlarged source viewing confirmed46(6) includes both instances of “in the property”.

Humane treatment/arrest powers sections37–40 (pages18–20) were then corrected. Fourteen missing records were recovered:38(1)(h)–(n), five Roman items under(n), and40(5)–(6). Twenty-one original records were corrected, including narrowed38(1)(g), full page-crossing40(4), and the40 marginal heading falsely merged with41’s title. All35 passed full readback and immediate decision-time checks before approval. The admin total is **688 approved Police Act extraction candidates**. Printed38(1)(j)/(l) periods,38(1)(n)(v) trailing “and”,38(1)(f) “would have been punished”, and40 cross-references were preserved.

Part VII and arrest-rights sections31–36 (pages17–18) were corrected. Section33’s incorrect notification heading was restored to Mode of arrest;34’s heading and body OCR were corrected;35’s page continuation was retained. The Part root mapping was narrowed to the actual six heading boxes. All19 existing candidates passed full final readback and immediate approval checks. The admin total is **707 approved Police Act extraction candidates**. Internal A–E cross-headings are separately pending structural preservation; their omission is not treated as completion of the hierarchy audit.

The printed internal cross-headings A–E in Part VII have now been preserved with a distinct cross_heading kind: A Investigation and Arrest, B Search, C Statements, D Release of arrested suspect and E Miscellaneous. All five heading records were source-checked and approved. Forty previously checked section roots31–70 were moved beneath the corresponding printed heading and each was individually reapproved only after rereading its complete unchanged text, identity, order, pages and source-box arrays. Canonical section paths and child identities were retained. The admin total is **712 approved Police Act extraction candidates**.

The cross-heading tooling change passed701 backend tests with4 skipped and89% coverage; app Mypy and ty, Ruff, frontend build and scoped Biome checks passed. The live admin recovery and reparenting flow was exercised. The running local service and static admin bundle were refreshed; no source verification, materialisation or publication was performed.

Financial Part VI and sections26–30 (pages15–17) were then repaired. Six missing records were recovered:26(1)(d)–(f), two Roman items under26(1)(e), and26(2)(b). Thirty-six originals were corrected, including page-crossing26(1)(f)/29(2), actual Part heading mapping, reporting dates and marginal headings. All42 candidates passed full final readback and immediate approval checks. The admin total is **754 approved Police Act extraction candidates**. Source26 mixed quotation marks,27(1)(e)’s lack of terminal punctuation,30’s “with regards” and all printed fractions/deadlines/cross-references were retained.

Remuneration/supernumerary sections20–25 (pages13–15) were subsequently repaired. Four Roman items under21(3)(d) and21(4)(b) were recovered;42 original records were corrected, including full21(5) continuation and narrow per-provision source spans. All46 candidates passed final readback and immediate approval checks. The admin total is **800 approved Police Act extraction candidates**. Printed23(3)(b) reference15,24(2)(d) reference20,25(2) “life time”,25(4) “that worn”,25(5) Pensions Reform Act, notice periods and rank limits were preserved.

General administration Part V and oath/recruitment/training sections17–19 (pages11–13) were then corrected. The missing19(4) was recovered from19(3);34 originals were corrected with complete page-crossing18(6)/19(3), precise word boxes and actual Part/marginal headings. All35 passed final readback and immediate approval checks. The admin total is **835 approved Police Act extraction candidates**. Recruitment membership/delegation ranks, the printed2020 provision18(8)35-year/60-year text,19(2)’s five-year training-review interval and specialised/specialized variation were preserved. This remains an as-enacted extraction audit, not an assertion of current amended recruitment law.

Appointment/functions Part IV and sections11–16 (pages9–11) were then repaired. All30 existing candidates were corrected, including the complete three-line Part heading, missing11 marginal heading, page-crossing11/16 text and narrow source word boxes. All30 passed full final readback and immediate approval checks. The admin total is **865 approved Police Act extraction candidates**. Printed13(1) “Subject to the provisions this Act”,13(1)(b) “sections4”,12(5) “maybe” and16(4) reference(1) were preserved.

Inspector-General Part III and sections7–10 (pages8–9) were then repaired. The missing Part root and seven9(1) paragraphs were recovered. Twenty-three originals were corrected:7–10 were moved from Part II toIII, false49 was restored as10, and the spurious cross-reference-derived9(2) record was restored to the complete actual subsection with(a)–(c) reparented beneath it. The actual two-line Part heading and marginal7 heading were retained. All31 passed full final readback and immediate approval checks. The admin total is **896 approved Police Act extraction candidates**. Printed7(4) extra “of”,9(3)’s missing terminal punctuation, statutory references and the2020 term/re-engagement wording were preserved. Enlarged viewing confirmed9(2)(c) reads “section5(2)”.

The comparison record is in `docs/legal-admin-source-comparisons-2026-10-20.json`; the live admin audit retains full source mappings and reasons. Police sections1–6 have now been completed; ACJA remains pending.

## Tooling changes and validation

The admin now supports audited structure/source-mapping edits, recovering missing provisions without altering the origin, nullable metadata clearing, page/path filters, readable audit reasons, and imported-run boundary confirmation. Graph validation rejects duplicate paths, cycles, cross-run parents, invalid page ranges, and edits to cancelled/materialised candidates. Raw source extractions and before/after snapshots are retained.

The latest full isolated backend run passed **700 tests,4 skipped,89% coverage**. Structural recovery allows a bodyless Part/Chapter only when it has a heading. A live reparenting save exposed a UUID audit-serialization bug; the failed transaction rolled back, the serializer was repaired, and non-null reparenting regression coverage was added. All54 admin backend tests also passed separately. Application Mypy/ty, Ruff, frontend build and Biome passed. Explicitly checking the whole legacy test file with Mypy also reports pre-existing fixture/type errors; these are outside the application type-check scope. Authored frontend regression specs have not yet been run as a suite; the live recovery, metadata-only structure, reparenting, filtering, readback and approval flows were checked through computer use.

## Police Act opening provisions and completion checkpoint (21 October 2026)

Sections1–6 and PartsI–II were source checked on PDF pages5–7. Section2 and its eight paragraphs had been misidentified as42; the original nine candidates were corrected in place. Paragraph3(2)(e) and Roman items6(3)(d)(i)–(ii) were recovered through the admin. All54 original candidates received corrected text, identity, headings and narrow source mappings. All57 records passed full readback, with printed2(h), repeated “accused persons” in5(2), the two “and” conjunctions in4(g)/(h), and all source cross-references preserved.

The extraction queue now contains **953 approved Police Act candidates and zero pending candidates**. A read-only audit confirmed142 section roots, exactly1–142, with no repeated/unexpected/missing sections, duplicate paths, invalid/cyclic parent links, missing source spans or mappings to excluded pages. The obsolete original graph-arrangement finding (124 parsed roots/default145 expected) was resolved through an explicit superuser resolution in the admin with this evidence. Raw extraction findings remain in the audit history. Source verification remains `needs_review`; no candidates have been materialised and no Act has been published.

The admin now exposes the existing issue-resolution API with structured evidence and a separately required blocking-override reason. Ordinary legal reviewers cannot override blocking findings. The frontend build and two focused mocked UI regressions passed (evidence/object validation, explicit override and role restriction); live resolution and final extraction approval were verified through computer use. The earlier cross-heading backend suite passed701 tests,4 skipped,89% coverage.

Final Police audit after resolving65 obsolete non-blocking findings through individual admin forms: **953 approved; zero pending candidates; zero open review issues**. All1–142 roots remain unique; parent/source checks pass; source verification remains pending and materialised count is0. Each confidence/numbering resolution contains source-page evidence and candidate identity, with all original findings retained.

## ACJA2015 review started (21 October 2026)

The retained243-page PDF boundaries were visually checked at the beginning/end of the body and Schedules, with source text/location checks across the document. Included pages15–241; excluded cover/memorandum/arrangement1–14 and authentication/assent242–243 as retained provenance. The boundary confirmation is run event9. No source verification or publication was performed.

Opening sections1–5 and Parts1–2 on PDF page15 were corrected:14 originals, precise source boxes, clean marginal headings and false page16 continuations removed. All14 passed full saved-field readback. **13 candidates were individually approved**; Part1 remains revised and on hold for the run-wide arrangement reconciliation after the rest of the Act is reviewed. Enlarged source inspection confirmed section3 punctuation; the printed section86 cross-reference in2(1), Court Martial exclusion and source wording were preserved. Sections6–495 and Schedules remain pending.

ACJA sections6–9 (PDF pages16–17):10 missing provisions were recovered, including6(2),8(1)(b),8(2)–(4),9(2)–(4) and9(2)(a)–(b). All15 original records were corrected;6(2)(a)–(c) and9(2)(c)–(d) were restored to their proper parents. The unnumbered6(2) proviso remains in its parent text;6(2)(c) keeps its printed colon. All25 passed full field/source readback without blockers and were individually approved. **ACJA approved total:38.**

ACJA sections10–13 (PDF pages17–18): recovered10(2)–(7), the missing section11 from the merged10 extraction, and12(3)(b). All8 originals were corrected and all16 records passed full readback without blockers before individual approval. Enlarged images confirmed and preserved the source full stops before “whether” in12(2), before “and may” in12(3)(b), and before “is detained” in13;10(7) retains “a proceed of offence”. **ACJA approved total:54.** Section13 raw text also contains14, which remains available in audit history for the next recovery.

ACJA sections14–17 (PDF pages18–20): recovered both missing section roots14/17 with their missing children, four Roman identification items15(1)(d)(i)–(iv), and actual16(3). Original16(3)–(5) were restored in place to17(3)–(5), preserving their IDs. Sixteen originals were corrected; all28 final candidates passed full source/metadata readback without blockers and were individually approved. Printed singular “reception of suspect” in14(1), “of arrested suspect” in15(5), 48-hour recording limit,30-day registry deadline, voluntary statement wording and Organization spelling were retained. Enlarged inspection distinguished scan noise after15(5)’s “confession” from punctuation. **ACJA approved total:82.**

ACJA sections18–19 (PDF pages20–22): recovered all12 printed paragraphs18(1)(a)–(l) and18(2); seven originals were corrected. All20 records passed full readback without blockers and were individually approved. Enlarged source crops confirmed the colons after “thing” in18(1)(d) and “Nigeria” in18(1)(e), which were preserved;18(1)(j) retains the printed “whose arrest a warrant” wording, and(l) was not converted to OCR digit1. Section19’s24-hour limit, recognizance spelling and page22 continuation were preserved. **ACJA approved total:102.**

ACJA sections20–23 (PDF page22): recovered23(4)–(7), corrected seven originals and separated all handover subsections. All11 passed full readback without blockers and were individually approved. The actual singular “Arrest by private person” marginal heading was used;21’s “servants, agent”,23(4)’s “authorized”,23(6)’s printed second “an-offence” and23(7)’s “sub section(2)” wording were preserved. **ACJA approved total:113.**

ACJA sections24–29 (PDF pages22–24): recovered29(4)–(5), corrected eleven originals and restored source continuations. All13 final records passed full field/source readback without blockers and were individually approved. Printed25(2) “either section23 or24”,29(2) “make arrest”,29(5) “Federal and State level”, and26’s comma before “or Justice” were retained. Enlarged viewing confirmed29(3) has lower-case “section15”. **ACJA approved total:126.**

ACJA sections30–34 (PDF pages24–26): recovered33(3)–(6) and34(5), corrected25 originals and removed the Part3 heading from34. Page-specific source-column limits prevent marginal headings entering the source body mappings. All30 records passed full readback without blockers and were individually approved. Printed24-hour periods, monthly inspection,31(2) “situate”,33(3) “advice”,34(4) “an arrests”,34(5) “a misconduct” and Police Regulation singular were preserved. **ACJA approved total:156.**

ACJA Part3 and sections35–40 (PDF pages26–27): recovered the missing bodyless WARRANTS Part root and section39 with its three subsections. Twelve originals were corrected and moved from incorrect Part2 to3, retaining IDs and parent-child links. All17 passed full field/source readback without blockers and were individually approved. Section40(2) retains singular “requirement”. Retrieval ancestry is rebuilt from canonical parent links rather than the retained original parser-heading hints. **ACJA approved total:173.** Remaining warrant provisions41 onwards still require review and any necessary reparenting.

ACJA sections41–44 (PDF page27): recovered42(1)(b)–(c), corrected/moved eleven originals from Part2 to3 and restored missing actual marginal headings. All13 passed full field/source readback without blockers and were individually approved. Enlarged viewing confirmed42(1)(b) “place. in”;43(3) capital “Police”,43(4) references44/45 and the printed30-day summons interval were retained. **ACJA approved total:186.**

ACJA sections45–49 (PDF pages27–29): recovered45(2)–(5) and46(3), corrected/moved16 originals to Part3, and restored45(a)–(d) beneath actual45(2). All21 passed full field/source readback without blockers before individual approval. Printed45(4) punctuation,46(2)(a) “division or district of which he was arrested”, cross-references and the full46(2)(b) page29 continuation were retained. **ACJA approved total:207.**

ACJA Part4 and sections50–55 (PDF pages29–30): restored both omitted section roots50/51,50(1)–(2),53(1)–(2),53(2)(a)–(c) and54(2)(b). Twelve originals were corrected, including the missing second-line BEHAVIOUR in the Part title. Unnumbered conclusions remain in54(1) and55 parent text only. Enlarged inspection confirmed printed54(2)(a) “Abuja. and”,54(2)(b) “suspect is. is” and55’s “Part.”; these were retained. All22 passed full field/source readback without blockers and were individually approved. **ACJA approved total:229.**

ACJA sections56–61 (PDF pages30–32): recovered56(e)–(f) and57(b)–(d), corrected13 originals and restored the misread section39 root/subsections to actual59 while preserving IDs. Unnumbered56 conclusion remains in parent only. Enlarged viewing confirmed57(c) “force; and” and56’s “period;”;56(e) retains printed “commission of, offence”. All18 passed complete source/metadata readback without blockers and were individually approved. **ACJA approved total:247.**

ACJA sections62–64 (PDF pages32–33): restored62(2)–(6),62(4)(a)–(b) and63(1)(b)–(c), corrected12 originals and moved62’s original lettered paragraphs to actual subsections3/4. Subsection3’s unnumbered conclusion remains in the parent only; the page33 “otherwise” continuation is included in62(5). Printed62(4)(b) reference58,63 reference164 and64 reference59 were retained. Both former blocking extraction defects in62 were resolved by corrected text/source mapping. All21 passed full field/source readback without blockers and were individually approved. **ACJA approved total:268.**

ACJA Part5 and sections65–71 (PDF pages33–34): recovered section67 from merged66 and71(4), corrected12 originals and completed the second-line Part title FURNISH SECURITY. Printed65(1) terminal comma,66 “counseling”,68 “in of this section”, and71(3) “Magistrate. the” were preserved; enlarged71 inspection confirmed the full stop. Section70’s prior blocking extraction issue cleared through source/text repair. All14 passed full readback without blockers and were individually approved. **ACJA approved total:282.**

ACJA Part6 and sections72–79 (PDF pages34–36): recovered72(a)–(b),74(a)–(b),75(b) and77(a)–(b); corrected18 originals. Cross-page72(b) and77 continuations, service details, statutory fine amounts and six/12-month imprisonment terms were checked against the scan. Printed77 “acts…is not performed”, reference75/76(2)(a) and78(2)’s unusual “immediately disobeying” wording were preserved. Three prior blocking extraction issues across75/77 cleared through corrected text/source mapping. All25 passed full field/source readback without blockers and were individually approved. **ACJA approved total:307.**

ACJA Part7 and sections80–85 (PDF pages36–37): recovered omitted80,82(2),82(1)(b) and83(1)(b); corrected14 originals and completed Part title WARRANT. Source82(1)(b) retains its full indented operative tail. Enlarged scan checks confirmed81(2) “Where,” and “summons. the”,82(1)(a) “and.”;82(2) retains “net proceed” and printed reference80. Three prior blocking83 extraction defects cleared through text/source repair. All18 passed full readback without blockers and were individually approved. **ACJA approved total:325.** User authorized parallel sub-agents; source-only preparation now runs in distinct blocks, with all admin changes/decisions retained in parent session.

ACJA Part8 and sections86–92 (PDF pages37–39): parallel source package used to restore89(5) and omitted section90, correct13 originals and complete GENERAL in the Part title. Source89(2) reference54, authorized spelling,91’s three refuted occurrences and92’s complete six-year limit/official-capacity exception were preserved. All15 passed complete admin field/source readback without blockers and were individually approved. **ACJA approved total:340.** Parallel source work also discovered repeated body scan blocks; a dedicated full-PDF audit is underway before final boundary/arrangement reconciliation.

ACJA Part9 and sections93–103 (PDF pages39–41): parallel source packages used to restore11 missing provisions, including section98 with four subsections,93(1)(d),100(1)(a)–(b),101(a)–(b),102(2). Corrected27 originals. Source93 “denied”,100 “custody: a warrant”,101 “continued. or”/“custody.”,102 “having regards” and103 “in all respect” were preserved;99(b) retains its indented operative tail, while96/101/102 conclusions remain in their parent texts. All38 passed full readback without blockers and were individually approved. Parent-counted approvals:378 before concurrent agent approvals. Agents now own exclusive ranges121–160,161–200,201–250 in separate admin tabs; source checks and admin checkpoints are kept separate for final audit.

ACJA Part10 and sections104–106 (PDF pages41–42): recovered106(a)–(c), corrected nine originals and restored section105/subsection paths from OCR10s while retaining IDs/sort keys. Printed104 authorize,105 Attorney General without hyphen,106 authorised/authorized spellings and all statutory powers were retained. All12 passed full field/span readback without blockers and were individually approved. Parent-counted approvals:390 before concurrent agents.

ACJA Part11 and sections107–108 (PDF pages42–43): recovered107(2)–(4),107(2)(b),107(3)(a),108(2)(b); corrected12 originals and moved original107(a)/(b) beneath printed107(2)/107(3). Completed ATTORNEY-GENERAL in Part title. Source108 duplicated may and discharged of the offence retained; complete107(3)(b) page43 notice continuation preserved. All18 passed full field/span readback without blockers and were individually approved. Parent-counted approvals:408 before concurrent agents. Continuation22Oct resumed the remaining nine decisions after checking persisted state; no decisions repeated.

22Oct parallel completion, sections121–160 and Parts16–19:119 source-checked records approved after complete saved metadata/text/span verification, with zero differences/blockers/held items.89 originals corrected and30 omissions recovered;138 identity restored from38 while retaining ID/sort. Parent independently adjudicated140(1) interword point as scan contamination (any defect); agent adjudicated160 child/to speck and retained raw source history. Full result/adjudications: /private/tmp/law-padi-legal-review/a121-result.json. Parent-owned109–120 remains in progress, so this later completed range does not imply continuous completion through160.

ACJA Part12 and sections109–111 (PDF pages43–45): recovered20 missing paragraphs/subsections, corrected14 originals and restored111(a) beneath actual111(2). All34 unique candidates passed complete saved text/identity/hierarchy/order/page/span readback with no differences or blockers and were individually approved. Printed111(1), despite OCR(4), the90/180-day periods, capital Awaiting Trial Persons,110(3)/(4) references(a) and(b),110(5) his Court and110(7) Monitoring Committee comma were retained. Parent-counted approvals:442 before concurrent agents. Source verification, materialisation and publication remain excluded.

## ACJA 2015 completion pass (22–23 October 2026)

### Working files and the 22 October reboot

A machine reboot on 22 October cleared `/private/tmp`, deleting the earlier working folder `/private/tmp/law-padi-legal-review/` (including `a121-result.json`, the full duplicate-page audit and the agents' interim packages cited above). The database was unaffected; a read-only check confirmed every write made before the reboot. All later work lives in the git-ignored `backend/storage/statute-review/acja-2015/review-work/`, which holds the source-check packages (`acja-*-source-check.json`), per-range plans (`x*-plan.json`), builders and evidence crops, page renders, the duplicate-page audit summary, apply/reject logs and `final-audit-acja.json`.

### Source checking

The remaining ranges were transcribed word by word from the scan and mapped to existing candidates: sections 112–120, 187–200, 241–250, 270–305, 306–350, 351–410, 411–460, 461–495, and the four Schedules (pp. 204–241). Each package's builder asserts that spans are byte-identical copies of the original OCR spans, that paths are unique, that parents are known, that section numbering is complete, and that sort order equals printed order. Printed anomalies (wording, punctuation, cross-references, spelling variants, skipped paragraph letters) are kept and listed in each package; OCR corrections were confirmed on enlarged crops. Reviewer rulings:

- 270(5) reads "subsection (3)" (degraded on every copy; matches the printed glyph and the plea-agreement scheme). 277(4) reads "tried".
- 112(6)(c), 189(f)(iv) and 245(1)(a) end with semicolons (faded tails consistent with the list).
- Section 468 has no printed "(1)"; the opening words are recorded as subsection (1) without a number.
- The body prints a second "PART 48 – FEES AND MISCELLANEOUS PROVISIONS" on p. 198 (Part 49 in the arrangement). It is recorded as `acja-2015.part48.source198`, following the Police Act Part XV precedent.
- Schedules: First (Forms 1–21 and an unnumbered Notice of Trial), Second (charges; no original root existed), Third (23 information precedents) and Fourth (13 items). Blanks are rendered as "…". Schedule roots carry their printed caption as text, because the admin cannot save an empty body.

### Applying the plans

Admin-UI entry worked (sections 306–307 were revised, recovered and approved through the UI) but did not scale: spans run to megabytes per range, and parallel admin tabs exhausted the browser's connections to the API. With the user's agreement, the plans were applied by `review-work/tools/apply.py`, which calls the same service functions as the admin API (`update_review_candidate`, `derive_review_candidate`, `decide_review_candidate`). Changes are recorded as the superuser, with per-record reasons and the normal revision and audit history. A record is approved only when its saved text, heading, identity, parent, sort key, pages and spans read back exactly and it has no open blocking issue.

Corrections made during the pass:

- Fourteen recovered children in sections 241–250 were first attached to duplicate-scan parents that still occupied the Part 25 paths. Their parent links were corrected and they were re-approved after an exact readback.
- Sections 222 and 233 (approved in earlier sessions) carried sort keys inherited from re-scan copies (`00314`, `00316`). They were re-keyed to `00231.9995` and `00242.5`, then re-approved with text and spans unchanged.
- Rejected candidates still occupy their canonical paths. So the 19 re-scan copies blocking sections 241–250 were moved to `acja-2015.rejected-duplicate.p<page>.…` and rejected again.

### Rejections

- **290 duplicate-scan copies** were rejected: 288 extracted only from pages 85–136, plus 2 copies of section 277 that also run onto page 137. Pages 85–136 re-scan pages 59–84 (26 three-page groups, reconfirmed visually for 59/85/111). Each reason names the audit group and the approved first-occurrence record holding the same printed text; 80–100% of each copy's words are covered by approved first-occurrence records, the rest being OCR noise.
- **9 junk fragments** were rejected after checking their text against approved records: two empty whole-page extractions (pp. 48 and 73), a fragment of the section 333 marginal note, two fragments of the former "section 1960" (section 494), a First Schedule aggregate spanning pp. 211–223, and a three-record page-60 re-extraction of section 176. The authentication-page candidate was not rejected; it was revised in place into Third Schedule precedent 1, and its original extraction is kept in the revision history.

### Final audit (23 October 2026)

`review-work/tools/final_audit.py`, read-only:

- **ACJA run `7b4b9bc4` (before the overrides below):** 1,970 approved, 299 rejected and 8 needs review; 0 materialised.
- **Sections:** 1–495 each occur exactly once, with none missing, repeated or unexpected.
- **Structure:** no duplicate live paths or sort keys. Every live parent is live, and every path sits under its parent. Section and Part/Schedule order equals printed order.
- **Spans:** every live record has spans, and none come from excluded pages (1–14, 242–243) or duplicate pages (85–136).
- **Findings:** 67 obsolete non-blocking findings (numbering gaps now filled; low OCR confidence superseded by the word-by-word check) were resolved with evidence.
- **Police Act run `07e6dc81`:** 953 approved, 0 materialised.
- **Excluded throughout:** source verification remains `needs_review`; nothing was materialised or published.

### Blocking findings cleared (23 October 2026)

With the user's explicit authorisation, the 8 remaining blocking findings were cleared through the superuser override, each with the scan evidence below. The records were then approved only after an exact readback (`review-work/resolve-blocking-2026-10-23.json`):

- 481 and 481(c) (p. 195): the print has an unmatched "(the corporation".
- First Schedule Forms 8 (pp. 210–211) and 11 (p. 213), Second Schedule charge 9 (p. 224) and the Fourth Schedule warrant (item 7, p. 237): brackets are left unclosed in the printed forms. Each was checked on the scan and is reproduced as printed.
- Third Schedule precedent 6 (p. 227): spans cover every word of the text; the low span precision is OCR noise on dotted fill-in lines. The override evidence lists pages 227 and 230 in error; the record itself is on p. 227 only.
- Part 1 root ("PART 1 – PRELIMINARY", p. 15): arrangement reconciliation closed. The body holds sections 1–495 exactly once, and the arrangement's numbering runs to 495. The arrangement's Part 49 appears in the body as a second Part 48 on p. 198, preserved as printed.

**Final state:** ACJA run `7b4b9bc4` has 1,978 approved, 299 rejected, 0 pending and 0 open issues; all seven range plans read back exactly. Police Act run `07e6dc81` has 953 approved. Neither Act has been source-verified, materialised or published.

Source defects that cannot be fixed from this scan:

1. **Section 120 is misprinted.** It prints section 121's summons wording under the marginal note "Discretion in *ex parte* application". It is retained as printed; the true text needs another official copy.
2. **A page is missing between PDF pp. 211 and 212.** First Schedule Form 8 is truncated and flagged `source_incomplete`; Form 9 is held rather than reconstructed.

## Second-source comparison and First Schedule Forms 8–9 (23 October 2026)

The retained scan was downloaded from the Federal Ministry of Justice website. At the user's request it was compared with two further editions, saved in the git-ignored `backend/storage/statute-review/acja-2015/second-sources/`:

- policinglaw.info `2015_Administration_of_Criminal_Justice_Act.pdf` (292 pages, sha256 `acd895f9…c4335`)
- corruptioncases.ng `Administration of Criminal Justice Act (ACJA) 2015.pdf` (189 pages, sha256 `a653231d…48939`)

Both were generated from Word documents, so they are retyped editions, not facsimiles of the printed Act. The comparison is recorded in `review-work/second-source-comparison-2026-10-23.json`.

**Section 120.** All three editions print section 121's summons wording as section 120, under the marginal note "Discretion in *ex parte* application." The defect is in the Act as published, not in the scan. Section 120 stays as printed; the intended text is not available from these sources. The retyped editions read "duplicate," where the scan reads "duplicate;"; the scan reading is kept.

**Forms 8 and 9.** The two retyped editions agree word for word on the text lost with the scan's missing page, and they match every surviving word of the scan:

- Form 8: 390 of 391 words in order; the one difference is where "Applicant" falls in the layout.
- Form 9: its surviving tail on scan p. 212 matches exactly.

With the user's authorisation:

- **Form 8** (`schedule1.item8`) was completed. The scan text through "(v) Name:" is unchanged; witness (v)–(vi) details, items 10–12 and the signature block were added from the retyped editions.
- **Form 9** (`schedule1.item9`, "INFORMATION ON LEGAL REPRESENTATION", Section 376 (9)) was restored by revising the rejected pp. 211–223 aggregate. The original extraction remains in its revision history. Text from "Signature of the Prison official…" onward is the scan reading with its p. 212 spans. The form number, title and opening paragraphs come from the retyped editions.

Both records were approved after an exact readback, and their revision reasons name both sources and their hashes. The added wording has no source spans in the retained document, by design.

The Form 8 revision re-raised its printed unclosed-bracket finding. That finding was cleared with the missing-page provenance wording; its substantive basis is the scan-verified unclosed parentheses recorded in the 23 October overrides above.

**Final state:** ACJA run `7b4b9bc4` has 1,979 approved, 298 rejected, 0 pending and 0 open issues; sections 1–495 are present exactly once.

### Reader notices

Provision-level reader notices are now built. `backend/app/legal/data/provision-notices.json` keys each notice by canonical path, and a notice also applies to every provision beneath that path. `app/legal/notices.py` attaches notices to provision references, search results and evidence items as `notices` (each with `code`, `params` and the English `text`). The frontend shows them, through `ProvisionNotices`, on Browse and section pages, in Find results, in the chat source panel, and under chat answers for the sources an answer cites. Strings are translated by code in all five reader languages; the Pidgin, Yorùbá, Hausa and Igbo strings are unreviewed drafts, like the rest of those catalogues.

Notices in force:

- `acja-2015.part15.section120` (`repeats_other_provision`): "The published Act prints the same wording here as section 121, under the heading “Discretion in ex parte application”. The intended text of section 120 is not known from any available copy."
- `acja-2015.schedule1.item8` and `acja-2015.schedule1.item9` (`missing_page_secondary_source`): "Part of this form is missing from the official scan used here. The missing wording comes from two independent retyped editions of the Act that agree with each other and with the surviving scan."

Tests: `backend/tests/legal/test_notices.py`, and a mocked Playwright case in `frontend/tests/laws.spec.ts` covering the section page and source panel. The notices reach readers once ACJA is source-verified, materialised and published; the running API container must be rebuilt to serve the new field.

## Source verification and materialisation (23 October 2026)

### Pre-flight audit

A read-only audit found no pending candidates or open issues on either live run. Both runs' page boundaries were already confirmed (Police Act 20 October, ACJA 21 October). Pressing **Confirm reviewed boundaries** again returns every approved candidate to needs review, so it was not pressed.

Two defects blocked the hand-off, and both were fixed with regression tests:

- **Rejected candidates blocked completion.** The review gate (`service.py`) and the materialisation worker (`worker.py`) counted rejected candidates as unfinished, and counted open findings on rejected records as blocking. ACJA's 298 rejected duplicates and 46 findings on them would have held the run at review forever. Rejection is now treated as a final decision: rejected candidates are never materialised and their findings do not block.
- **Nested paragraph citations were truncated in retrieval text.** `citation_for_provision` kept only one paragraph level, so ACJA 123(b)(i)–(vi) were all cited "Section 123(b)". Every level is now kept ("Section 123(b)(iv)"). Reader-facing citations in `public_corpus.py` were already correct.

### Actions, with the user's authorisation

- A safety dump was taken at ignored path `backend/storage/backups/app-before-materialize-acts-20261023T100456Z.dump`.
- Both source documents were verified through `verify_source_document` as the as-enacted historical editions. Each reason records the known defects: ACJA section 120 and the missing page for Forms 8–9, and the Police Act Part XV/XVI numbering.
- The worker ran inside the backend container, with `INGESTION_ALLOWED_INSTRUMENT_TYPES=["constitution","act"]` set for that command only; `.env` is unchanged. The first local attempt failed on the container-only storage path and rolled back with nothing written. Both runs were retried through `retry_ingestion_run`.
- A rebuild of retrieval documents with corrected citations was refused by the immutable artifact store. The original artifacts were kept, and both runs were restored to ready to embed with a `retrieval_documents_rebuild_withdrawn` event. The corrected citations take effect when the composite release rebuilds retrieval documents. The per-run member artifacts keep the truncated citations, so nested Roman items are re-embedded at composition.

### Result

A post-materialisation audit compared every live candidate with its provision: identity, kind, number, heading, sort key, parent and version text all match, and every version has historical status. No rejected candidate was materialised.

| Run | Source | Candidates | Release entries | Retrieval documents | State |
| --- | --- | --- | --- | --- | --- |
| ACJA `7b4b9bc4` | verified | 1,979 materialised, 298 rejected | 1,930 | 1,948 | ready to embed |
| Police Act `07e6dc81` | verified | 953 materialised | 931 | 938 | ready to embed |

The releases without entries are bodyless Part and cross-heading roots (ACJA 49; Police Act 17 Parts and 5 cross-headings). Retrieval documents outnumber entries because long provisions are split into chunks. Draft releases `draft-7b4b9bc40a9c` and `draft-07e6dc81c9d5` are building. The production Constitution release `draft-c8d50d87fae9` is unchanged. Embedding, release validation, composition and publication have not been started.

## Embedding and benchmark scoring (23 October 2026)

### Benchmarks

The Constitution benchmark `constitution-source-edition-retrieval-2026-10-05-v1` was missing from the database; it had not been present since the 7 October recovery. It was restored from `docs/constitution-source-edition-benchmark.json` (50 queries, content hash `57bcfc5f…`). The user approved new Act benchmarks: `acja-2015-retrieval-v1` has 35 queries and `police-act-2020-retrieval-v1` has 32. All three were loaded with `backend/scripts/load_retrieval_benchmark.py`. Each release is now graded by the dataset for each instrument it contains. The embedding profile is unchanged, so the live Constitution vectors can still be reused when the combined release is built.

### Fixes found while embedding

- **Scoring.** Benchmark scoring now counts a hit on a provision inside the expected one, so s.8(2) counts for s.8. nDCG credits each expected provision once, at its best rank.
- **Retry payload.** Retrying a failed run dropped its task payload, so a retried embedding run failed with "Task does not identify a corpus release". Retry now carries over the latest payload that holds the stage's inputs.
- **Re-scored results.** The embeddings file had a fixed name per profile, so re-scoring was refused by the write-once store. The name now carries a content hash.

### Results

| Run | Documents | Recall@10 | nDCG@10 | State |
| --- | --- | --- | --- | --- |
| ACJA `7b4b9bc4` | 1,948 | 0.971 (34/35) | 0.916 | Indexed and index validated; ready to publish |
| Police Act `07e6dc81` | 938 | 0.9375 (30/32) | 0.922 | Failed at embedding: below the 0.95 gate |

### Real retrieval misses

These are not benchmark artefacts. Simulating the live hybrid ranking (vector, keyword at weight 0.15, topic hints and section titles) also misses them:

| Query | Expected | Vector rank | Keyword | Fused rank |
| --- | --- | --- | --- | --- |
| "Can the police arrest my brother because they cannot find me?" | ACJA s.7 | 78 | outside top 50 | not found |
| "Can the police arrest a family member in place of a suspect?" | Police s.36 | 13 | outside top 50 | 18 |
| "How is the Nigeria Police funded?" | Police s.26 | 11 | no match: `funded:*` misses "funding" and "fund" | 11 |

No topic hint or title match fires for any of them. The "arrest in place of a suspect" provisions are one-liners whose wording is far from everyday phrasing. The funding question shares only two of three title words with "Funding of the Police Force", below the 75% title threshold. No retrieval change has been made; proposals await the user's decision. The ACJA release has not been validated as a corpus release, composed or published.
