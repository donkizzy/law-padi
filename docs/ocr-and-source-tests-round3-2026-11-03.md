# OCR and source tests — Round3 — 2026-11-03

Evidence only. All new catalogue/evidence JSON retains `needs_review`. No legal source is marked verified, approved or ingestion-ready. Page numbers below are **one-based PDF page positions** unless explicitly labelled printed pages. Raw readings remain raw; reference-row association does not repair an OCR label or select the correct reading.

## Task A — Employees’ Compensation Act2010 title catalogue

Created `backend/app/legal/data/employees-compensation-act-2010-section-titles.json` and notified the user immediately after writing it, before completing the other tasks. Instrument slug: `employees-compensation-act-2010`. It contains `source`, `expected_section_count:74`, empty `chapters`,9 printed `parts`,74 `sections`, `source.review_status:needs_review`, and separate raw/transcription `notes`.

Source: retained `backend/storage/statute-review/source-tests/round2-eca-2010-iguides/Employee Compensation Act.pdf`, [iGuides reproduction](https://admin.theiguides.org/Media/Documents/Employee%20Compensation%20Act.pdf). SHA-256: `111cbe332b2d2793e564794492a2cb7851051a38bcccaab9c71e047f37230d6b`. Titles come only from its own arrangement, PDF3–6, with all four pages visually inspected. Printed singular title `EMPLOYEE’S COMPENSATION ACT,2010` is separately retained. No body-only headings were added.

The existing `catalogue_titles` function was loaded read-only from its local file without application startup. It returned74 section titles,9 part titles and0 chapter titles; section keys are exactly1–74. Catalogue SHA-256: `6464135d1f86aacb911cd9cdefb867e314ee70995014aac6a6cbbc15f413c320`.

Printed quirks retained: section3 `Exemptions` without a period; section44 printed `Sub-` / `Contractors.` joined with the printed hyphen retained and original lines in notes; section72 `Cap.470 LFN` retained rather than substituted with the body’s different reference; first part label is printed `PART1`, subsequent parts use Roman numerals. Arabic part-map keys are navigation identities; raw printed labels remain in notes. Case and punctuation are retained; line-wrap handling is documented. This is title/navigation evidence, without full-body or currency validation.

## Task B — Conditional catalogues

No additional catalogue was created. All three specified candidates were rated **no** in the retained Round1 report’s “Usable for weekend?” column. Those ratings, rather than a new assumption that readable text implies usability, control this task.

| Law / proposed slug | Round1 evidence and reason no catalogue was created |
|---|---|
| Criminal Code Act / `criminal-code-act` | PLAC C38:214 pages, readable text but mixed enabling Act, scheduled Code and subsidiary namespaces.572 arrangement/body candidate rows, with four unresolved raw-label discrepancies, including `l0A`/`10A`, `l2A`/`12A`, `l4A`/`14A`, arrangement `190` versus body `190A`. A single sequence would conceal unresolved provision identity and scope. |
| VAPP2015 / `violence-against-persons-prohibition-act-2015` | FIDA33-page scan: no own arrangement in that copy.48 body labels can be observed after OCR, but bill-style wording/blank commencement and source identity remain review issues despite assent-copy evidence. Body headings cannot substitute for the requested own arrangement. |
| FCCPA2018 / `federal-competition-and-consumer-protection-act-2018` | Official FCCPC99-page PDF: damaged existing text layer, strict97/168 arrangement and66/168 body labels. Follow-up OCR and image annotations do not resolve all wording/numbering issues; printed A23 is duplicated at PDF24–25. |

No changes were made to their retained originals or Round1 evidence. This does not decide that the laws themselves are unusable; it records the conditional source decision requested here.

## Task C — Evidence Act2011 label extraction evidence

Original retained PLAC PDF: `backend/storage/statute-review/source-tests/round2-evidence-2011-plac/Evidence-Act-2011.pdf`;75 pages; SHA-256 `58f71df65d79656baab0ee4c89516efc029421d26df6b33b8059fa30efaee09f`. Original unchanged. New outputs are under `backend/storage/statute-review/source-tests/round3-evidence-2011/`.

Offline Apple Vision was run in accurate mode at maximum1800×2500 and3600×5000 render sizes, plus a3600-size left-region pass, with language correction disabled and no expected-number vocabulary. The attempted narrow arrangement region returned no useful observations; that raw output is retained too. Native Poppler `pdftotext -bbox-layout` output is preserved separately. No host Tesseract was on PATH; none was installed or run, and no Docker/network OCR was used. Python readers used `-I` from `/private/tmp`; the local Swift Vision script was outside the evidence folders.

The detailed `section-label-evidence.json` keeps raw labels, surrounding text, engine/pass, page, bounding box, confidence where emitted, and the location/content basis for association. Raw full-pass files remain independent. Region boxes are transformed to page coordinates only in the comparison; original region-relative boxes remain in the raw regional file. Vision confidence describes its own observation, not accuracy or legal confidence.

**Coverage observation:** all259 arrangement rows have a label observation, including separate visual observations where machine extraction failed. Arrangement1 is an ambiguous `) / thin vertical stroke`, not a readable numeral silently changed to1.253 reference rows have body-heading label observations. The only labels not located at all are **body132,133,134,135,136,137**; arrangement unread/unlocated list is empty, subject to the explicit row1 ambiguity.

**Visible source gap:** PDF45 ends at the opening of131, which is itself truncated there; PDF46 begins138. This jump is visible in retained previews. No wording for132–137 was supplied, and the report does not infer why the retained copy has this gap or whether the missing text exists in another edition.

The following259-row table uses the requested section/reference index as a location aid. “Found” means an observation at the associated arrangement/heading location, not a decision that every alternative raw token is a correct section number. Conflicts such as `30.`/`36.`, `44.`/`46.`, and `[61.`/`16i.`/`I6l.` remain alternatives. Heading/opening content and page position are recorded as association evidence; no preferred reading or repaired OCR field is produced. Unassigned/cross-reference fragments remain in the JSON and are not used to fill gaps.

| Reference row | Arrangement label observation (PDF page; raw readings) | Body label observation (PDF page; raw readings) |
|---:|---|---|
| 1 | Found, p2: `) / thin vertical stroke` | Found, p10: `1.` |
| 2 | Found, p2: `2` / `o` | Found, p10: `2.` |
| 3 | Found, p2: `3` | Found, p10: `3.` |
| 4 | Found, p2: `4` | Found, p11: `4.` |
| 5 | Found, p2: `5` | Found, p11: `5.` |
| 6 | Found, p2: `6` | Found, p11: `6.` |
| 7 | Found, p2: `7` | Found, p11: `7.` / `7,` |
| 8 | Found, p2: `8` | Found, p11: `8.` |
| 9 | Found, p2: `9` | Found, p12: `9.` |
| 10 | Found, p2: `10` / `]0` | Found, p12: `10.` |
| 11 | Found, p2: `II` / `11` | Found, p12: `11.` |
| 12 | Found, p2: `12` | Found, p12: `12.` |
| 13 | Found, p2: `jJ` / `13` | Found, p12: `13.` |
| 14 | Found, p2: `14` | Found, p13: `14.` |
| 15 | Found, p2: `15` / `]5` | Found, p13: `15.` |
| 16 | Found, p2: `16` / `J` | Found, p13: `16.` |
| 17 | Found, p2: `17` | Found, p13: `17.` |
| 18 | Found, p2: `18` / `[8` | Found, p13: `18.` |
| 19 | Found, p2: `19` / `J` | Found, p14: `19.` |
| 20 | Found, p2: `20` | Found, p14: `20.` |
| 21 | Found, p2: `21` | Found, p14: `21.` |
| 22 | Found, p2: `22` | Found, p14: `22.` / `22,` |
| 23 | Found, p2: `23` | Found, p14: `23.` |
| 24 | Found, p2: `24` | Found, p14: `24.` / `4.` |
| 25 | Found, p2: `25` | Found, p15: `25.` |
| 26 | Found, p2: `26` | Found, p15: `26.` |
| 27 | Found, p3: `27` | Found, p15: `27.` / `2'7.` |
| 28 | Found, p3: `28` | Found, p15: `28.` |
| 29 | Found, p3: `29` | Found, p15: `29.` |
| 30 | Found, p3: `30` | Found, p16: `30.` |
| 31 | Found, p3: `31` / `3I` | Found, p16: `31.` / `31Ia` |
| 32 | Found, p3: `32` | Found, p16: `32.` |
| 33 | Found, p3: `33` | Found, p16: `33.` / `33,` |
| 34 | Found, p3: `34` | Found, p17: `34.(1)` / `34.` |
| 35 | Found, p3: `35` | Found, p17: `35.` / `35,` |
| 36 | Found, p3: `36` | Found, p17: `36.` / `30.` |
| 37 | Found, p3: `37` | Found, p18: `37.` |
| 38 | Found, p3: `38` | Found, p18: `38.` |
| 39 | Found, p3: `39` | Found, p18: `39.` / `39).` |
| 40 | Found, p3: `40` | Found, p18: `40).` / `40.` |
| 41 | Found, p3: `41` | Found, p19: `41.CA` / `41.` |
| 42 | Found, p3: `42` | Found, p19: `42.` |
| 43 | Found, p3: `43` | Found, p19: `43.` |
| 44 | Found, p3: `44` | Found, p19: `44.` |
| 45 | Found, p3: `45` | Found, p20: `45.` / `45.(1)` |
| 46 | Found, p3: `46` | Found, p20: `44.` / `44.(1h` / `4().` / `46.` |
| 47 | Found, p3: `47` | Found, p21: `47.` |
| 48 | Found, p3: `48` | Found, p21: `48.` |
| 49 | Found, p3: `49` | Found, p21: `49.` |
| 50 | Found, p3: `50` | Found, p21: `50.` |
| 51 | Found, p3: `51` | Found, p21: `51.` |
| 52 | Found, p3: `52` | Found, p21: `52.` |
| 53 | Found, p3: `53` | Found, p21: `53.` |
| 54 | Found, p3: `54` / `S4` | Found, p21: `54.` |
| 55 | Found, p3: `55` | Found, p22: `55.` |
| 56 | Found, p3: `56` | Found, p22: `56.` |
| 57 | Found, p4: `57` | Found, p23: `57.` |
| 58 | Found, p4: `58` | Found, p23: `58.` / `5~.` |
| 59 | Found, p4: `59` | Found, p23: `59.` |
| 60 | Found, p4: `60` | Found, p23: `60.` |
| 61 | Found, p4: `61` | Found, p23: `61.` |
| 62 | Found, p4: `62` | Found, p24: `62.` |
| 63 | Found, p4: `63` | Found, p24: `3.‹1)` / `63.` |
| 64 | Found, p4: `64` | Found, p24: `G4A` / `64.` / `64A` |
| 65 | Found, p4: `65` | Found, p24: `65.` / `6é.` |
| 66 | Found, p4: `66` | Found, p24: `66.` |
| 67 | Found, p4: `67` | Found, p24: `67.` |
| 68 | Found, p4: `68` | Found, p25: `68.` |
| 69 | Found, p4: `69` | Found, p25: `69.` |
| 70 | Found, p4: `70` | Found, p25: `70.` |
| 71 | Found, p4: `7]` / `71` | Found, p25: `71.` |
| 72 | Found, p4: `72` | Found, p25: `72.` |
| 73 | Found, p4: `73` | Found, p25: `73.` |
| 74 | Found, p4: `74` | Found, p25: `74.` |
| 75 | Found, p4: `75` / `7S` | Found, p26: `75.` |
| 76 | Found, p4: `76` | Found, p26: `76.` |
| 77 | Found, p4: `77` | Found, p26: `77.` |
| 78 | Found, p4: `78` | Found, p26: `78.` |
| 79 | Found, p4: `79` | Found, p26: `79.` / `7%.` |
| 80 | Found, p4: `80` | Found, p26: `80.` |
| 81 | Found, p4: `81` | Found, p26: `81.` |
| 82 | Found, p4: `82` | Found, p27: `82.` |
| 83 | Found, p4: `83` | Found, p27: `83.` |
| 84 | Found, p4: `84` | Found, p28: `84.` / `84.11)` |
| 85 | Found, p4: `85` | Found, p30: `85.` |
| 86 | Found, p4: `86` | Found, p30: `R6.` / `86.` |
| 87 | Found, p4: `87` | Found, p30: `87.` |
| 88 | Found, p4: `88` | Found, p31: `88.` |
| 89 | Found, p4: `89` | Found, p31: `89.` / `N9.` |
| 90 | Found, p4: `90` | Found, p31: `90.` / `70.` |
| 91 | Found, p4: `21` / `91` | Found, p32: `91.` |
| 92 | Found, p4: `92` | Found, p33: `92.` / `72.` |
| 93 | Found, p5: `93` | Found, p33: `93.` / `93. I` |
| 94 | Found, p5: `94` | Found, p33: `94.` |
| 95 | Found, p5: `95` / `9S` | Found, p34: `95.` |
| 96 | Found, p5: `96` | Found, p34: `96.` |
| 97 | Found, p5: `97` | Found, p34: `97.` |
| 98 | Found, p5: `98` | Found, p34: `98.` |
| 99 | Found, p5: `99` | Found, p34: `99. Il` / `99.` |
| 100 | Found, p5: `100` | Found, p34: `100.` / `100,` |
| 101 | Found, p5: `101` | Found, p34: `101.` |
| 102 | Found, p5: `102` | Found, p35: `102.` |
| 103 | Found, p5: `103` | Found, p35: `103.` |
| 104 | Found, p5: `104` | Found, p35: `104.` |
| 105 | Found, p5: `105` | Found, p36: `105.` |
| 106 | Found, p5: `106` | Found, p36: `106.` |
| 107 | Found, p5: `107` | Found, p37: `107.` |
| 108 | Found, p5: `108` | Found, p37: `108.` |
| 109 | Found, p5: `109` | Found, p37: `109.` / `109,` |
| 110 | Found, p5: `110` / `J` | Found, p37: `110.` |
| 111 | Found, p5: `111` / `J` | Found, p38: `111.` / `Ill.` / `I11.` |
| 112 | Found, p5: `112` / `I` | Found, p38: `112.` / `1` |
| 113 | Found, p5: `113` | Found, p38: `113.` |
| 114 | Found, p5: `114` / `I` | Found, p38: `114.` |
| 115 | Found, p5: `115` | Found, p38: `115.` |
| 116 | Found, p5: `116` / `J` | Found, p38: `116.` |
| 117 | Found, p5: `117` / `]` | Found, p39: `117.` / `117,` |
| 118 | Found, p5: `118` / `1] 8` | Found, p39: `118.` / `l` / `1l5.` |
| 119 | Found, p5: `119` / `I` | Found, p39: `119.` / `119,` |
| 120 | Found, p5: `120` | Found, p40: `120.` / `120,` |
| 121 | Found, p5: `121` | Found, p40: `121.` |
| 122 | Found, p5: `122` | Found, p40: `122.` |
| 123 | Found, p5: `123` | Found, p42: `123.` |
| 124 | Found, p5: `124` / `J` | Found, p42: `124.` / `1e2` |
| 125 | Found, p5: `125` | Found, p42: `125.` |
| 126 | Found, p5: `126` | Found, p42: `126.` |
| 127 | Found, p5: `127` | Found, p43: `127.` / `127` / `]27.` |
| 128 | Found, p6: `128` | Found, p43: `128.` |
| 129 | Found, p6: `129` | Found, p44: `12<).` / `12%.` / `124.` / `129.` |
| 130 | Found, p6: `130` | Found, p45: `130.` |
| 131 | Found, p6: `131` | Found, p45: `131.` |
| 132 | Found, p6: `132` / `]32` | **Not located** |
| 133 | Found, p6: `133` | **Not located** |
| 134 | Found, p6: `134` / `]34` | **Not located** |
| 135 | Found, p6: `135` | **Not located** |
| 136 | Found, p6: `136` | **Not located** |
| 137 | Found, p6: `137` | **Not located** |
| 138 | Found, p6: `138` / `]38` | Found, p46: `138.` / `13X.` |
| 139 | Found, p6: `]39` / `139` | Found, p46: `13%` / `139.` / `13Y.` |
| 140 | Found, p6: `140` / `]40` | Found, p46: `140.` |
| 141 | Found, p6: `141` / `14]` / `]` | Found, p46: `141.` |
| 142 | Found, p6: `]42` / `142` | Found, p46: `142.` |
| 143 | Found, p6: `143` | Found, p47: `143.` |
| 144 | Found, p6: `144` / `]44` | Found, p47: `144.` |
| 145 | Found, p6: `]45` / `145` | Found, p47: `145.` / `]` |
| 146 | Found, p6: `146` | Found, p47: `146.(1)` / `146.` |
| 147 | Found, p6: `i-17` / `147` | Found, p47: `147.` |
| 148 | Found, p6: `148` | Found, p48: `148.` |
| 149 | Found, p6: `149` | Found, p48: `14%.` / `149.` |
| 150 | Found, p6: `]50` / `150` | Found, p48: `150.` |
| 151 | Found, p6: `]51` / `151` / `15)` | Found, p48: `151.` / `J` |
| 152 | Found, p6: `152` | Found, p48: `152.` / `J` |
| 153 | Found, p6: `]53` / `153` | Found, p49: `153.` / `15J.` |
| 154 | Found, p6: `154` | Found, p49: `154.` |
| 155 | Found, p6: `155` | Found, p49: `155.` |
| 156 | Found, p6: `156` | Found, p49: `156.` |
| 157 | Found, p6: `157` | Found, p49: `157.` |
| 158 | Found, p6: `158` | Found, p49: `158.` |
| 159 | Found, p7: `159` | Found, p49: `159` / `159.` / `15%` |
| 160 | Found, p7: `160` | Found, p50: `160.` |
| 161 | Found, p7: `161` | Found, p50: `16i.` / `I6l.` / `[61.` / `16l.` |
| 162 | Found, p7: `162` | Found, p50: `162.` |
| 163 | Found, p7: `163` | Found, p50: `163.` / `163,` |
| 164 | Found, p7: `164` | Found, p51: `164.` |
| 165 | Found, p7: `165` | Found, p51: `165.` |
| 166 | Found, p7: `166` | Found, p51: `166.` |
| 167 | Found, p7: `167` | Found, p51: `167.` |
| 168 | Found, p7: `168` | Found, p52: `168.` |
| 169 | Found, p7: `169` | Found, p52: `169.` |
| 170 | Found, p7: `170` | Found, p52: `170.` |
| 171 | Found, p7: `171` | Found, p52: `171.` |
| 172 | Found, p7: `172` | Found, p52: `172.` |
| 173 | Found, p7: `173` / `J73` | Found, p53: `173.` |
| 174 | Found, p7: `174` | Found, p53: `174.` |
| 175 | Found, p7: `175` | Found, p53: `175.` / `]` |
| 176 | Found, p7: `176` | Found, p53: `176.` |
| 177 | Found, p7: `177` | Found, p53: `177.` / `177.U` / `]` |
| 178 | Found, p7: `178` | Found, p54: `178.` |
| 179 | Found, p7: `179` | Found, p54: `179.` |
| 180 | Found, p7: `180` | Found, p54: `180.` |
| 181 | Found, p7: `181` | Found, p55: `181.` |
| 182 | Found, p7: `182` | Found, p55: `182.` / `182,` |
| 183 | Found, p7: `183` | Found, p55: `183.` |
| 184 | Found, p7: `184` | Found, p56: `184.` |
| 185 | Found, p7: `185` | Found, p56: `185.` |
| 186 | Found, p7: `186` | Found, p56: `186.` |
| 187 | Found, p7: `187` | Found, p56: `187.` |
| 188 | Found, p7: `188` | Found, p57: `188.` |
| 189 | Found, p7: `189` | Found, p57: `189.` |
| 190 | Found, p7: `190` | Found, p57: `190.` / `190,` |
| 191 | Found, p7: `191` | Found, p57: `191.` |
| 192 | Found, p7: `192` | Found, p57: `192.` |
| 193 | Found, p7: `193` | Found, p58: `193.` |
| 194 | Found, p7: `194` | Found, p58: `194.` |
| 195 | Found, p8: `195` | Found, p58: `95.` / `3.` / `195.` |
| 196 | Found, p8: `196` | Found, p58: `196.` / `196` / `J` |
| 197 | Found, p8: `197` | Found, p58: `197.` / `19%.` |
| 198 | Found, p8: `198` | Found, p58: `198.` |
| 199 | Found, p8: `199` | Found, p59: `199.` |
| 200 | Found, p8: `200` | Found, p59: `200.` |
| 201 | Found, p8: `201` / `20J` | Found, p59: `201.` |
| 202 | Found, p8: `202` | Found, p59: `202.` |
| 203 | Found, p8: `203` | Found, p59: `203.` |
| 204 | Found, p8: `204` | Found, p59: `204.` |
| 205 | Found, p8: `205` | Found, p59: `205.` |
| 206 | Found, p8: `206` | Found, p60: `20().` / `20%.` / `206.` |
| 207 | Found, p8: `207` | Found, p60: `207.` |
| 208 | Found, p8: `208` | Found, p60: `208.` |
| 209 | Found, p8: `209` | Found, p60: `209.` |
| 210 | Found, p8: `210` / `2JO` | Found, p60: `210.` |
| 211 | Found, p8: `211` / `2 J` | Found, p61: `211.` |
| 212 | Found, p8: `212` / `2J2` | Found, p61: `212.` |
| 213 | Found, p8: `213` | Found, p61: `213.` |
| 214 | Found, p8: `214` | Found, p61: `214.` / `11'-l.` |
| 215 | Found, p8: `215` | Found, p61: `2J 5.` / `215.` |
| 216 | Found, p8: `216` / `::16` | Found, p62: `216.` |
| 217 | Found, p8: `217` | Found, p62: `217.` |
| 218 | Found, p8: `218` | Found, p62: `218.` |
| 219 | Found, p8: `219` | Found, p62: `219.` / `219` |
| 220 | Found, p8: `220` | Found, p62: `220.` |
| 221 | Found, p8: `221` | Found, p62: `221.` |
| 222 | Found, p8: `222` | Found, p62: `2.22.` / `222.` |
| 223 | Found, p8: `223` | Found, p62: `223.` |
| 224 | Found, p8: `224` | Found, p63: `224.` |
| 225 | Found, p8: `225` | Found, p63: `225.` |
| 226 | Found, p8: `226` | Found, p63: `226.` / `220.` |
| 227 | Found, p8: `227` | Found, p63: `227.` |
| 228 | Found, p8: `228` | Found, p64: `228.` |
| 229 | Found, p8: `229` | Found, p64: `229.` |
| 230 | Found, p8: `230` | Found, p64: `230.` |
| 231 | Found, p9: `231` | Found, p64: `231.` / `2.31.` |
| 232 | Found, p9: `232` | Found, p64: `232.` |
| 233 | Found, p9: `233` | Found, p64: `233.` |
| 234 | Found, p9: `234` | Found, p65: `234.` |
| 235 | Found, p9: `235` | Found, p65: `235.` |
| 236 | Found, p9: `236` | Found, p65: `236.` |
| 237 | Found, p9: `237` | Found, p65: `237.` / `237,` |
| 238 | Found, p9: `238` | Found, p65: `238.` |
| 239 | Found, p9: `239` | Found, p65: `239.` |
| 240 | Found, p9: `240` | Found, p66: `240.` / `241).` |
| 241 | Found, p9: `241` | Found, p66: `241.` |
| 242 | Found, p9: `242` | Found, p66: `242.` |
| 243 | Found, p9: `243` | Found, p66: `243.` |
| 244 | Found, p9: `244` | Found, p66: `244.` |
| 245 | Found, p9: `245` | Found, p66: `245,` / `245.` |
| 246 | Found, p9: `246` | Found, p67: `246.` |
| 247 | Found, p9: `247` | Found, p67: `247.` |
| 248 | Found, p9: `248` | Found, p67: `248.` / `2~8.` |
| 249 | Found, p9: `249` | Found, p68: `24%CI)A` / `24%(T)A` / `241).` / `249.` |
| 250 | Found, p9: `250` | Found, p68: `250.(1)` / `250.` / `250.(L)A` / `250,` |
| 251 | Found, p9: `251` | Found, p69: `251.` / `251,` |
| 252 | Found, p9: `252` | Found, p69: `252.` |
| 253 | Found, p9: `253` | Found, p69: `253.` |
| 254 | Found, p9: `254` | Found, p70: `254.` |
| 255 | Found, p9: `255` | Found, p70: `255.` / `55.` |
| 256 | Found, p9: `256` | Found, p70: `256.` |
| 257 | Found, p9: `257` | Found, p71: `257.` / `25%.` |
| 258 | Found, p9: `258` | Found, p71: `258.` |
| 259 | Found, p9: `259` | Found, p73: `259.` / `259,` |

## Task D — Cybercrimes2024 amendment map

Retained ONSA booklet source SHA-256: `71aa33defe3507417db01270e6e94afe6c8f982c1c37567f43b51bea71ebd65f`. Retained Round1 OCR SHA-256: `e1503b7f7e1ded5751a82c00d077beacfd9155db85d86cf5b28042bbfd0202be`. The booklet is an ONSA compilation containing principal and amending material, not an issuing gazette. Neither the original nor the old OCR was changed. New map and previews are in `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/`.

The principal Act’s arrangement occupies **PDF5 only**, printed gazette page **A617**, printed booklet page **4**. It visibly lists1–24. The photograph is legible enough at enlargement to inspect that partial list, but the number column is poorly captured in the retained OCR (`1.`, `2.`, `wo`, then lost numbers). PDF6 starts principal-Act body text; no continuation for25–59 was located in the retained booklet. Thus the retained principal arrangement is partial, not a complete legible59-section arrangement.

The11 requested numbers are principal-Act targets; the corresponding amending clauses are2–12. Clause1 is introductory and13 is citation. Associations below use the main operative reference, with raw marginal text retained even where it conflicts. No amendments have been applied and no consolidated text was produced.

| Amending clause | Principal-Act target | PDF page(s) | Printed booklet page(s) |
|---:|---|---|---|
| 2 | 17 | 52 | 51 |
| 3 | 21 | 52 | 51 |
| 4 | 22 | 52 | 51 |
| 5 | 24 | 52 | 51 |
| 6 | 27(2) | 53 | 52 |
| 7 | 30 | 53 | 52 |
| 8 | 37(1)(a) | 53 | 52 |
| 9 | 38 | 53 | 52 |
| 10 | 41(1) | 53, 54 | 52, 53 |
| 11 | 44 | 54 | 53 |
| 12 | 48 | 54 | 53 |

### Exact retained raw OCR clause spans

These are unchanged substrings of the retained OCR, including marginal-note interference, punctuation, apparent misspellings and page-footer fragments. The JSON records page-local character offsets. Exact substring equality against the old OCR was checked. Clause7 retains `7,`; clause6’s main `27(2)` and marginal `witen37` both remain; clause10(e) ends `thereby protecting the` before(f), with no supplied words; clause11 retains `Section of44` and its raw subsection reference. Text here is evidence of the OCR output, not an endorsed statutory quotation.

#### Clause2 — principal target17

PDF52, characters527–831 (end exclusive):

```text
2. Section 17 of the Principal Act is amended — Amendment of
section 17
(a) in subsection (2) by substituting for the word “geniuses” the word
“genuineness”; and
(b) in subsection (4) by inserting after the word “signature”, the words,
“except where they are legally verified in “Certified True Copies”.
```

#### Clause3 — principal target21

PDF52, characters831–1224 (end exclusive):

```text
3. Section 21 (1) of the Principal Act is amended — Amendment of
section 21
(a) in subsection (1) by inserting after the words “Coordination Center” in line
6, the words, “through their respective sectoral CERTs or sectoral Security
Operations Centres (SOC)”; and
(b) in subsection (3) by substituting for the expression “7 days of its
occurance”, the expression, “72 hours of its detection”.
```

#### Clause4 — principal target22

PDF52, characters1224–1395 (end exclusive):

```text
4. Section 22 (1) of the Principal Act is amended by inserting after the words “any Financial Amendment of
Institution”, the words “public or private organisation”. MS ie
```

#### Clause5 — principal target24

PDF52, characters1395–1719 (end exclusive):

```text
5. Section 24 (1) of the Principal Act is amended by substituting for paragraphs (a) and (b), Amendment of
new paragraphs “(a)” and “(b)” — section 24
“(a) is pornographic; or
(b) he knows to be false, for the purpose of causing a breakdown of law
and order, posing a threat to life, or causing such message to be sent,”.
5]
```

#### Clause6 — principal target27(2)

PDF53, characters0–195 (end exclusive):

```text
6. Section 27 (2) of the Principal Act is amended by substituting for the words “a financial Amendment of
institution” in lines | and 2, the words, “any public or private organisation”: witen 37
```

#### Clause7 — principal target30

PDF53, characters195–516 (end exclusive):

```text
7, Section 30 of the Principal Act is amended — Amendment of
section 30
(a) in subsection (1) by inserting after the word “terminals”, the words “or
any other payment technology means”; and
(b) in subsection (2) by substituting for the words “or point of sales device”,
the words “or any other payment technology means”.
```

#### Clause8 — principal target37(1)(a)

PDF53, characters516–735 (end exclusive):

```text
8. Section 37 (1) (a) of the Principal Act is amended by inserting after the word “present”. ae of
the words, “National Identification Number issued by the National Identity Management "°°"
Commission and other valid”.
```

#### Clause9 — principal target38

PDF53, characters735–1187 (end exclusive):

```text
9. Section 38 of the Principal Act is amended by substituting for subsection (1) a new Co of
subsection “(1)” — section
“(1) A service provider shall keep and protect specific traffic data and
subscriber information in accordance with the provision of the Nigeria
Data Protection Act and as may be prescribed by the relevant authority for
the time being, responsible for the regulation of communication services
in Nigeria, for a period of two years.”
```

#### Clause10 — principal target41(1)

PDF53, characters1187–1807 (end exclusive):

```text
10. Section 41 (1) of the Principal Act is amended by substituting for paragraphs (d) — (h) oe of
new paragraphs “(d)"-“(j)” — si
“(d) ensure the establishment of sectoral Computer Emergency Response
Teams (CERT) and sectoral Security Operation Centres (SOC) that
shall feed into the national CERT;
(e) ensure that all public and private organisations integrate and route their
internet and data traffic to the sectoral SOCs thereby protecting the
(f) establish and maintain a National Computer Forensic Laboratory and
coordinate utilisation of the facility by all law enforcement, security
and intelligence agencies:
rr
```

PDF54, characters0–613 (end exclusive):

```text
(g) build capacity for the effective discharge of the functions of all relevant
security, intelligence, law enforcement and military services under this
Act or any other law on cybercrime in Nigeria;
(h) establish appropriate platforms for public private partnership (PPP).
(i) coordinate Nigeria's involvement in international cyber security
cooperation to ensure the integration of Nigeria into the global
frameworks on cyber security; and F ~~
(j) do such other acts or things that are necessary for the effective
performance of the functions of the relevant security and enforcement
agencies under this Act.”
```

#### Clause11 — principal target44

PDF54, characters613–1601 (end exclusive):

```text
11. Section of 44 of the Principal Act is amended —
(a) in subsection (1) by substituting for paragraph (a) a new paragraph “(a)”
“(a) a levy of 0.5% (0.005) equivalent to a half percent of all
electronic transactions value by the business specified in the
Second Schedule to this Act”; and
(b) by substituting for subsection (6), new subsections “(6)” — “(8)” —
(6) The Office of the National Security Adviser shall administer, keep
proper records of the accounts and shall ensure compliance
monitoring mechanism.
(7) The account of the Fund shall be audited in accordance with
guidelines provided by the Auditor General for the Federation.
(8) A business specified in the Second Schedule to this Act that fails
to remit the levy under section 44 (2)(a) of this Act commits an
offence and is liable on conviction to a fine of not less than 2%
of the annual tumover of the defaulting business and failure to
comply shall lead to closure or withdrawal of the business
operational licence.
```

#### Clause12 — principal target48

PDF54, characters1601–1725 (end exclusive):

```text
12. Section 48 of the Principal Act is amended by deleting subsection “(4)”
Amendment of
section 44
Amendment of
section 48
```

## Task E — Signed minimum-wage text

Two candidate downloads were separately authorized in this round, each with filename, source and an unknown-size25MB cap disclosed. No paid source was purchased or access challenge bypassed. Outcomes differ: the2019 ILO copy contains visible scanned assent signatures; the2024 Lexark copy is editorially retypeset with blank signature lines. An original signed/gazetted2024 copy remains **not obtained**.

### Downloaded candidates

| Instrument | Exact URL / publisher / status | Bytes; pages; text layer | Assent evidence and limit |
|---|---|---|---|
|2019 Act | [ILO attachment](https://natlex.ilo.org/dyn/natlex2/natlex2/files/download/111617/NGA111617%20.pdf), via [NATLEX record111617](https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=111617). ILO is an intergovernmental republisher of a Nigerian National Assembly copy, not Nigeria’s issuing authority. |346,636 bytes;14 pages; no text layer,0 native words on every page. SHA-256 `6d624addf4e94c994c2caf3fa37ed82261fb2c13d9858163a4dcdaac3a886f23`. | PDF13 contains clerk certification/signature image; PDF14 visibly contains `I ASSENT`, signature image and Muhammadu Buhari’s printed name. Handwritten day appears18; printed `March2019` is crossed out with handwritten `April`. Both raw date observations retained. This meets the search for an assent-bearing copy, without authenticating the signature or every statutory word. |
|2024 Amendment | [Lexark record](https://www.lexark.org/d/national-minimum-wage-amendment-act-2024); [canonical PDF object](https://lexark-documents.s3.amazonaws.com/2026/Sep/Fr/a8cb00b1-17af-4c05-8231-b4a043784808.pdf), retrieved using its publicly supplied temporary link. Secondary host attributing author to National Assembly; not direct National Assembly provenance. |65,528 bytes;6 pages; text layer yes; words/page `[43,28,154,53,208,138]`. SHA-256 `9414ef03137aba8dfa50e2553f0daaf74f8336eba7463871279aa015b3243b97`. | PDF5 has typed assent wording/president name/date29July2024 but blank signature lines. PDF6 editor’s note discloses corrections to heading/quotation marks. PDF3 still says `A Bill`, commencement bracket blank. No signature image/gazette cover observed. Rejected for the specific original signed/gazetted-copy requirement; not silently promoted from typed assent wording. |

The2019 file is retained as `NGA111617 .pdf` with its literal space. Command-line attachment routes returned403, but the approved canonical route worked in the browser. **Isolation deviation:** the browser’s default download mechanism first saved the exact newly downloaded file in Downloads. It was moved unchanged into a newly created empty evidence folder before any PDF processing. This did not satisfy the requested destination rule at the initial save; the deviation is recorded in `download.json`, not presented as compliance. No code from that PDF or evidence folder was executed. The Lexark download went directly into its own new empty folder. Original bytes were retained in each case.

### Other routes investigated; no additional download

| Candidate / route | Publisher and official/secondary classification | Outcome / assent observation |
|---|---|---|
| [2019 Gazette No62,23April2019](https://archive.gazettes.africa/archive/ng/2019/ng-government-gazette-supplement-dated-2019-04-23-no-62.pdf) | Federal Government Printer gazette reproduced by Gazettes.Africa; official-origin gazette, secondary archival host. | Round2 attempted download returned403; no new PDF download this round. Issuing heading/index is a lead, not a newly inspected assent page. No corresponding original2024 gazette PDF was located in the search. |
| [National Assembly public catalogue](https://nass.gov.ng/documents/magazine_track/) | National Assembly, official. | Returned catalogue did not yield2019/2024 wage Act attachments. Search results included bill/passage tracking, not an enrolled signed2024 PDF; not substituted for assent evidence. |
| [Ministry’s law listing](https://labour.gov.ng/about-the-ministry/); [downloads route](https://labour.gov.ng/downloads/) | Federal Ministry of Labour and Employment, official agency. | Listing names the2019 Act; no accessible signed Act PDF link obtained. Unavailable/error responses do not establish absence of a ministry copy. |
| [2019 ministry announcement](https://labour.gov.ng/2019/06/18/ilc-nigera-calls-for-upgrading-of-ilo-country-office-abuja/) | Federal Ministry of Labour and Employment, official agency. | Refers to assent; announcement is not a signed statutory text. |
| [LawNigeria2019 article](https://lawnigeria.com/2025/03/27/national-minimum-wage-act-2019/) and [product](https://lawnigeria.com/product/national-minimum-wage-act-2019/) | LawNigeria, secondary commercial legal publisher. | Public text/listing and paid PDF offering. No public assent-signature image inspected; no purchase/download. |
| [LawNigeria2024 listing](https://lawnigeria.com/2025/10/06/national-minimum-wage-amendment-act-2024/) | LawNigeria, secondary commercial legal publisher. | Public listing/typed date is not signature evidence. Paid PDF not purchased; its actual assent page remains uninspected. |
| [State House4August2024 broadcast](https://statehouse.gov.ng/president-tinubus-broadcast-on-the-nationwide-protest/) | Presidency, official primary statement. | Confirms signing in the preceding week; not the signed Act or gazette. |
| [Lexark2019 record](https://www.lexark.org/d/national-minimum-wage-act-2019) | Lexark, secondary. | HTML lead only; no separate attachment download because the ILO assent-bearing copy was obtained. |

The2025 dates on LawNigeria’s pages are web publication/listing dates, not evidence of a new enactment. Search results for other countries’ wage gazettes were excluded. No conclusion about current wage entitlements, commencement disputes or legal effect is made here.

## Scope, checks and matters not established

No database, containers, `docker compose`, migrations, `.env`, commits or branch changes were used. No pre-existing repository file was edited. Only the one expressly requested new Employees’ Compensation catalogue was created under `backend/app/`; no other application file was changed. NDPA, Child’s Rights, Land Use and Labour source/catalogue material was not processed or modified in this round. Round1 report ratings were read solely to decide Task B.

Read-only checks: the existing catalogue reader loaded74/9/0 section/part/chapter titles; all11 amendment clauses’ retained strings matched their source OCR offsets; the Evidence comparison has259 reference rows and preserves its alternatives; the818-file baseline of retained relevant source/evidence files, reader and prior reports remained hash-identical. This baseline covers this lane’s relevant allowed files, not the entire shared checkout. Other agents’ unrelated work was not reconciled or reverted.

Not established: authenticity or handwriting/signature validity; issuing-authority endorsement; legal currency; complete body wording; completeness of the damaged Evidence PDF; a complete principal Cybercrimes arrangement; a corrected reading for conflicting OCR; an original signed/gazetted2024 wage amendment; ingestion suitability or production readiness. The2019 wage PDF has not received a full section/wording audit here. No provision was reconstructed to fit a sequence. A source-location association in the Evidence table is an explicit interpretation of location/context, not a choice between competing raw readings.

## Every repository file created in this round

Paths below are relative to the repository root `/Users/amosgodwin/WebstormProjects/law-padi`. The inventory JSON records byte counts and SHA-256 for every listed file except its own self-hash. Temporary processing scripts/previews under `/private/tmp` are scratch work, outside the repository deliverable; retained raw extraction evidence and relevant previews are listed here.

- `backend/app/legal/data/employees-compensation-act-2010-section-titles.json`
- `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/amendment-map.json`
- `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/page-05.png`
- `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/page-06.png`
- `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/page-52.png`
- `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/page-53.png`
- `backend/storage/statute-review/cybercrimes-2015-2024/round3-amendment-map/page-54.png`
- `backend/storage/statute-review/source-tests/round3-created-files.json`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-02.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-03.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-04.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-05.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-06.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-07.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-08.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-09.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-45.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-46.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-50.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/page-63.png`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/pdftotext-bbox-raw.xhtml`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/section-label-evidence.json`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/vision-ocr-raw.json`
- `backend/storage/statute-review/source-tests/round3-evidence-2011/vision-regions-raw.json`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/NGA111617 .pdf`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/assent-observations.json`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/download.json`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/extracted-text.txt`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/inspection.json`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/page-01.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/page-02.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/page-03.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/page-13.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/page-14.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2019-ilo-browser/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/a8cb00b1-17af-4c05-8231-b4a043784808.pdf`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/download.json`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/extracted-text.txt`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/inspection.json`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/page-01.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/page-02.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/page-03.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/page-04.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/page-05.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/page-06.png`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round3-minimum-wage-2024-lexark/source-observations.json`
- `docs/ocr-and-source-tests-round3-2026-11-03.md`
