# OCR and source tests — Round 4 — 2026-11-03

Evidence only; all new catalogue and review records remain `needs_review`. No source is marked verified, approved or ingestion-ready. PDF page numbers are one-based file positions; printed page labels are identified separately. Raw text and numeric readings remain unchanged. Reference rows and location/content associations are comparison aids, not repaired OCR labels or a choice of the legally correct reading.

## Task A — Criminal Code scope map

Retained source: [PLAC C38 PDF](https://lawsofnigeria.placng.org/laws/C38.pdf), secondary republication, 214 pages. SHA-256: `42be35360b26ac038176d2a71d1999d3257671ef3017470b0a9a420188d385ae`. Originals and prior evidence remain unchanged. New scope/range records and boundary previews are in `backend/storage/statute-review/source-tests/round4-criminal-code/`.

### Instrument boundaries

| Material | PDF pages | Boundary / scope |
|---|---|---|
| Cap. C38 enabling Act arrangement | 1, before `SCHEDULE` | Eight headings: 1, 1A, 2–7. |
| Scheduled Criminal Code arrangement | 1 after `SCHEDULE` through 31 | Section endpoint 521, with lettered insertions and printed repealed/deleted entries. 572 heading positions; 571 distinct raw labels because `190` is repeated. This is the source’s own printed arrangement, not a generated contents list. No reliable independent printed-page counter was observed in the inspected reflowed arrangement pages; use PDF positions. |
| Cap. C38 enabling Act body | 32–34, before `SCHEDULE` on 34 | Sections 1, 1A, 2–7. Opening paragraph on PDF 34 continues section 7; the Code does not begin at the page top. |
| Code proper — Schedule under section 2(1) | 34 after `SCHEDULE` through 207 before `Federal sections` | 572 body heading positions, range 1–521 with lettered insertions. These counts include printed repeal/deletion entries and do not establish full subsection wording. |
| Federal-section classification table | 207–208 | `Federal sections` / `See Preface`, described as the Committee’s opinion. Not extra Code provisions or an independently decided federal/state applicability rule. |
| Subsidiary-legislation index | Bottom of 208 | Separate instrument list; not part of the Code’s numbered sequence. |
| Unlawful Societies Order | 209–210 | Ends before Race Club heading on shared PDF 210; embedded historical order references retained. |
| Race Club Lotteries and Sweepstakes Notices | 210 | Separate notice under section 240D(1). |
| Prohibited Publications Orders and their schedules | 210–214 | Several separately numbered orders, including schedules at 211–213. No merging of their restarted numbering into the Code. |

Boundary previews were inspected at the Schedule transition and subsidiary index; raw text preserves the rest of each boundary. Inclusive ranges below may share a page; they are not instructions to drop or split pages without inspecting their contents.

The subsidiary group contains these separate instruments (raw text in the extraction remains authoritative for punctuation): Pan-African Trade Union Conference Order, PDF210; Film “The Road to Peace” Order, PDF210–211; Song of the Rivers/Criminal Code (Prohibited Publication) Order, PDF211; scheduled-publications Criminal Code (Prohibited Importations) Order, PDF211–213; and Peking Review Criminal Code (Prohibited Importations) Order, PDF213–214. The latter prints prohibition as1 and short title as2; that order was not “corrected”. Details are in `subsidiary-instrument-ranges.json`.

### Part groups

Only Parts 1 and 2 were found as standalone `PART` markers in the native body stream. Parts 3–8 below are **arrangement groupings associated with their first body section**, not invented printed body headings. All eight are printed in the arrangement.

| Printed arrangement Part | Arrangement PDF range | Associated body PDF range | Standalone body PART marker found in native layer? |
|---:|---|---|---|
|1|1–3|34–50|Yes|
|2|3–6|50–70|Yes|
|3|6–12|70–103|Not found|
|4|12–16|103–124|Not found|
|5|16–22|124–154|Not found|
|6|22–30|154–197|Not found|
|7|30|197–203|Not found|
|8|30–31|203–207|Not found|

### Chapter ranges

The arrangement prints 57 chapter divisions: 1–55 plus 6A and 21A. Chapter 53 has a misplaced marker on PDF 202 inside ongoing text, then repeats with its substantive heading on PDF 203. Both observations remain. Titles crossing page breaks are not replaced with body-only wording. Chapter 6’s title is not present after its arrangement marker in the extracted stream; no title was supplied from the body.

| Raw Chapter label | Arrangement PDF range | Body PDF range, including shared boundary | Body marker PDF page(s) |
|---|---|---|---|
|1|1–2|34–41|34|
|2|2|41–42|41|
|3|2|42–45|42|
|4|2–3|45–46|45|
|5|3|46–50|46|
|6|3–4|50–54|50|
|6A|4|54–55|54|
|7|4–5|55–61|55|
|8|5|61|61|
|9|5|61–64|61|
|10|5–6|64–70|64|
|11|6–7|70–71|70|
|12|7–8|71–77|71|
|13|8|77–78|77|
|14|8–9|78–83|78|
|15|9|83–85|83|
|16|9–10|85–91|85|
|17|10–11|91–100|91|
|18|11–12|100–103|100|
|19|12|103|103|
|20|12–13|103–106|103|
|21|13–14|106–113|106|
|21A|14|113–115|113|
|22|14–15|115–121|115|
|23|15|121–122|121|
|24|15–16|122–124|122|
|25|16–18|124–132|124|
|26|18|132–134|132|
|27|18–19|134–139|134|
|28|19–20|139–145|139|
|29|20|145–146|145|
|30|20–21|146–147|146|
|31|21|147–149|147|
|32|21|149–150|149|
|33|21–22|150–154|150|
|34|22–23|154–160|154|
|35|23|160–161|160|
|36|23–24|161–165|161|
|37|24|165–167|165|
|38|24–25|167–170|167|
|39|25|170–172|170|
|40|25–26|172–175|172|
|41|26|175|175|
|42|26–27|175–183|175|
|43|27|183–185|183|
|44|27–28|185–191|185|
|45|28–29|191–194|191|
|46|29|194–195|194|
|47|29|195|195|
|48|29|195–196|195|
|49|29–30|196–197|196|
|50|30|197–199|197|
|51|30|199–202|199|
|52|30|202|202|
|53|30–31|202–205|202, 203|
|54|31|205–207|205|
|55|31|207|207|

The four printed Division markers within Part 6 are recorded separately:

| Raw Division | Arrangement PDF marker | Body PDF marker |
|---|---:|---:|
|1|22|154|
|2|26|174|
|3|27|182|
|4|29|195|

### Code label table — 572 comparison positions

Retained Round 1 order/location pairing was re-used within the scoped Code only. Full raw lines, selection basis and discrepancy records are in `scope-and-label-evidence.json`; new native text is in `native-layout-raw.txt`. A comparison-row index is not a statutory label. Whitespace alternatives such as `13 A`/`13A` and `327A`/`327 A` remain visible too.

The four unresolved alternatives remain **`10A`/`l0A`, `l2A`/`12A`, `l4A`/`14A`, and arrangement `190` versus body `190A`**. There are two separate arrangement positions labelled `190`: the execution-of-death-sentence title and the passport title. No number was changed to create a one-to-one sequence.

**No Criminal Code catalogue was created.** All 572 heading positions can be paired, but a complete unique arrangement/body label set is not established: the arrangement has no distinct `190A` entry and retains the three l/1 alternatives. This does not claim that a whole Code body provision is absent. Supplying a catalogue key for each unresolved identity would require choosing a reading or source correspondence not settled here. Full body wording, present repeal status and federal/state scope remain outside this extraction map.

| Comparison row | Arrangement raw label; PDF page | Body raw label; PDF page | Status |
|---:|---|---|---|
|1|`1.`;p1|`1.`;p34|Raw observations|
|2|`2.`;p1|`2.`;p40|Raw observations|
|3|`3.`;p1|`3.`;p40|Raw observations|
|4|`4.`;p1|`4.`;p40|Raw observations|
|5|`5.`;p2|`5.`;p40|Raw observations|
|6|`6.`;p2|`6.`;p41|Raw observations|
|7|`7.`;p2|`7.`;p41|Raw observations|
|8|`8.`;p2|`8.`;p41|Raw observations|
|9|`9.`;p2|`9.`;p42|Raw observations|
|10|`10.`;p2|`10.`;p42|Raw observations|
|11|`10A.`;p2|`l0A.`;p42|Unresolved alternatives|
|12|`11.`;p2|`11.`;p43|Raw observations|
|13|`12.`;p2|`12.`;p43|Raw observations|
|14|`l2A.`;p2|`12A.`;p43|Unresolved alternatives|
|15|`13.`;p2|`13.`;p44|Raw observations|
|16|`13 A.`;p2|`13A.`;p44|Raw observations|
|17|`14.`;p2|`14.`;p44|Raw observations|
|18|`l4A.`;p2|`14A.`;p45|Unresolved alternatives|
|19|`15.`;p2|`15.`;p45|Raw observations|
|20|`16.`;p2|`16.`;p45|Raw observations|
|21|`17.`;p2|`17.`;p45|Raw observations|
|22|`18.`;p2|`18.`;p45|Raw observations|
|23|`19.`;p2|`19.`;p45|Raw observations|
|24|`20.`;p3|`20.`;p46|Raw observations|
|25|`21.`;p3|`21.`;p46|Raw observations|
|26|`22.`;p3|`22.`;p46|Raw observations|
|27|`23.`;p3|`23.`;p46|Raw observations|
|28|`24.`;p3|`24.`;p46|Raw observations|
|29|`25.`;p3|`25.`;p47|Raw observations|
|30|`26.`;p3|`26.`;p47|Raw observations|
|31|`27.`;p3|`27.`;p47|Raw observations|
|32|`28.`;p3|`28.`;p47|Raw observations|
|33|`29.`;p3|`29.`;p47|Raw observations|
|34|`30.`;p3|`30.`;p48|Raw observations|
|35|`31.`;p3|`31.`;p48|Raw observations|
|36|`32.`;p3|`32.`;p48|Raw observations|
|37|`33.`;p3|`33.`;p49|Raw observations|
|38|`34.`;p3|`34.`;p49|Raw observations|
|39|`35.`;p3|`35.`;p49|Raw observations|
|40|`36.`;p3|`36.`;p49|Raw observations|
|41|`37.`;p3|`37.`;p50|Raw observations|
|42|`38.`;p3|`38.`;p50|Raw observations|
|43|`39.`;p3|`39.`;p50|Raw observations|
|44|`40.`;p4|`40.`;p51|Raw observations|
|45|`41.`;p4|`41.`;p51|Raw observations|
|46|`42.`;p4|`42.`;p51|Raw observations|
|47|`43.`;p4|`43.`;p52|Raw observations|
|48|`44.`;p4|`44.`;p52|Raw observations|
|49|`45.`;p4|`45.`;p52|Raw observations|
|50|`46.`;p4|`46.`;p52|Raw observations|
|51|`46A.`;p4|`46A.`;p53|Raw observations|
|52|`47.`;p4|`47.`;p53|Raw observations|
|53|`48.`;p4|`48.`;p53|Raw observations|
|54|`49.`;p4|`49.`;p54|Raw observations|
|55|`49A.`;p4|`49A.`;p54|Raw observations|
|56|`49B.`;p4|`49B.`;p54|Raw observations|
|57|`49C.`;p4|`49C.`;p54|Raw observations|
|58|`49D.`;p4|`49D.`;p55|Raw observations|
|59|`50.`;p4|`50.`;p55|Raw observations|
|60|`51.`;p4|`51.`;p56|Raw observations|
|61|`52.`;p4|`52.`;p56|Raw observations|
|62|`53.`;p4|`53.`;p57|Raw observations|
|63|`54.`;p4|`54.`;p57|Raw observations|
|64|`55.`;p4|`55.`;p58|Raw observations|
|65|`56.`;p5|`56.`;p58|Raw observations|
|66|`57.`;p5|`57.`;p58|Raw observations|
|67|`58.`;p5|`58.`;p59|Raw observations|
|68|`59.`;p5|`59.`;p61|Raw observations|
|69|`60.`;p5|`60.`;p61|Raw observations|
|70|`61.`;p5|`61.`;p61|Raw observations|
|71|`62.`;p5|`62.`;p62|Raw observations|
|72|`62A.`;p5|`62A.`;p62|Raw observations|
|73|`63.`;p5|`63.`;p62|Raw observations|
|74|`64.`;p5|`64.`;p62|Raw observations|
|75|`65.`;p5|`65.`;p63|Raw observations|
|76|`66.`;p5|`66.`;p63|Raw observations|
|77|`67.`;p5|`67.`;p63|Raw observations|
|78|`68.`;p5|`68.`;p64|Raw observations|
|79|`69.`;p5|`69.`;p64|Raw observations|
|80|`70.`;p5|`70.`;p65|Raw observations|
|81|`71.`;p6|`71.`;p65|Raw observations|
|82|`72.`;p6|`72.`;p65|Raw observations|
|83|`73.`;p6|`73.`;p65|Raw observations|
|84|`74.`;p6|`74.`;p65|Raw observations|
|85|`75`;p6|`75.`;p66|Raw observations|
|86|`76.`;p6|`76.`;p66|Raw observations|
|87|`77.`;p6|`77.`;p66|Raw observations|
|88|`78.`;p6|`78.`;p66|Raw observations|
|89|`79.`;p6|`79.`;p66|Raw observations|
|90|`80.`;p6|`80.`;p67|Raw observations|
|91|`81.`;p6|`81.`;p67|Raw observations|
|92|`82.`;p6|`82.`;p67|Raw observations|
|93|`83.`;p6|`83.`;p67|Raw observations|
|94|`84.`;p6|`84.`;p67|Raw observations|
|95|`85.`;p6|`85.`;p67|Raw observations|
|96|`86.`;p6|`86.`;p67|Raw observations|
|97|`87.`;p6|`87.`;p68|Raw observations|
|98|`88.`;p6|`88.`;p68|Raw observations|
|99|`88A.`;p6|`88A.`;p69|Raw observations|
|100|`89.`;p6|`89.`;p70|Raw observations|
|101|`90.`;p6|`90.`;p70|Raw observations|
|102|`91.`;p7|`91.`;p70|Raw observations|
|103|`92.`;p7|`92.`;p70|Raw observations|
|104|`93.`;p7|`93.`;p70|Raw observations|
|105|`94.`;p7|`94.`;p70|Raw observations|
|106|`95.`;p7|`95.`;p70|Raw observations|
|107|`96.`;p7|`96.`;p70|Raw observations|
|108|`97.`;p7|`97.`;p70|Raw observations|
|109|`98.`;p7|`98.`;p71|Raw observations|
|110|`98A.`;p7|`98A.`;p72|Raw observations|
|111|`98B.`;p7|`98B.`;p73|Raw observations|
|112|`98C.`;p7|`98C.`;p74|Raw observations|
|113|`98D.`;p7|`98D.`;p74|Raw observations|
|114|`99.`;p7|`99.`;p75|Raw observations|
|115|`100.`;p7|`100.`;p75|Raw observations|
|116|`101.`;p7|`101.`;p75|Raw observations|
|117|`102.`;p7|`102.`;p75|Raw observations|
|118|`103.`;p7|`103.`;p75|Raw observations|
|119|`104.`;p7|`104.`;p75|Raw observations|
|120|`105.`;p7|`105.`;p76|Raw observations|
|121|`106.`;p7|`106.`;p76|Raw observations|
|122|`107.`;p7|`107.`;p76|Raw observations|
|123|`108.`;p8|`108.`;p76|Raw observations|
|124|`109.`;p8|`109.`;p77|Raw observations|
|125|`110.`;p8|`110.`;p77|Raw observations|
|126|`111.`;p8|`111.`;p77|Raw observations|
|127|`112.`;p8|`112.`;p78|Raw observations|
|128|`113.`;p8|`113.`;p78|Raw observations|
|129|`114.`;p8|`114.`;p78|Raw observations|
|130|`115.`;p8|`115.`;p78|Raw observations|
|131|`116.`;p8|`116.`;p78|Raw observations|
|132|`117.`;p8|`117.`;p78|Raw observations|
|133|`118.`;p8|`118.`;p79|Raw observations|
|134|`119.`;p8|`119.`;p79|Raw observations|
|135|`120.`;p8|`120.`;p79|Raw observations|
|136|`121`;p8|`121.`;p79|Raw observations|
|137|`122`;p8|`122.`;p80|Raw observations|
|138|`123.`;p8|`123.`;p80|Raw observations|
|139|`124.`;p8|`124.`;p80|Raw observations|
|140|`125.`;p8|`125.`;p80|Raw observations|
|141|`125A.`;p8|`125A.`;p80|Raw observations|
|142|`126.`;p8|`126.`;p81|Raw observations|
|143|`127.`;p8|`127.`;p81|Raw observations|
|144|`128.`;p9|`128.`;p81|Raw observations|
|145|`129.`;p9|`129.`;p82|Raw observations|
|146|`130.`;p9|`130.`;p82|Raw observations|
|147|`131.`;p9|`131.`;p82|Raw observations|
|148|`132.`;p9|`132.`;p82|Raw observations|
|149|`133.`;p9|`133.`;p82|Raw observations|
|150|`134.`;p9|`134.`;p83|Raw observations|
|151|`135.`;p9|`135.`;p84|Raw observations|
|152|`136.`;p9|`136.`;p84|Raw observations|
|153|`137.`;p9|`137.`;p84|Raw observations|
|154|`138.`;p9|`138.`;p84|Raw observations|
|155|`139.`;p9|`139.`;p84|Raw observations|
|156|`140.`;p9|`140.`;p85|Raw observations|
|157|`141.`;p9|`141.`;p85|Raw observations|
|158|`142.`;p9|`142.`;p85|Raw observations|
|159|`143.`;p9|`143.`;p85|Raw observations|
|160|`144.`;p9|`144.`;p85|Raw observations|
|161|`145.`;p9|`145.`;p85|Raw observations|
|162|`146.`;p9|`146.`;p85|Raw observations|
|163|`147.`;p9|`147.`;p86|Raw observations|
|164|`148.`;p9|`148.`;p86|Raw observations|
|165|`148A.`;p10|`148A.`;p87|Raw observations|
|166|`149`;p10|`149.`;p88|Raw observations|
|167|`150.`;p10|`150.`;p88|Raw observations|
|168|`151`;p10|`151.`;p88|Raw observations|
|169|`152.`;p10|`152.`;p88|Raw observations|
|170|`153.`;p10|`153.`;p89|Raw observations|
|171|`154.`;p10|`154.`;p89|Raw observations|
|172|`155.`;p10|`155.`;p89|Raw observations|
|173|`156.`;p10|`156.`;p90|Raw observations|
|174|`157.`;p10|`157.`;p90|Raw observations|
|175|`158.`;p10|`158.`;p90|Raw observations|
|176|`159.`;p10|`159.`;p90|Raw observations|
|177|`160.`;p10|`160.`;p90|Raw observations|
|178|`160A.`;p10|`160A.`;p91|Raw observations|
|179|`160B.`;p10|`160B.`;p91|Raw observations|
|180|`161.`;p10|`161.`;p91|Raw observations|
|181|`162.`;p10|`162.`;p91|Raw observations|
|182|`163.`;p10|`163.`;p91|Raw observations|
|183|`164.`;p10|`164.`;p92|Raw observations|
|184|`165.`;p10|`165.`;p92|Raw observations|
|185|`166.`;p10|`166.`;p92|Raw observations|
|186|`167.`;p10|`167.`;p92|Raw observations|
|187|`168.`;p10|`168.`;p92|Raw observations|
|188|`169.`;p11|`169.`;p92|Raw observations|
|189|`170.`;p11|`170.`;p93|Raw observations|
|190|`171.`;p11|`171.`;p93|Raw observations|
|191|`172.`;p11|`172.`;p94|Raw observations|
|192|`173.`;p11|`173.`;p94|Raw observations|
|193|`174.`;p11|`174.`;p94|Raw observations|
|194|`175.`;p11|`175.`;p95|Raw observations|
|195|`176.`;p11|`176.`;p95|Raw observations|
|196|`177.`;p11|`177.`;p96|Raw observations|
|197|`178.`;p11|`178.`;p97|Raw observations|
|198|`179.`;p11|`179.`;p97|Raw observations|
|199|`180.`;p11|`180.`;p98|Raw observations|
|200|`181.`;p11|`181.`;p98|Raw observations|
|201|`182.`;p11|`182.`;p98|Raw observations|
|202|`183.`;p11|`183.`;p98|Raw observations|
|203|`184.`;p11|`184.`;p99|Raw observations|
|204|`185.`;p11|`185.`;p99|Raw observations|
|205|`186.`;p11|`186.`;p99|Raw observations|
|206|`187.`;p11|`187.`;p99|Raw observations|
|207|`188.`;p11|`188.`;p99|Raw observations|
|208|`189.`;p11|`189.`;p99|Raw observations|
|209|`190.`;p11|`190.`;p100|Raw observations|
|210|`190.`;p12|`190A.`;p100|Unresolved alternatives|
|211|`191.`;p12|`191.`;p100|Raw observations|
|212|`192.`;p12|`192.`;p100|Raw observations|
|213|`193.`;p12|`193.`;p100|Raw observations|
|214|`194.`;p12|`194.`;p101|Raw observations|
|215|`195`;p12|`195.`;p101|Raw observations|
|216|`196.`;p12|`196.`;p101|Raw observations|
|217|`197.`;p12|`197.`;p101|Raw observations|
|218|`198.`;p12|`198.`;p101|Raw observations|
|219|`199.`;p12|`199.`;p102|Raw observations|
|220|`200.`;p12|`200.`;p102|Raw observations|
|221|`201.`;p12|`201.`;p102|Raw observations|
|222|`202.`;p12|`202.`;p102|Raw observations|
|223|`203.`;p12|`203.`;p102|Raw observations|
|224|`204.`;p12|`204.`;p103|Raw observations|
|225|`205.`;p12|`205.`;p103|Raw observations|
|226|`206.`;p12|`206.`;p103|Raw observations|
|227|`207.`;p12|`207.`;p104|Raw observations|
|228|`208.`;p12|`208.`;p104|Raw observations|
|229|`209.`;p13|`209.`;p104|Raw observations|
|230|`210.`;p13|`210.`;p104|Raw observations|
|231|`211.`;p13|`211.`;p105|Raw observations|
|232|`212.`;p13|`212.`;p105|Raw observations|
|233|`213.`;p13|`213.`;p105|Raw observations|
|234|`214.`;p13|`214.`;p106|Raw observations|
|235|`215.`;p13|`215.`;p106|Raw observations|
|236|`216.`;p13|`216.`;p106|Raw observations|
|237|`217.`;p13|`217.`;p106|Raw observations|
|238|`218.`;p13|`218.`;p106|Raw observations|
|239|`219.`;p13|`219.`;p107|Raw observations|
|240|`220.`;p13|`220.`;p107|Raw observations|
|241|`221.`;p13|`221.`;p107|Raw observations|
|242|`222.`;p13|`222.`;p108|Raw observations|
|243|`222A.`;p13|`222A.`;p108|Raw observations|
|244|`222B.`;p13|`222B.`;p108|Raw observations|
|245|`222C.`;p13|`222C.`;p108|Raw observations|
|246|`223.`;p13|`223.`;p109|Raw observations|
|247|`224.`;p13|`224.`;p109|Raw observations|
|248|`225.`;p13|`225.`;p109|Raw observations|
|249|`225A.`;p13|`225A.`;p110|Raw observations|
|250|`225B.`;p13|`225B.`;p110|Raw observations|
|251|`226.`;p13|`226.`;p111|Raw observations|
|252|`227.`;p14|`227.`;p111|Raw observations|
|253|`228.`;p14|`228.`;p111|Raw observations|
|254|`229.`;p14|`229.`;p112|Raw observations|
|255|`230.`;p14|`230.`;p112|Raw observations|
|256|`231.`;p14|`231.`;p112|Raw observations|
|257|`232.`;p14|`232.`;p112|Raw observations|
|258|`233.`;p14|`233.`;p112|Raw observations|
|259|`233A.`;p14|`233A.`;p112|Raw observations|
|260|`233B.`;p14|`233B.`;p113|Raw observations|
|261|`233C.`;p14|`233C.`;p113|Raw observations|
|262|`233D.`;p14|`233D.`;p113|Raw observations|
|263|`233E.`;p14|`233E.`;p114|Raw observations|
|264|`233F.`;p14|`233F.`;p115|Raw observations|
|265|`234.`;p14|`234.`;p115|Raw observations|
|266|`235.`;p14|`235.`;p116|Raw observations|
|267|`236.`;p14|`236.`;p116|Raw observations|
|268|`237.`;p14|`237.`;p117|Raw observations|
|269|`238.`;p15|`238.`;p117|Raw observations|
|270|`239.`;p15|`239.`;p117|Raw observations|
|271|`239A.`;p15|`239A.`;p118|Raw observations|
|272|`239B.`;p15|`239B.`;p118|Raw observations|
|273|`240.`;p15|`240.`;p118|Raw observations|
|274|`240A.`;p15|`240A.`;p119|Raw observations|
|275|`240B.`;p15|`240B.`;p119|Raw observations|
|276|`240C.`;p15|`240C.`;p119|Raw observations|
|277|`240D.`;p15|`240D.`;p119|Raw observations|
|278|`240E.`;p15|`240E.`;p120|Raw observations|
|279|`241.`;p15|`241.`;p120|Raw observations|
|280|`242.`;p15|`242.`;p120|Raw observations|
|281|`243.`;p15|`243.`;p121|Raw observations|
|282|`244.`;p15|`244.`;p121|Raw observations|
|283|`245.`;p15|`245.`;p121|Raw observations|
|284|`246.`;p15|`246.`;p121|Raw observations|
|285|`247.`;p15|`247.`;p122|Raw observations|
|286|`248.`;p15|`248.`;p122|Raw observations|
|287|`249.`;p15|`249.`;p122|Raw observations|
|288|`250.`;p15|`250.`;p123|Raw observations|
|289|`251.`;p16|`251.`;p123|Raw observations|
|290|`252.`;p16|`252.`;p124|Raw observations|
|291|`253.`;p16|`253.`;p124|Raw observations|
|292|`254.`;p16|`254.`;p124|Raw observations|
|293|`255.`;p16|`255.`;p124|Raw observations|
|294|`256.`;p16|`256.`;p124|Raw observations|
|295|`257.`;p16|`257.`;p125|Raw observations|
|296|`258.`;p16|`258.`;p125|Raw observations|
|297|`259.`;p16|`259.`;p125|Raw observations|
|298|`260.`;p16|`260.`;p125|Raw observations|
|299|`261.`;p16|`261.`;p126|Raw observations|
|300|`262.`;p16|`262.`;p126|Raw observations|
|301|`263.`;p16|`263.`;p126|Raw observations|
|302|`264.`;p16|`264.`;p126|Raw observations|
|303|`265.`;p16|`265.`;p126|Raw observations|
|304|`266.`;p16|`266.`;p126|Raw observations|
|305|`267.`;p16|`267.`;p126|Raw observations|
|306|`268.`;p16|`268.`;p126|Raw observations|
|307|`269.`;p16|`269.`;p126|Raw observations|
|308|`270.`;p16|`270.`;p126|Raw observations|
|309|`271.`;p16|`271.`;p126|Raw observations|
|310|`272.`;p17|`272.`;p126|Raw observations|
|311|`273.`;p17|`273.`;p127|Raw observations|
|312|`274.`;p17|`274.`;p127|Raw observations|
|313|`275.`;p17|`275.`;p127|Raw observations|
|314|`276.`;p17|`276.`;p127|Raw observations|
|315|`277.`;p17|`277.`;p127|Raw observations|
|316|`278.`;p17|`278.`;p127|Raw observations|
|317|`279.`;p17|`279.`;p128|Raw observations|
|318|`280.`;p17|`280.`;p128|Raw observations|
|319|`281.`;p17|`281.`;p128|Raw observations|
|320|`282.`;p17|`282.`;p128|Raw observations|
|321|`283.`;p17|`283.`;p128|Raw observations|
|322|`284.`;p17|`284.`;p129|Raw observations|
|323|`285.`;p17|`285.`;p129|Raw observations|
|324|`286.`;p17|`286.`;p129|Raw observations|
|325|`287.`;p17|`287.`;p130|Raw observations|
|326|`288.`;p17|`288.`;p130|Raw observations|
|327|`289.`;p17|`289.`;p130|Raw observations|
|328|`290.`;p17|`290.`;p130|Raw observations|
|329|`291.`;p17|`291.`;p130|Raw observations|
|330|`292.`;p17|`292.`;p130|Raw observations|
|331|`293.`;p17|`293.`;p131|Raw observations|
|332|`294.`;p17|`294.`;p131|Raw observations|
|333|`295.`;p17|`295.`;p131|Raw observations|
|334|`296.`;p18|`296.`;p132|Raw observations|
|335|`297.`;p18|`297.`;p132|Raw observations|
|336|`298.`;p18|`298.`;p132|Raw observations|
|337|`299.`;p18|`299.`;p132|Raw observations|
|338|`300.`;p18|`300.`;p133|Raw observations|
|339|`301.`;p18|`301.`;p133|Raw observations|
|340|`302.`;p18|`302.`;p133|Raw observations|
|341|`303.`;p18|`303.`;p133|Raw observations|
|342|`304.`;p18|`304.`;p133|Raw observations|
|343|`305.`;p18|`305.`;p133|Raw observations|
|344|`305A.`;p18|`305A.`;p134|Raw observations|
|345|`306.`;p18|`306.`;p134|Raw observations|
|346|`307.`;p18|`307.`;p135|Raw observations|
|347|`308.`;p18|`308.`;p135|Raw observations|
|348|`309.`;p18|`309.`;p135|Raw observations|
|349|`310.`;p18|`310.`;p135|Raw observations|
|350|`311.`;p18|`311.`;p135|Raw observations|
|351|`312.`;p18|`312.`;p135|Raw observations|
|352|`313.`;p18|`313.`;p135|Raw observations|
|353|`314.`;p18|`314.`;p135|Raw observations|
|354|`315.`;p18|`315.`;p136|Raw observations|
|355|`316.`;p19|`316.`;p136|Raw observations|
|356|`317.`;p19|`317.`;p137|Raw observations|
|357|`318.`;p19|`318.`;p137|Raw observations|
|358|`319.`;p19|`319.`;p137|Raw observations|
|359|`320.`;p19|`320.`;p137|Raw observations|
|360|`321.`;p19|`321.`;p138|Raw observations|
|361|`322.`;p19|`322.`;p138|Raw observations|
|362|`323.`;p19|`323.`;p138|Raw observations|
|363|`324.`;p19|`324.`;p138|Raw observations|
|364|`325.`;p19|`325.`;p138|Raw observations|
|365|`326.`;p19|`326.`;p138|Raw observations|
|366|`327.`;p19|`327.`;p138|Raw observations|
|367|`327A.`;p19|`327 A.`;p138|Raw observations|
|368|`328.`;p19|`328.`;p139|Raw observations|
|369|`329.`;p19|`329.`;p139|Raw observations|
|370|`329A.`;p19|`329A.`;p139|Raw observations|
|371|`330.`;p19|`330.`;p139|Raw observations|
|372|`331.`;p19|`331.`;p139|Raw observations|
|373|`332.`;p19|`332.`;p140|Raw observations|
|374|`333.`;p19|`333.`;p140|Raw observations|
|375|`334.`;p19|`334.`;p140|Raw observations|
|376|`335.`;p19|`335.`;p141|Raw observations|
|377|`336.`;p20|`336.`;p141|Raw observations|
|378|`337.`;p20|`337.`;p141|Raw observations|
|379|`338.`;p20|`338.`;p141|Raw observations|
|380|`339.`;p20|`339.`;p141|Raw observations|
|381|`340.`;p20|`340.`;p142|Raw observations|
|382|`341.`;p20|`341.`;p142|Raw observations|
|383|`342.`;p20|`342.`;p142|Raw observations|
|384|`343.`;p20|`343.`;p142|Raw observations|
|385|`344.`;p20|`344.`;p143|Raw observations|
|386|`345.`;p20|`345.`;p143|Raw observations|
|387|`346.`;p20|`346.`;p144|Raw observations|
|388|`347.`;p20|`347.`;p144|Raw observations|
|389|`348.`;p20|`348.`;p144|Raw observations|
|390|`349.`;p20|`349.`;p144|Raw observations|
|391|`350.`;p20|`350.`;p144|Raw observations|
|392|`351.`;p20|`351.`;p145|Raw observations|
|393|`352.`;p20|`352.`;p145|Raw observations|
|394|`353.`;p20|`353.`;p145|Raw observations|
|395|`354.`;p20|`354.`;p145|Raw observations|
|396|`355.`;p20|`355.`;p145|Raw observations|
|397|`356.`;p20|`356.`;p145|Raw observations|
|398|`357.`;p21|`357.`;p146|Raw observations|
|399|`358.`;p21|`358.`;p146|Raw observations|
|400|`359.`;p21|`359.`;p146|Raw observations|
|401|`360.`;p21|`360.`;p146|Raw observations|
|402|`361.`;p21|`361.`;p147|Raw observations|
|403|`362.`;p21|`362.`;p147|Raw observations|
|404|`363.`;p21|`363.`;p147|Raw observations|
|405|`364.`;p21|`364.`;p147|Raw observations|
|406|`365.`;p21|`365.`;p147|Raw observations|
|407|`366.`;p21|`366.`;p148|Raw observations|
|408|`367.`;p21|`367.`;p148|Raw observations|
|409|`368.`;p21|`368.`;p148|Raw observations|
|410|`369.`;p21|`369.`;p149|Raw observations|
|411|`370.`;p21|`370.`;p149|Raw observations|
|412|`371.`;p21|`371.`;p150|Raw observations|
|413|`372.`;p21|`372.`;p150|Raw observations|
|414|`373.`;p21|`373.`;p150|Raw observations|
|415|`374.`;p21|`374.`;p151|Raw observations|
|416|`375.`;p22|`375.`;p151|Raw observations|
|417|`376.`;p22|`376.`;p151|Raw observations|
|418|`377.`;p22|`377.`;p151|Raw observations|
|419|`378.`;p22|`378.`;p151|Raw observations|
|420|`379.`;p22|`379.`;p152|Raw observations|
|421|`380.`;p22|`380.`;p153|Raw observations|
|422|`381.`;p22|`381.`;p154|Raw observations|
|423|`382.`;p22|`382.`;p154|Raw observations|
|424|`383.`;p22|`383.`;p155|Raw observations|
|425|`384.`;p22|`384.`;p156|Raw observations|
|426|`385.`;p22|`385.`;p156|Raw observations|
|427|`386.`;p22|`386.`;p156|Raw observations|
|428|`387.`;p22|`387.`;p157|Raw observations|
|429|`388.`;p22|`388.`;p157|Raw observations|
|430|`389.`;p22|`389.`;p157|Raw observations|
|431|`390.`;p22|`390.`;p157|Raw observations|
|432|`391.`;p23|`391.`;p160|Raw observations|
|433|`392.`;p23|`392.`;p160|Raw observations|
|434|`393.`;p23|`393.`;p160|Raw observations|
|435|`394.`;p23|`394.`;p160|Raw observations|
|436|`395.`;p23|`395.`;p160|Raw observations|
|437|`396.`;p23|`396.`;p160|Raw observations|
|438|`397.`;p23|`397.`;p160|Raw observations|
|439|`398.`;p23|`398.`;p161|Raw observations|
|440|`399.`;p23|`399.`;p161|Raw observations|
|441|`400.`;p23|`400.`;p161|Raw observations|
|442|`401.`;p23|`401.`;p161|Raw observations|
|443|`402.`;p23|`402.`;p161|Raw observations|
|444|`403.`;p24|`403.`;p162|Raw observations|
|445|`403A.`;p24|`403A.`;p162|Raw observations|
|446|`403B.`;p24|`403B.`;p162|Raw observations|
|447|`404.`;p24|`404.`;p163|Raw observations|
|448|`405.`;p24|`405.`;p163|Raw observations|
|449|`406.`;p24|`406.`;p164|Raw observations|
|450|`407.`;p24|`407.`;p164|Raw observations|
|451|`408.`;p24|`408.`;p164|Raw observations|
|452|`409.`;p24|`409.`;p165|Raw observations|
|453|`410.`;p24|`410.`;p165|Raw observations|
|454|`411.`;p24|`411.`;p165|Raw observations|
|455|`412.`;p24|`412.`;p166|Raw observations|
|456|`413.`;p24|`413.`;p166|Raw observations|
|457|`414.`;p24|`414.`;p166|Raw observations|
|458|`415.`;p24|`415.`;p166|Raw observations|
|459|`416.`;p24|`416.`;p166|Raw observations|
|460|`417.`;p24|`417.`;p166|Raw observations|
|461|`418.`;p24|`418.`;p167|Raw observations|
|462|`419.`;p24|`419.`;p167|Raw observations|
|463|`419A.`;p24|`419A.`;p168|Raw observations|
|464|`419B.`;p24|`419B.`;p168|Raw observations|
|465|`420.`;p25|`420.`;p168|Raw observations|
|466|`421.`;p25|`421.`;p168|Raw observations|
|467|`422.`;p25|`422.`;p169|Raw observations|
|468|`423.`;p25|`423.`;p169|Raw observations|
|469|`424.`;p25|`424.`;p169|Raw observations|
|470|`425.`;p25|`425.`;p169|Raw observations|
|471|`426.`;p25|`426.`;p170|Raw observations|
|472|`427.`;p25|`427.`;p170|Raw observations|
|473|`428.`;p25|`428.`;p170|Raw observations|
|474|`429.`;p25|`429.`;p171|Raw observations|
|475|`430.`;p25|`430.`;p171|Raw observations|
|476|`431.`;p25|`431.`;p171|Raw observations|
|477|`432.`;p25|`432.`;p172|Raw observations|
|478|`433.`;p25|`433.`;p172|Raw observations|
|479|`434.`;p25|`434.`;p172|Raw observations|
|480|`435.`;p25|`435.`;p173|Raw observations|
|481|`436.`;p25|`436.`;p173|Raw observations|
|482|`437.`;p25|`437.`;p174|Raw observations|
|483|`438.`;p25|`438.`;p174|Raw observations|
|484|`439.`;p25|`439.`;p174|Raw observations|
|485|`440.`;p26|`440.`;p175|Raw observations|
|486|`441.`;p26|`441.`;p175|Raw observations|
|487|`442.`;p26|`442.`;p175|Raw observations|
|488|`443.`;p26|`443.`;p175|Raw observations|
|489|`444.`;p26|`444.`;p175|Raw observations|
|490|`445.`;p26|`445.`;p176|Raw observations|
|491|`446.`;p26|`446.`;p176|Raw observations|
|492|`447.`;p26|`447.`;p176|Raw observations|
|493|`448.`;p26|`448.`;p176|Raw observations|
|494|`449.`;p26|`449.`;p177|Raw observations|
|495|`450.`;p26|`450.`;p177|Raw observations|
|496|`451.`;p26|`451.`;p177|Raw observations|
|497|`452.`;p27|`452.`;p180|Raw observations|
|498|`453.`;p27|`453.`;p180|Raw observations|
|499|`454.`;p27|`454.`;p180|Raw observations|
|500|`455.`;p27|`455.`;p180|Raw observations|
|501|`456.`;p27|`456.`;p181|Raw observations|
|502|`457.`;p27|`457.`;p181|Raw observations|
|503|`458.`;p27|`458.`;p181|Raw observations|
|504|`459.`;p27|`459.`;p181|Raw observations|
|505|`459A.`;p27|`459A.`;p181|Raw observations|
|506|`459B.`;p27|`459B.`;p182|Raw observations|
|507|`460.`;p27|`460.`;p182|Raw observations|
|508|`461.`;p27|`461.`;p182|Raw observations|
|509|`462.`;p27|`462.`;p182|Raw observations|
|510|`463.`;p27|`463.`;p183|Raw observations|
|511|`464.`;p27|`464.`;p183|Raw observations|
|512|`465.`;p27|`465.`;p184|Raw observations|
|513|`466.`;p27|`466.`;p184|Raw observations|
|514|`467.`;p28|`467.`;p185|Raw observations|
|515|`468.`;p28|`468.`;p189|Raw observations|
|516|`469.`;p28|`469.`;p189|Raw observations|
|517|`470.`;p28|`470.`;p189|Raw observations|
|518|`471.`;p28|`471.`;p189|Raw observations|
|519|`472.`;p28|`472.`;p189|Raw observations|
|520|`473.`;p28|`473.`;p190|Raw observations|
|521|`474.`;p28|`474.`;p190|Raw observations|
|522|`475.`;p28|`475.`;p190|Raw observations|
|523|`476.`;p28|`476.`;p190|Raw observations|
|524|`477.`;p28|`477.`;p190|Raw observations|
|525|`478.`;p28|`478.`;p190|Raw observations|
|526|`479.`;p28|`479.`;p191|Raw observations|
|527|`480.`;p28|`480.`;p191|Raw observations|
|528|`480A.`;p28|`480A.`;p192|Raw observations|
|529|`481.`;p28|`481.`;p192|Raw observations|
|530|`482.`;p29|`482.`;p193|Raw observations|
|531|`483.`;p29|`483.`;p193|Raw observations|
|532|`484.`;p29|`484.`;p194|Raw observations|
|533|`485.`;p29|`485.`;p194|Raw observations|
|534|`486.`;p29|`486.`;p194|Raw observations|
|535|`487.`;p29|`487.`;p194|Raw observations|
|536|`488.`;p29|`488.`;p195|Raw observations|
|537|`489.`;p29|`489.`;p195|Raw observations|
|538|`490.`;p29|`490.`;p195|Raw observations|
|539|`491.`;p29|`491.`;p195|Raw observations|
|540|`492.`;p29|`492.`;p196|Raw observations|
|541|`493.`;p29|`493.`;p196|Raw observations|
|542|`494.`;p29|`494.`;p196|Raw observations|
|543|`495.`;p30|`495.`;p197|Raw observations|
|544|`496.`;p30|`496.`;p198|Raw observations|
|545|`497.`;p30|`497.`;p199|Raw observations|
|546|`498.`;p30|`498.`;p199|Raw observations|
|547|`499.`;p30|`499.`;p199|Raw observations|
|548|`500.`;p30|`500.`;p199|Raw observations|
|549|`501.`;p30|`501.`;p200|Raw observations|
|550|`502.`;p30|`502.`;p201|Raw observations|
|551|`503.`;p30|`503.`;p201|Raw observations|
|552|`504.`;p30|`504.`;p202|Raw observations|
|553|`505.`;p30|`505.`;p202|Raw observations|
|554|`506.`;p30|`506.`;p202|Raw observations|
|555|`507.`;p30|`507.`;p202|Raw observations|
|556|`508.`;p31|`508.`;p203|Raw observations|
|557|`509.`;p31|`509.`;p204|Raw observations|
|558|`510.`;p31|`510.`;p204|Raw observations|
|559|`511.`;p31|`511.`;p204|Raw observations|
|560|`512.`;p31|`512.`;p204|Raw observations|
|561|`513.`;p31|`513.`;p204|Raw observations|
|562|`514.`;p31|`514.`;p205|Raw observations|
|563|`515.`;p31|`515.`;p205|Raw observations|
|564|`516.`;p31|`516.`;p205|Raw observations|
|565|`516A.`;p31|`516A.`;p205|Raw observations|
|566|`517.`;p31|`517.`;p205|Raw observations|
|567|`517 A.`;p31|`517 A.`;p206|Raw observations|
|568|`518.`;p31|`518.`;p206|Raw observations|
|569|`518A.`;p31|`518A.`;p206|Raw observations|
|570|`519.`;p31|`519.`;p207|Raw observations|
|571|`520.`;p31|`520.`;p207|Raw observations|
|572|`521.`;p31|`521.`;p207|Raw observations|

## Task B — FCCPA 2018 label table and title catalogue

Retained official [FCCPC PDF](https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf), 99 pages; SHA-256 `aa942cdef860387e8f984de52666e5683d12d6e2813cb47b10335e0bf82a07f5`. New offline Apple Vision accurate passes at maximum 1800×2500 and arrangement/detail passes at 3600×5000 were run with language correction disabled and no expected-number vocabulary. Native Poppler text remains separate. Previously retained OCR/image observations are explicitly labelled as such; no Tesseract or Docker was run in this round.

The own arrangement occupies PDF 2–7, printed A1–A6. All **168 title positions are legible** in the six arrangement images; unreadable arrangement-title rows: **none located**. Created `backend/app/legal/data/federal-competition-and-consumer-protection-act-2018-section-titles.json`: expected count 168, 168 section titles, 18 printed Part titles, empty Chapters, source hash, `source.review_status:needs_review`, and raw-image/glitch notes. The existing reader loads 168 section titles and 18 Parts read-only. This satisfies the title-legibility condition; it does not establish complete reliable body text.

A source printing issue is explicit: the arrangement prints **`58` for Funding of the Tribunal and `58` again for Prohibition of agreements in restraint of competition**, on PDF 4. The latter title corresponds to body label `59` at PDF 33. Catalogue key `59` is that declared body correspondence, while notes preserve raw printed `58`; no OCR text is changed and no printed `59` is claimed. This differs from silently filling a sequence. Other source quirks retained include `Representation test and publication testimonials.`, `Conclusion by industry sector regulator.`, absent terminal stops on titles 46/89/100, and numeric labels 154/155 without stops. Titles were transcribed from the arrangement images, joining line wraps; grammatical glitches were not rewritten.

**Duplicated printed page A23:** PDF 24 and 25 both visibly/readably carry `A 23` and repeat headings 33/34, with different scan artefacts. Both PDFs’ page positions and both OCR observations remain; no deduplication, relabelling or replacement was performed.

The table’s alternatives combine separate image observations, native readings, the new Vision pass, and explicitly labelled retained earlier candidates. `label-evidence.json` holds surrounding text, confidence/geometry where available and association basis. `raw-prefix-addendum.json` exposes strict-parser misses such as `14r`, `7G.` and `12Z.`. Vision omitted the 119 opening: the content-based continuation selected in the first evidence record has no label and is not counted as a new Vision heading observation. Earlier/native candidates remain separate. Known false earlier candidates `15` at PDF 83 (cross-reference) and `20` at PDF 49 (part of 2018) were not used as headings.

| Reference row | Arrangement raw readings; PDF page | Body raw readings; PDF page(s) |
|---:|---|---|
|1|`1` / `l`;p2|`1` / `I` / `l`;p8|
|2|`2`;p2|`2`;p8|
|3|`3` / `J`;p2|`3`;p9|
|4|`4`;p2|`4`;p9|
|5|`5`;p2|`5`;p10|
|6|`6`;p2|`6`;p10|
|7|`7`;p2|`7`;p11|
|8|`8`;p2|`8`;p11|
|9|`9`;p2|`9`;p11|
|10|`10`;p2|`10`;p12|
|11|`11` / `Il`;p2|`11`;p12|
|12|`12`;p2|`12`;p12|
|13|`13`;p2|`13`;p12|
|14|`14`;p2|`14` / `14r`;p12|
|15|`15`;p2|`15`;p12|
|16|`16`;p2|`16`;p13|
|17|`17`;p2|`17`;p13|
|18|`18`;p2|`18`;p15|
|19|`19`;p2|`19`;p17|
|20|`20`;p2|`20`;p17|
|21|`21`;p2|`21`;p18|
|22|`22`;p2|`22`;p18|
|23|`23`;p3|`23`;p18|
|24|`24`;p3|`24`;p19|
|25|`25`;p3|`25`;p19|
|26|`26`;p3|`26`;p20|
|27|`27`;p3|`27`;p20|
|28|`28`;p3|`28`;p21|
|29|`29`;p3|`29` / `20`;p21|
|30|`30`;p3|`30`;p22|
|31|`31` / `3l`;p3|`31`;p23|
|32|`32`;p3|`32`;p23|
|33|`33`;p3|`33` / `J3`;p24,25|
|34|`34`;p3|`34`;p24,25|
|35|`35`;p3|`35`;p26|
|36|`36`;p3|`36`;p26|
|37|`37` / `3`;p3|`37`;p27|
|38|`38`;p3|`38`;p27|
|39|`39`;p3|`39`;p27|
|40|`40`;p3|`40`;p27|
|41|`41` / `4l`;p3|`41`;p28|
|42|`42`;p3|`42`;p28|
|43|`43`;p3|`43`;p28|
|44|`44`;p3|`44`;p28|
|45|`45`;p3|`45`;p28|
|46|`46`;p3|`46`;p29|
|47|`47`;p3|`47`;p29|
|48|`48`;p3|`48`;p29|
|49|`49`;p3|`49`;p30|
|50|`50`;p3|`50`;p30|
|51|`51` / `Sl`;p3|`51`;p31|
|52|`52`;p3|`52`;p31|
|53|`53`;p3|`53`;p31|
|54|`54` / `$4`;p3|`54`;p32|
|55|`55`;p3|`55`;p32|
|56|`56`;p3|`56`;p32|
|57|`57`;p4|`57`;p32|
|58|`58`;p4|`58`;p32|
|59|`58`;p4|`59`;p33|
|60|`60`;p4|`60`;p33|
|61|`61`;p4|`61`;p34|
|62|`62`;p4|`62`;p34|
|63|`63`;p4|`63`;p34|
|64|`64`;p4|`64`;p35|
|65|`65`;p4|`65`;p35|
|66|`66`;p4|`66`;p35|
|67|`67`;p4|`67`;p37|
|68|`68`;p4|`68`;p37|
|69|`69`;p4|`69`;p38|
|70|`70`;p4|`70`;p39|
|71|`71`;p4|`71`;p39|
|72|`72`;p4|`72`;p39|
|73|`73`;p4|`73`;p41|
|74|`74`;p4|`74` / `7`;p41|
|75|`75`;p4|`75`;p41|
|76|`76` / `J6`;p4|`76` / `7G.`;p41|
|77|`77`;p4|`77`;p42|
|78|`78`;p4|`78`;p42|
|79|`79`;p4|`79`;p42|
|80|`80`;p4|`80`;p42|
|81|`81`;p4|`81`;p42|
|82|`82`;p4|`82`;p43|
|83|`83`;p4|`83`;p43|
|84|`84`;p4|`84`;p43|
|85|`85`;p4|`85`;p44|
|86|`86`;p4|`86` / `35`;p44|
|87|`87`;p4|`87`;p46|
|88|`88`;p5|`88`;p47|
|89|`89`;p5|`89`;p48|
|90|`90`;p5|`90`;p49|
|91|`91`;p5|`91`;p49|
|92|`92`;p5|`92`;p50|
|93|`93`;p5|`93`;p51|
|94|`94`;p5|`94`;p52|
|95|`95`;p5|`95`;p53|
|96|`96`;p5|`96`;p54|
|97|`97`;p5|`97`;p55|
|98|`98`;p5|`98`;p55|
|99|`99`;p5|`99`;p56|
|100|`100`;p5|`100`;p56|
|101|`101`;p5|`101`;p56|
|102|`102`;p5|`102`;p57|
|103|`103`;p5|`103`;p57|
|104|`104`;p5|`104`;p57|
|105|`105` / `10S`;p5|`105`;p57|
|106|`106` / `I06`;p5|`106`;p58|
|107|`107`;p5|`107`;p59|
|108|`108` / `l08`;p5|`108`;p60|
|109|`109`;p5|`109`;p60|
|110|`110`;p5|`110`;p61|
|111|`111` / `I11`;p5|`111`;p61|
|112|`112` / `ll2`;p5|`112`;p62|
|113|`113` / `1` / `I13`;p5|`113`;p62|
|114|`114`;p5|`114`;p62|
|115|`115` / `I`;p5|`115` / `ll5`;p63|
|116|`116` / `I`;p5|`116`;p63|
|117|`117` / `I17`;p5|`117`;p64|
|118|`118` / `I`;p6|`118`;p64|
|119|`119` / `I19`;p6|`119`;p65|
|120|`120`;p6|`120`;p65|
|121|`121`;p6|`121` / `12l`;p65|
|122|`122`;p6|`122` / `12Z.`;p66|
|123|`123`;p6|`123`;p66|
|124|`124`;p6|`124`;p68|
|125|`125`;p6|`125`;p68|
|126|`126`;p6|`126`;p69|
|127|`127`;p6|`127`;p69|
|128|`128`;p6|`128`;p70|
|129|`129`;p6|`129`;p70|
|130|`130`;p6|`130`;p71|
|131|`131` / `13I` / `l3`;p6|`131`;p72|
|132|`132` / `J32`;p6|`132`;p72|
|133|`133`;p6|`133`;p73|
|134|`134`;p6|`134`;p73|
|135|`135`;p6|`135`;p73|
|136|`136`;p6|`136`;p74|
|137|`137`;p6|`137`;p74|
|138|`138`;p6|`138`;p75|
|139|`139`;p6|`139`;p75|
|140|`140`;p6|`140`;p75|
|141|`141`;p6|`141`;p75|
|142|`142`;p6|`142`;p76|
|143|`143`;p6|`143`;p76|
|144|`144`;p6|`144`;p76|
|145|`145`;p6|`145`;p77|
|146|`146`;p6|`146`;p77|
|147|`147`;p6|`147`;p77|
|148|`148`;p6|`148`;p77|
|149|`149`;p6|`149`;p78|
|150|`150`;p6|`150`;p78|
|151|`151`;p6|`151` / `I5`;p79|
|152|`152`;p6|`152`;p80|
|153|`153` / `I53`;p6|`153`;p80|
|154|`154`;p7|`154`;p80|
|155|`155`;p7|`155`;p81|
|156|`156`;p7|`156`;p81|
|157|`157`;p7|`157`;p82|
|158|`158`;p7|`158`;p82|
|159|`159`;p7|`159`;p83|
|160|`160`;p7|`160` / `I60`;p83|
|161|`161` / `16l`;p7|`161`;p84|
|162|`162`;p7|`162`;p84|
|163|`163`;p7|`163`;p85|
|164|`164`;p7|`164`;p86|
|165|`165`;p7|`165`;p86|
|166|`166`;p7|`166`;p87|
|167|`167`;p7|`167`;p87|
|168|`168`;p7|`168`;p94|

## Task C — Minimum Wage Act 2019 offline OCR

Retained ILO [NATLEX attachment](https://natlex.ilo.org/dyn/natlex2/natlex2/files/download/111617/NGA111617%20.pdf), 14-page assent-bearing scan from round 3. SHA-256 `6d624addf4e94c994c2caf3fa37ed82261fb2c13d9858163a4dcdaac3a886f23`. Original unchanged; no new download. It has zero native words on every page. New raw OCR, line confidence, geometry and previews are in `round4-minimum-wage-2019/`.

Offline Apple Vision accurate was run on all 14 pages at maximum 1800×2500, plus an independent 3600×5000 detail pass on 2,3,6,7,13,14. Language correction was disabled. Candidate confidence is an engine score, not a probability that legal wording is right. Neither pass was adopted as canonical; all raw lines are retained below and in JSON.

All 18 arrangement titles are legible on PDF 2. Created `backend/app/legal/data/national-minimum-wage-act-2019-section-titles.json`, with expected count 18, 18 titles, empty Parts/Chapters because none are printed in this arrangement, source SHA-256, `needs_review` and notes. The existing reader loads all 18 titles. The image visibly prints label 7, which both arrangement OCR passes omit; it is a separate visual observation, not an OCR repair. The detail pass’s `Employerto` remains raw while the independent image transcription reads `Employer to`.

### Arrangement titles and body-label observations

All arrangement titles below are separate image transcriptions from PDF 2. Body locations use opening content and page position. A raw alternative is not replaced by an expected number.

| Reference row / visually observed arrangement label | Arrangement title as printed | Body PDF page | Raw body reading(s) / observation |
|---:|---|---:|---|
|1|Objective of this Act.|3|separate visual 1.|
|2|Application.|3|2|
|3|Employer to pay minimum wage.|3|3|
|4|Exemptions.|3|4|
|5|Establishment of Tripartite Committee on National Minimum Wage.|4|5|
|6|Composition of the Tripartite Committee.|4|6|
|7|Powers of Tripartite Committee.|5|7|
|8|Meetings of the Tripartite Committee.|5|8|
|9|Employer's obligations in respect of minimum wage.|5|9|
|10|Employers to keep records.|6|separate visual 10.|
|11|Officers and their powers.|6|1f. / Il. / separate visual 11.|
|12|Monitoring and compliance.|7|12|
|13|Enforcement.|7|• 3. / 13.|
|14|Offences by an agent.|8|14|
|15|Other offences and penalties.|9|standalone Vision `15.`; opening line has no captured label|
|16|Repeal and savings provisions.|10|16|
|17|Interpretation.|11|17|
|18|Citation.|12|18|

Body 1/10 prefixes were omitted by the OCR opening lines; separate image observations record `1.`/`10.`. Body 11 includes raw `1f.` and `Il`, alongside a separate visual `11.`. Body 13 includes raw `• 3.`/`13.` alternatives. These observations do not correct the full page text. The isolated `15.` appears elsewhere in the page’s OCR reading order and is not silently moved into the opening sentence.

### Schedule/table and raw date observations

PDF 14 is headed **Schedule to the National Minimum Wage Bill, 2019**. Separate visual cell observations:

- **SHORT TITLE OF THE BILL:** National Minimum Wage, Bill, 2019.
- **LONG TITLE OF THE BILL:** An Act to repeal the National Minimum Wage Act, Cap N61, Laws of the Federation of Nigeria, 2004 and enact the National Minimum Wage Act, 2019 to prescribe a national minimum wage for workers; and for related matters.
- **SUMMARY OF THE CONTENTS OF THE BILL:** This Bill repeals the National Minimum Wage Act Cap. N61, Laws of the Federation of Nigeria, 2004 and enact the National Minimum Wage Act, 2019 to prescribe a national minimum wage and provide a legal framework for seamless review of the national minimum wage.
- **DATE PASSED BY THE SENATE:** 19th March, 2019
- **DATE PASSED BY THE HOUSE OF REPRESENTATIVES:** 29th January, 2019

The table is followed by clerk certification and assent. PDF 13 also contains clerk certification. `A Bill` on PDF 3, the empty commencement bracket and Bill wording on the authentication schedule remain source observations alongside the signature images; they were not silently removed or treated as conclusive proof of a draft.

**Both date layers on PDF 14 are retained, with no date chosen:** the handwritten day appears `18` against the printed line `Day of March, 2019`, with `March` crossed out; a separate handwritten `April` appears below it. Vision1800 reads `18 Day of Aarala, 2019` and separate `April`; Vision3600 reads `18 Day of Mazeala, 2019` and separate `April`. Raw strings, their line confidence and geometry remain in the files. No canonical date or repaired month was produced. Signature appearance was inspected, not authenticated.

### Page-by-page raw text with line confidence

The following is the complete first-pass output; the detail pass remains separately retained in `vision-detail-raw.json`. Table rendering escapes a literal pipe only; the JSON preserves exact strings.



Line confidence is the engine candidate confidence, not accuracy. Strings below remain uncorrected; geometry and source metadata are in the JSON.

#### PDF page1

| Line confidence | Raw line |
|---:|---|
|1|NATIONAL MINIMUM WAGE ACT, 2019|
|1|EXPLANATORY MEMORANDUM|
|1|This Act repeals the National Minimum Wage Act Cap. N61, Laws of the Federation of Nigeria,|
|1|2004 and enact the National Minimum Wage Act, 2019 to prescribe a national minimum wage|
|1|and provide a legal framework for seamless review of the national minimum wage.|

#### PDF page2

| Line confidence | Raw line |
|---:|---|
|1|--|
|1|NATIONAL MINIMUM WAGE ACT, 2019|
|1|Arrangement of Sections|
|1|Section:|
|1|1. Objective of this Act.|
|1|2.|
|1|Application.|
|1|3. Employer to pay minimum wage.|
|1|4. Exemptions.|
|1|5. Establishment of Tripartite Committee on National Minimum Wage.|
|1|6. Composition of the Tripartite Committee.|
|1|Powers of Tripartite Committee.|
|1|8.|
|1|Meetings of the Tripartite Committee.|
|1|9. Employer's obligations in respect of minimum wage.|
|1|10. Employers to keep records.|
|1|11. Officers and their powers.|
|1|12. Monitoring and compliance.|
|1|13. Enforcement.|
|1|14. Offences by an agent.|
|1|15. Other offences and penalties.|
|1|16. Repeal and savings provisions.|
|1|17. Interpretation.|
|1|18. Citation.|

#### PDF page3

| Line confidence | Raw line |
|---:|---|
|1|NATIONAL MINIMUM WAGE ACT, 2019|
|1|A Bill|
|1|For|
|1|An Act to repeal the National Minimum Wage Act, Cap. N61, Laws of the Federation of|
|1|Nigeria, 2004 and enact the National Minimum Wage Act, 2019 to prescribe a national|
|1|minimum wage for workers; and for related matters.|
|1|} Commencement.|
|1|ENACTED by the National Assembly of the Federal Republic of Nigeria -|
|1|This Act is to prescribe the national minimum wage and provide for a legal framework Objective ofthis Act.|
|1|for a seamless review of the national minimum wage within the period specified under|
|1|this Act.|
|1|2. This Act applies throughout the Federal Republic of Nigeria.|
|1|Application.|
|1|3. (1) Every employer shall pay a national minimum wage of not less than #30,000.00 per Eiployer torpay|
|1|month to every worker under his establishment, except as otherwise provided under|
|1|this Act.|
|1|(2) The national minimum wage shall be the minimum total amount of money an|
|1|employer of labour is required to pay the lowest paid worker or employee monthly in|
|1|his establishment.|
|1|(3) Any agreement for the payment of wages less than the national minimum wage is|
|1|void.|
|1|(4) The national minimum wage expires after five years, and it shall be reviewed in line|
|1|with the provisions of this Act.|
|1|4. (1) Section 3 (1) does not apply to-|
|1|Exemptions.|
|1|(a) an establishment in which workers are employed or|
|1|paid on -|
|1|(1)|
|1|part-time basis, and|
|1|(1i)|
|1|commission or piece-rate;|
|1|(b) an establishment employing less than 25 persons;|

#### PDF page4

| Line confidence | Raw line |
|---:|---|
|1|(c) workers in seasonal employment like agriculture; and|
|1|(d) any person employed in a vessel or aircraft to which the|
|1|laws regulating merchant shipping or civil aviation|
|1|apply,|
|1|(2) The Minister of Labour and Employment shall, through the National Labour|
|1|Advisory Council and by order published in the Federal Government Gazette, grant|
|1|other exemptions as he deems necessary in the interest of the national economy,|
|1|taking into consideration reports from National Salaries, Incomes and Wages|
|1|Commission or such other body that may make representation for exemption.|
|1|5. (1) There is established the Tripartite Committee on National Minimum Wage (in this Establishment of|
|1|Act referred to as "the Tripartite Committee") consisting of representatives of|
|1|Tripartite Committee o|
|1|National Minimun|
|1|Government, organised labour and private sector, on equal representation.|
|1|Wage.|
|1|(2) The Secretariat of the Tripartite Committee shall be domiciled in the National|
|1|Salaries, Income and Wages Commission.|
|1|6. (1) The Tripartite Committee as constituted shall be appointed by the President and shall Composition of the|
|1|consist of -|
|1|Tripartite Committee.|
|1|(a) a chairman;|
|1|(b) a secretary;|
|1|(c) a representative each of -|
|1|(i) the Secretary to the Government of the Federation,|
|1|(ii) Head of Civil Service of the Federation,|
|1|(iii) Minister of Labour and Employment,|
|1|(iv) Minister of Finance,|
|1|(V) Minister of Budget and National Planning,|

#### PDF page5

| Line confidence | Raw line |
|---:|---|
|1|-|
|1|(VI) the Executive Chairman, National|
|1|Salaries,|
|1|Income and Wages Commission, and|
|1|(d) a Governor from each of the six geo-political zones to|
|1|be nominated by the Governors from that zone;|
|1|(e) a representative each of the organised labour from -|
|1|(i) Nigeria Labour Congress,|
|1|(ii) Trade Union Congress, and|
|1|(iii) any labour centre that may be registered in|
|1|accordance with the labour laws; and|
|1|(f) a representative each from -|
|1|(i) Nigeria Employer's Consultative Association,|
|1|(ii) Manufacturers Association of Nigeria,|
|1|(iii) Nigeria Association of Chambers of Commerce,|
|1|Industry, Mines and Agriculture,|
|1|(iv) Nigeria Association of Small and Medium|
|1|Enterprises, and|
|1|(v) any such employers group that may be registered|
|1|in accordance with the labour laws.|
|1|(2) The membership listed under subsection (1) may be expanded by the appointment of|
|1|additional members, on the recommendation by the Minister of Labour and|
|1|Employment, to the President.|
|1|7. The Tripartite Committee shall have all the powers to make recommendations on the Powers of Tripartite|
|1|national minimum wage, more especially to exercise the powers of review given under Committee.|
|1|section 3 (4) of this Act.|
|1|8. The meeting ot the Impartite Committee shail be convened by the Chairman, as may be Meetings of the|
|1|expedient but not later than six months to the expiration of the existing national|
|1|Tripartite Committee.|
|1|minimum wage, to consider a new national minimum wage, the proceedings and other|
|1|supplementary provisions relating to the Tripartite Committee shall be decided by its|
|1|members.|
|1|9. (1) An employer shall pay to the workers a wage not less than the national minimum Employer's obligations in|
|1|wage, subject to statutory deductions.|
|1|respect of minimum|
|1|wage.|
|1|(2) Any employer who fails to comply with subsection (1), commits an offence and is|

#### PDF page6

| Line confidence | Raw line |
|---:|---|
|1|liabie on conviction to pay -|
|1|-|
|1|(a) a fine not exceeding 5% of the offenders monthly wage;|
|1|(b) all outstanding arrears of the workers' wages; and|
|1|(c) an additional penalty of not less than the prevailing|
|1|Central Bank of Nigeria lending rate on the wages owed,|
|1|for each month of continuing violation, provided that the|
|1|power to order payment on account of wages under|
|1|subsection (2) shall not derogate from the right of the|
|1|worker to recover wages due to him by any other|
|1|proceeding in a court of competent jurisdiction.|
|1|(1) An employer shall keep such records of wages or conditions of employment as are|
|1|Employers to keep|
|1|necessary to show that the provisions of this Act are being complied with in respect|
|1|records.|
|1|of workers in his employment and to retain the records for three years after the|
|1|period to which they refer.|
|1|(2) Any employer who fails to comply with subsection (1), commits an offence and is|
|1|liable on conviction to -|
|1|(a) a fine not exceeding #75,000.00; and|
|1|(b) an additional penalty not exceeding #10,000.00 for|
|1|each day the offence continues.|
|1|1f. fl) The Minister of Labour and Employrent may authorise any officer in the Civil|
|1|Officers and their|
|1|Service of the Federation to act for the purpose of this Act, and every authorised|
|1|powers.|
|1|labour officer within the meaning of the Labour Act is deemed to have been|
|1|Cap. LI, LFN, 2004.|
|1|authorised.|
|1|(2) Every authorised officer shall be furnished with a letter of authority and|
|1|identification when visiting an employer's premises for the purposes of this Act and|
|1|shall, if so required, produce both documents to the employer or other person|
|1|holding a responsible position of management at the said premises.|
|1|(3) An authorised officer may-|
|1|(a) require the production by an employer of wages sheets|
|1|payroll, other records of wages and records of conditions|

#### PDF page7

| Line confidence | Raw line |
|---:|---|
|1|of employment, inspect and examine them and copy any|
|1|part;|
|1|(b) order any person or body of persons found to have|
|1|contravened any of the provisions of this Act to take|
|1|remedial action within a specified period of time; and|
|1|(C) make recommendation for the prosecution of any person|
|1|who contravenes the provisions of this Act.|
|1|(4) An officer who is authorised in that behalf by genera! or special directions of the|
|1|Minister may, if it appears to him that a sum is due from an employer to a worker to|
|1|whom this Act applies or to a person who has been a worker on account of the|
|1|payment to him of wages less than the national minimum wage, institute, on behalf|
|1|and in the name of that worker or person, civil proceedings for the recovery of that|
|1|sum, and in any proceeding, the court may make an order for the payment of costs|
|1|by the authorised officer as if he were a party to the proceedings.|
|1|(5) The power given under subsection (4) for the recovery of a sum due from an|
|1|employer to a worker or former worker shall not derogate from any right to recover|
|1|that sum by civil proceedings.|
|1|12. (1) The Ministry of Labour and Employment and National Salaries, Incomes and Wages|
|1|Monitoring and|
|1|Commission shall collaborate to monitor the implementation of the national|
|1|compliance.|
|1|minimum wage in line with the provisions of the Labour Act and National Salaries,|
|1|Cap. LI, LFN, 2004.|
|1|Incomes and Wages Commission Act.|
|1|Cap. N72, LEN, 2004.|
|1|(2) Any report of non-compliance with the provisions of this Act discovered by the|
|1|authorised officer upon routine inspection shall be forwarded to the Minister of|
|1|Labour and Employment and copied to labour centres and employment associations.|
|1|(3) The Minister of Labour and Employment shall, upon receipt of such report, activate|
|1|the machinery for enforcing compliance to redress the breach within 30 working|
|1|days.|
|1|(4) Monitoring of compliance with this Act shall commence six months after the|
|1|commencement of this Act.|
|1|• 3. The national minimum wage may be enforced by the aggrieved worker, trade unions and|
|1|Enforcement.|
|1|Minister of Labour and Employment as follows -|

#### PDF page8

| Line confidence | Raw line |
|---:|---|
|1|(a) a worker who is paid an amount less than the national|
|1|minimum wage is contractually entitled to whichever is|
|1|the higher amount of the difference between his pay and|
|1|the amount of the national minimum wage that he should|
|1|have been paid;|
|1|(b) the worker has the right to take his case directly to the|
|1|National Industrial Court, or may file a formal complaint|
|1|with the Minister of Labour and Employment;|
|1|(c) trade unions may demand for compliance with the|
|1|provisions of this Act, on behalf of their members and|
|1|shall not later than 30 days from the receipt of the|
|1|workers complaint, file the claim to the National|
|1|Industrial Court;|
|1|(d) where an employer fails to pay the national minimum|
|1|wage to a worker or a group of workers, an authorised|
|1|officer shall serve a notice of enforcement requiring the|
|1|employer to pay the arrears of the wage to the worker|
|1|named on the notice within 30 days, but the employer is|
|1|entitled to appeal the notice to the Minister of Labour|
|1|and Employment who shall resolve the matter within 30|
|1|days of the receipt of the appeal;|
|1|(e) the notice of enforcement shall state the -|
|1|(i) amount owed to the worker,|
|1|(ii) period to which the payment applies, and|
|1|(iii) time limit for the payment; and|
|1|(f) where an employer served with an enforcement notice|
|1|fails, in whole or in part, to comply with the notice, the|
|1|matter shall be referred to the National Industrial|
|1|Court:|
|1|14. (1) Where an offence under this Act is committed by an agent of the employer or some|
|1|other person, that agent or other person is liable to be proceeded against for the|
|1|offence in the same manner as if he were the employer.|
|1|Offences by an agent.|

#### PDF page9

| Line confidence | Raw line |
|---:|---|
|0.30000001192092896|: -|
|1|--|
|1|15.|
|1|(2) An employer who is charged with an offence under this Act is entitled to prove that -|
|1|(a) the offence was due fo the act or default of another|
|1|person; or|
|1|(b) he has used all due diligence to ensure that this Act is|
|1|complied with.|
|1|(3) Where a defendant seeks to avail himself the defense under subsection (2) -|
|1|(a) the prosecution and person whom the defendant charges|
|1|with the offence shall have the right to -|
|1|(i) cross-examine the defendant if he gives evidence,|
|1|and any witness called by him in support of his|
|1|plea, and|
|1|(ii) call rebutting evidence; and|
|1|(b) the court may make such order as it deems fit for the|
|1|payment of the costs by any party to the proceedings,|
|1|other than the prosecution, or to any other party thereto.|
|1|(4) Where it appears to an authorised officer that an offence has been committed in|
|1|respect of which proceedings might be taken under this Act against an employer, and|
|1|the authorised officer is reasonably satisfied that the offence of which complaint is|
|1|made was due to an act or default of some other person and that the employer could|
|1|establish a defence under subsection (2), the authorised officer may make|
|1|recommendation for proceedings to be taken against that other person, and in such|
|1|proceedings, the defendant may be charged with the offence and, on proof that the|
|1|offence was due to his act or default, be convicted for the offence for which the|
|1|employer might have been charged.|
|1|A person commits an offence and is liable on conviction to a fine not exceeding Other offences and|
|1|#250,000.00 or imprisonment for a term not exceeding six months or both, where the|
|1|penalties.|
|1|person -|
|1|(a) refuses or neglects to furnish the means required by an|
|1|authorised officer as being necessary for any entry in|
|1|the exercise of his powers under this Act;|

#### PDF page10

| Line confidence | Raw line |
|---:|---|
|1|=-|
|1|(b) hinders any authorised officer in the exercise of his|
|1|powers under this Act;|
|1|(c) refuses or neglects to produce any document or give|
|1|any information which an authorised officer, in the|
|1|exercise of his powers under this Act, requires him to|
|1|produce or give;|
|1|(d) makes or causes to be made, or knowingly allows to be|
|1|made, any wages sheet, record of wages or record of|
|1|conditions of employment which is false;|
|1|(e) produces or causes to be produced, oi knowingly|
|1|allows to be produced, any wages sheet or record to an|
|1|authorised officer, in the exercise of his powers under|
|1|this Act, knowing the wages sheet or record to be false;|
|1|or|
|1|(E) furnishes any information to any authorised officer in|
|1|the exercise of his powers under this Act, knowing the|
|1|information to be false.|
|1|16. (1) The National Minimum Wage Act, Cap. N61, Laws of the Federation of Nigeria, Rrpieal and savings|
|1|2004 is repealed|
|1|(2) Without prejudice to section 6 of the Interpretation Act and notwithstanding the|
|1|repeal of the enactment specified under subsection (1) -|
|1|(a) proceedings may be taken on any offence committed|
|1|under the repealed Act, in the same manner as if the|
|1|offence has been committed under the corresponding|
|1|provisions of this Act; and|
|1|(b) any proceeding or cause of action pending or existing|
|1|immediately before the commencement of this Act, by|
|1|or against any person or body arising from the repealed|
|1|Act in respect of rights, interest, obligations or liabilities|
|1|of that person or body may be continued or commenced,|
|1|and any determination of a court, tribunal or other|
|1|authority or person may be enforced to the same extent|
|1|that any proceeding, cause of action or determination|
|1|would have been continued, commenced or enforced if|

#### PDF page11

| Line confidence | Raw line |
|---:|---|
|0.5|i...|
|1|--|
|1|-|
|1|this Act had not been made.|
|1|17. In this Act-|
|1|"authorised officer" means an officer in the Public Service of the Federation authorised|
|1|or deemed to have been authorised to act for the purpose of this Act;|
|1|"authorised labour officer" means any public officer serving in a Ministry or Department|
|1|for which the Minister of Labour and Employment is responsible, and with the consent|
|1|of the state authority, any officer in the public service of the state, for the purposes of|
|1|this Act;|
|1|"employer" means any person who has entered into a contract of employment to employ|
|1|any other person as a worker either for himself or for the service of any other person,|
|1|and includes the agent, manager or factor of employer and the personal representative of|
|1|a deceased employer;|
|1|"Minister of Labour and Employment" means the Minister responsible for labour|
|1|matters;|
|1|"Minister of Finance" means the Minister responsible for finance;|
|1|"Minister of Budget and National Planning" means the Minister responsible for budget;|
|1|"national minimum wage" means the national minimum wage prescribed under section 3|
|1|(1) of this Act;|
|1|"part-time work" means work of a duration shorter than those for comparable full-time|
|1|work in a sector or occupation;|
|1|"piece-rate" means any type of employment in which a worker is paid according to the|
|1|quantity produced regardless of time;|
|1|"wage" means remuneration or earnings (however designated or calculated) capable of|
|1|being expressed in terms of money fixed by mutual agreement or by law which is|
|1|payable by virtue of a contact by an employer for work done or to be done for service|
|1|rendered; and|
|1|"worker" means any person who has entered into or works under a contract with an|
|1|employer whether contract is for manual labour, clerical work, is expressed or implied,|
|1|oral or written, and whether it is a contract of service or a contract personally to execute|
|1|Interpretation.|

#### PDF page12

| Line confidence | Raw line |
|---:|---|
|1|....|
|1|âny work or labour, but excludes the exemptions contained in this Act.|
|1|18. This Act may be cited as the National Minimum Wage Act, 2019.|
|1|Citation.|

#### PDF page13

| Line confidence | Raw line |
|---:|---|
|1|1, CERTIFY, IN ACCORDANCE WITH SECTION 2 (1) OF THE ACTS|
|1|AUTHENTICATION ACT CAP. A2, LAWS OF THE FEDERATION OF NIGERIA 2004,|
|1|THAT THIS IS A TRUE COPY OF THIS BILL PASSED BY BOTH HOUSES OF THE|
|1|NATIONAL ASSEMBLY.|
|0.30000001192092896|hobay|
|1|MOHAMMED ATABA SANI-OMOLORI|
|1|CLERK TO THE NATIONAL ASSEMBLY|
|1|26t9|
|1|DAY OF MARCH, 2019|

#### PDF page14

| Line confidence | Raw line |
|---:|---|
|1|SHORT TITLE OF|
|1|TLONG TITLE OF THE BILL|
|1|THE BILL|
|1|Schedule to the National Minimum Wage Bill, 2019|
|1|SUMMARY|
|1|OF|
|1|THE DATE PASSED|
|1|CONTENTS OF THE BILL|
|1|BY THE SENATE|
|1|National Minimum|
|1|Wage, Bill, 2019.|
|1|An Act to repeal the Nationa|
|1|This Bill repeals the National|
|1|Laws of the Federation of Nigeria,|
|1|Minimum Wage Act Cap. N61,|
|1|Laws of the Federation of Nigeria,|
|1|tinimum Wage Act, 2019 to|
|1|2004|
|1|and|
|1|enact the National|
|1|Minimum Wage Act, 2019 to|
|1|wage for workers; and for related|
|1|prescribe a national minimum wage|
|1|matters.|
|1|and provide a legal framework for|
|1|seamless review of the national|
|1|minimum wage.|
|1|19"March, 2019|
|1|DATE PASSED BY|
|1|THE HOUSE OF|
|1|REPRESENTATIVES|
|1|29" January, 2019|
|1|I certify that this Bill has been carefully compared by me with the decision reached by the National Assembly and found by me to be true|
|1|and correct decision of the Houses and is in accordance with the provisions of the Acts Authentication Act Cap. A2, Laws of the|
|1|MOFAMMED ATABA SANI-OMOLORI|
|0.5|264 bay oo the ia,ional Assemuby|
|1|IASSENT|
|1|VIUHAMMADO BUHARI, GCFR|
|1|President of the Federal Republic of Nigeria|
|1|18 Day of Aarala, 2019|
|1|April|


## Task D — VAPP 2015 and FRSC 2007 sources

Nine source-specific download attempts across Tasks D/E were individually authorized in chat. All used direct HTTP streams into their own newly created empty folders before parsing, with a 25,000,000-byte cap; six PDFs were obtained and three attempts failed. No browser was used, no default download location was involved, and no file landed in or was moved from Downloads. Python used `-I` from `/private/tmp`; local Swift/Poppler tools also ran outside downloaded folders. No downloaded code was executed.

### VAPP candidates

| Candidate / exact source | Publisher / classification | Bytes; pages; text layer; words per page | Labels versus arrangement / assent / draft indicators |
|---|---|---|---|
| [Gazette candidate No.61](https://archive.gazettes.africa/archive/ng/2015/ng-government-gazette-dated-2015-05-25-no-61.pdf) | Gazettes.Africa, secondary archival host; hypothesised official-origin route based on a cited Gazette No.61 Vol.102, not established PDF contents. | Approved GET returned 404; no PDF. Size/pages/words unknown. HEAD had returned 403. | No arrangement, body or assent could be inspected; a 403 did not prove that this constructed URL existed. Failure record retained. |
| [ecoi/Refworld copy](https://www.ecoi.net/en/file/local/1053569/1930_1433836609_556d5eb14.pdf), via [ecoi record](https://www.ecoi.net/en/document/1053569.html) and [Refworld](https://www.refworld.org/legal/legislation/natlegbod/2015/105106) | ecoi.net republication of Refworld/UNHCR’s Nigerian-origin document; secondary. | 1,530,072 bytes; 15 pages; no native text layer; **0 words on every page**. | Own arrangement not found. Ends at body32 on PDF15. Strict raw Vision candidates30/32, not captured2/25; not missing-law conclusions. No assent page in this file. PDF2 says A Bill with empty commencement bracket. Refworld’s warning that the main attachment ends32 matches the observed endpoint. |
| [ACPF legal repository copy](https://clr.africanchildforum.org/Legislation%20Per%20Country/Nigeria/2019/nigeria_prohibitionofdomesticviolence_2015_en.pdf) | African Child Policy Forum, secondary legal repository. This is VAPP, not the excluded Child’s Rights material. | 6,053,595 bytes; 33 pages; no native text layer; **0 words on every page**. | Own arrangement not found. Endpoint48/citation is on PDF27; strict raw Vision candidates45/48, unlocated36–38. **PDF17 ends at35; PDF18 begins mid rights-related text without36–38 headings**. No missing wording supplied. PDF33 has I ASSENT and signature images; handwritten day appears25 with printed May2015. PDF2 still says A Bill / blank commencement. Reaching48 does not establish all body text is present. |

The complete raw Vision streams and strict candidate lists are retained for both scans. A body occurrence of “arrangements” on PDF14 is not an arrangement of sections. The ACPF assent image was inspected but not authenticated. The new copy with both its own arrangement and assent requested here was **not located**; no VAPP catalogue was made. The earlier FIDA copy was already known to lack an arrangement and was not downloaded again. The NAPTIP 2017 URL returned404 on HEAD. National Assembly/gazette/Refworld/WIPO searches did not yield a qualifying copy; that is “none located”, not “none exist”. A CSJ page offers a download, but direct HTML research returned406 and its linked file was not downloaded without a disclosed URL/size.

### FRSC routes

| Source | Publisher / classification | Size, pages, text layer, words/page | Labels / assent / limitation |
|---|---|---|---|
| [Checklist FRSC-hosted PDF](https://old.frsc.gov.ng/FRSCACT2007.pdf) | FRSC, official agency host. | HEAD and approved bounded GET timed out; no PDF retained. All PDF metrics unknown. Current [frsc.gov.ng route](https://frsc.gov.ng/FRSCACT2007.pdf) and [www route](https://www.frsc.gov.ng/FRSCACT2007.pdf) returned404 on HEAD; no unapproved alternate download. | Could not reconcile arrangement/body or inspect assent/draft indicators. Failure metadata retained. |
| [judy.legal checklist link](https://www.judy.legal/legislation/akn/ng/act/2007/22) | Secondary commercial legal publisher. | Public HTML preview, not a PDF download. PDF size/pages/words per page: not applicable/unknown. | Public site TOC lists1–31 and First/Second Schedules, but body preview exposes only section1 opening. Metadata says published/assented/commenced25May2007; this is not an inspected assent image or source-own PDF arrangement. No public full PDF link was obtained; no login, purchase or access bypass. |

No FRSC source was marked complete or usable. A website-generated TOC is kept distinct from the Act’s own printed arrangement and full body text.

## Task E — CAMA, Copyright and Nigeria Tax Act candidates

“Text layer” means native Poppler produces words; it does not mean those words are reliable. Full raw native text, every page’s exact word count, source metadata/hash, section-label candidates and the retrieval record are retained in each successful source folder. Candidate coverage below is a raw search result, not complete provision acceptance.

| Instrument / candidate and exact source | Publisher / classification | Size; PDF pages; native text | Arrangement/body label observations | Assent / edition observations |
|---|---|---|---|---|
| CAMA [ILO attachment](https://natlex.ilo.org/dyn/natlex2/natlex2/files/download/112593/NGA112593.pdf), [record112593](https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=112593) | ILO NATLEX, intergovernmental republication. | Approved GET403; no PDF, metrics unknown. CAC linked candidate had returned404. | Not tested. | No browser route was used after the direct failure. |
| CAMA [TheNigeriaLawyer copy](https://thenigerialawyer.com/wp-content/uploads/2020/08/CAMA-2020.pdf) | Secondary legal-news publisher; [linking article](https://thenigerialawyer.com/download-companies-allied-matters-act-2020/). | 4,945,077 bytes;606 pages; text layer yes. | Expected endpoint870; strict bare-label arrangement candidates867/870, missing191/550/765; body candidates870/870. ArrangementPDF1–43; body44–508. Counts do not cure wrong edition. | **Rejected as2020 source:** arrangement heading, opening and citation print2019; PDF44 says A Bill, empty commencement; no assent block located. Filename/article year2020 does not override document contents. |
| CAMA [Open Ownership gazette reproduction](https://oo.hacdn.io/media/documents/Nigeria_-_Companies_and_Allied_Matters_Act_2020.pdf) | Secondary archival/reference host reproducing Federal Government Printer material. | 1,269,127 bytes;528 pages; text layer yes, **defective PDF91**. Best retrieved2020-origin candidate, with defect retained. | Own arrangementPDF3–31:870/870 numeric candidates. BodyPDF33–440:867/870 strict numeric candidates, labels125–127 not captured. PDF91/printedA91 has **mirrored main text**, including backward native tokens `.521`, `.621`, `.721`; header/side notes remain normal. Independent detail Vision also fails to read it normally. No mirror/number reversal repair. | Cover GazetteNo124,10August2020,Vol107, “REFERENCE NOTE BOOK”; body commencement7August2020; citation2020. PDF528 printed I ASSENT, LS seal and date7August2020, typeset names; no wet-ink signature image observed. Gazette-style evidence, without provenance/authenticity certification. |
| [Copyright Act2022 — NCC](https://www.copyright.gov.ng/CopyrightAct/CopyrightAct2023FinalPublication1.pdf), linked from [NCC library](https://copyright.gov.ng/CopyrightAct/) | Nigerian Copyright Commission, official agency republication of gazette-origin text. | 738,936 bytes;68 pages; native text yes. | Own arrangementPDF3–6 and body7–64 each yield109/109 numeric candidates. Schedule/authentication follows. | Cover GazetteNo56,27March2023,Vol110,2023No8; body and typeset assent date17March2023. PDF68 I ASSENT / LS / president name and date; no wet-ink image. “Schedule to Copyright Bill2022” is authentication context, not by itself rejection as draft. |
| [Nigeria Tax Act2025 — NASS](https://nass.gov.ng/documents/download/11249), [official catalogue](https://nass.gov.ng/documents/magazine) | National Assembly, official legislature host; issuing Federal Government Printer gazette-style copy. | 598,389 bytes;215 pages; native text yes. | Own arrangementPDF3–9 and body11–129 each yield202/202 numeric candidates with dash-only headings accepted as raw candidates. `148—` atPDF91 and `154—` atPDF93 are retained; a stop-only search captures200/202. Schedules restart numbering after the body and were excluded. | Cover GazetteNo117,26June2025. PDF214 has I ASSENT, signature images and date26June2025. PDF11 commencement1January2026. Metadata title includes **“Edited1-1-2026”**; NASS upload is2026. No comparison with another2025 print or claim that the metadata identifies an amending Act. |

No catalogues were requested or created for these Task E laws. Open Ownership’s CAMA page91 prevents treating its native layer as fully reliable; the unmirrored-looking2019 text was not spliced into the2020 source. No missing source words or labels were supplied.

### Nigeria Tax Act2025 — repeal, amendment and commencement evidence

The source prints commencement **1st January,2026** at PDF11; assent26June2025 at PDF214. These are different events and are recorded separately. The enacted/signed year2025, commencement2026 and metadata “Edited1-1-2026” are all explicitly flagged; editorial metadata was not treated as proof of a further enactment.

Section195, PDF117/printedA501, lists the following11 enactments as repealed from commencement. Names/caps below follow this source; abbreviated titles were not expanded to a recalled alternative:

1. Capital Gains Tax Act, Cap.C1, LFN2004.
2. Casino Act, Cap.C3, LFN2004.
3. Companies Income Tax Act, Cap.C21, LFN2004.
4. Deep Offshore and Inland Basin Act, Cap.D3, LFN2004.
5. Industrial Development (Income Tax Relief) Act, Cap.I17, LFN2004.
6. Income Tax (Authorised Communications) Act, Cap.I4, LFN2004.
7. Personal Income Tax Act, Cap.P8, LFN2004.
8. Petroleum Profits Tax Act, Cap.P13, LFN2004.
9. Stamp Duties Act, Cap.S8, LFN2004.
10. Value Added Tax Act, Cap.V1, LFN2004.
11. Venture Capital (Incentives) Act, Cap.V2, LFN2004.

Section196, PDF118/printedA502, lists14 consequential amendment targets: Petroleum Industry; Nigeria Export Processing Zones; Oil and Gas Export Free Trade Zone; NITDA; Tertiary Education Trust Fund; NASENI; Customs/Excise Tariffs; National Lottery; Nigerian Minerals and Mining; Nigeria Start-up; Export Incentives; Federal Roads Maintenance Agency; Student Loans2023; and Cybercrime2015. The full raw page and deletion operations are retained in `repeal-amendment-evidence.json`.

**Direct flag for our existing-law list:** section196(14) says the Cybercrime (Prohibition, Prevention, Etc.) Act,No17,2015 is amended by deleting **section44(2)(a), section44(4), and the Second Schedule**. This is source evidence affecting a law examined in earlier rounds; no Cybercrimes source file was opened, edited or consolidated in this round. FERMA is a separate instrument from the FRSC Act requested here; they were not conflated.

Section197, PDF119, prints revocation of VAT (Modification) Order2021 and two Oil/Gas Tax Incentives Orders identified as S.I.No21,2024 and S.I.No1,2024; it also prints amendments deleting paragraph2 of Companies Income Tax (Significant Economic Presence) Order2020 and regulations60B,60C,61(1),(2),(4),62 of Petroleum (Drilling and Production) Regulations1969. Its mixed heading/operations are retained. Section198 contains savings; its paragraph(a) cites repeal/amendment section numbers197/198 although the headings here are195/196. That cross-reference glitch is flagged, not repaired. Section200 contains a fiscal-conflict provision; its interaction with other legislation was not adjudicated.

### Copyright cross-law flag

Section106(1), PDF60/printedA236, repeals the old Copyright Act,Cap.C28,LFN2004. Section106(2) explicitly prints repeal of **Criminal Code First Schedule sections491–493 and Penal Code sections426–427**. This matters to the retained historical Code material. The text of that page was visually inspected; no older-law source/catalogue was updated, no consolidated text was made, and present application/savings were not decided. The2022 short title coexists with2023 gazette/commencement/assent dates; all are retained.

### Native words per PDF page — exact raw counts

In each array, position1 is PDF1, position2 PDF2, and so on. Counts use whitespace-separated Poppler output; they include headings/footers, can include extraction damage and are not OCR/legal-quality scores. Zero means no native words on that page, not no visible content. The same arrays and full text are in each `native-pages.json`.

#### round4-vapp-2015-ecoi

15 pages; total 0 native words; min/median/max 0/0/0.

```json
[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

#### round4-vapp-2015-acpf

33 pages; total 0 native words; min/median/max 0/0/0.

```json
[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

#### round4-cama-2020-tnl

606 pages; total 204,815 native words; min/median/max 0/344/555.

```json
[115, 146, 163, 167, 164, 161, 176, 154, 142, 151, 162, 112, 125, 138, 185, 174, 172, 192, 184, 157, 141, 145, 174, 145, 173, 157, 194, 165, 183, 178, 197, 174, 191, 153, 180, 163, 148, 146, 175, 159, 122, 137, 122, 256, 187, 282, 269, 326, 250, 348, 339, 356, 308, 411, 424, 440, 298, 299, 487, 338, 221, 281, 287, 330, 306, 434, 408, 487, 448, 398, 379, 445, 211, 332, 347, 292, 297, 299, 335, 222, 229, 326, 281, 274, 287, 267, 310, 234, 291, 352, 347, 344, 387, 415, 334, 376, 442, 377, 428, 500, 414, 399, 360, 397, 498, 448, 396, 442, 431, 370, 377, 404, 357, 364, 344, 353, 371, 368, 385, 440, 341, 362, 374, 401, 488, 543, 466, 523, 478, 521, 363, 366, 501, 430, 454, 490, 315, 386, 327, 372, 340, 343, 420, 422, 418, 427, 399, 373, 504, 344, 375, 336, 352, 418, 417, 341, 455, 358, 489, 352, 521, 382, 315, 366, 516, 440, 370, 316, 387, 336, 483, 455, 439, 412, 411, 521, 388, 524, 538, 459, 493, 404, 392, 444, 372, 390, 313, 465, 430, 344, 448, 475, 331, 453, 402, 434, 430, 427, 396, 394, 405, 422, 407, 382, 407, 334, 358, 415, 412, 379, 349, 423, 416, 342, 252, 290, 274, 269, 261, 266, 278, 385, 367, 274, 332, 307, 337, 311, 368, 291, 311, 330, 430, 367, 460, 366, 317, 523, 399, 443, 419, 375, 303, 375, 286, 394, 396, 336, 374, 294, 331, 485, 388, 393, 396, 418, 480, 267, 294, 368, 320, 407, 294, 359, 352, 353, 355, 279, 350, 407, 332, 404, 382, 436, 383, 542, 431, 402, 466, 486, 368, 330, 322, 267, 310, 325, 296, 327, 358, 255, 227, 297, 325, 262, 325, 297, 276, 262, 313, 301, 266, 316, 255, 303, 229, 291, 242, 229, 343, 241, 223, 251, 319, 323, 330, 346, 276, 208, 215, 283, 267, 261, 290, 292, 292, 273, 291, 259, 350, 285, 257, 233, 346, 311, 143, 244, 257, 267, 284, 448, 490, 432, 355, 452, 329, 426, 315, 415, 294, 276, 375, 501, 432, 414, 355, 351, 388, 335, 447, 442, 472, 435, 484, 499, 452, 485, 468, 417, 363, 457, 441, 522, 400, 448, 379, 319, 489, 524, 373, 459, 528, 452, 341, 330, 388, 309, 390, 442, 527, 362, 289, 490, 338, 268, 326, 441, 494, 373, 478, 424, 426, 343, 428, 395, 329, 428, 413, 407, 442, 464, 457, 330, 318, 409, 307, 365, 380, 313, 469, 422, 409, 423, 439, 407, 239, 247, 268, 213, 252, 357, 365, 267, 327, 457, 402, 344, 555, 390, 503, 346, 398, 355, 356, 261, 328, 323, 371, 344, 326, 404, 455, 397, 358, 378, 361, 308, 392, 513, 422, 351, 435, 344, 255, 196, 478, 344, 466, 320, 259, 384, 411, 435, 376, 416, 387, 277, 307, 349, 427, 331, 299, 262, 312, 376, 348, 303, 285, 348, 303, 321, 272, 307, 305, 292, 362, 283, 349, 416, 419, 301, 273, 380, 365, 306, 343, 322, 386, 120, 166, 374, 328, 368, 171, 189, 107, 155, 203, 431, 214, 238, 243, 361, 401, 353, 269, 277, 351, 351, 380, 352, 289, 293, 290, 314, 258, 322, 256, 263, 313, 310, 317, 333, 308, 394, 316, 409, 239, 328, 299, 252, 404, 368, 466, 282, 364, 376, 404, 325, 281, 360, 290, 379, 4, 317, 361, 316, 280, 309, 347, 260, 336, 285, 294, 268, 102, 367, 297, 338, 329, 326, 8, 0, 324, 329, 226, 249, 355, 291, 273, 201, 228, 352, 227, 221, 263, 348, 315, 142, 312, 164, 140, 162, 148, 329, 305, 61]
```

#### round4-cama-2020-openownership

528 pages; total 211,282 native words; min/median/max 10/417/699.

```json
[105, 10, 193, 247, 266, 253, 246, 205, 269, 232, 219, 230, 252, 292, 262, 268, 256, 242, 274, 245, 237, 286, 277, 280, 258, 243, 230, 238, 240, 211, 172, 11, 335, 387, 382, 364, 376, 420, 393, 399, 465, 390, 436, 422, 376, 448, 342, 397, 386, 422, 371, 500, 483, 473, 475, 465, 449, 337, 401, 391, 399, 343, 386, 378, 423, 346, 356, 338, 395, 348, 374, 457, 409, 429, 406, 399, 479, 478, 487, 512, 432, 422, 455, 480, 509, 489, 409, 436, 423, 412, 699, 427, 394, 463, 448, 440, 432, 406, 469, 445, 414, 480, 479, 527, 454, 533, 497, 526, 440, 437, 481, 463, 491, 475, 424, 465, 466, 441, 383, 433, 458, 439, 466, 460, 458, 497, 430, 437, 468, 465, 428, 443, 466, 483, 493, 477, 440, 423, 404, 527, 471, 452, 426, 440, 429, 474, 491, 421, 444, 492, 472, 503, 513, 484, 504, 442, 482, 483, 435, 395, 494, 432, 408, 477, 483, 460, 479, 445, 477, 447, 468, 480, 476, 496, 453, 474, 470, 425, 432, 456, 463, 420, 448, 464, 403, 343, 331, 368, 356, 360, 448, 436, 330, 350, 399, 411, 435, 419, 453, 456, 448, 483, 474, 418, 482, 478, 480, 487, 399, 428, 407, 427, 443, 418, 405, 442, 425, 468, 445, 444, 484, 436, 386, 391, 422, 445, 369, 417, 404, 442, 396, 405, 457, 453, 463, 433, 456, 490, 511, 416, 456, 496, 434, 423, 417, 379, 390, 374, 402, 370, 331, 377, 423, 303, 378, 359, 371, 381, 355, 433, 341, 383, 333, 360, 380, 371, 330, 306, 307, 353, 421, 397, 336, 350, 372, 324, 353, 347, 392, 338, 347, 407, 392, 383, 358, 404, 244, 337, 327, 404, 507, 482, 447, 484, 447, 443, 421, 385, 410, 379, 495, 449, 453, 477, 419, 486, 483, 463, 440, 466, 463, 485, 494, 499, 498, 486, 470, 381, 454, 521, 498, 473, 413, 435, 526, 496, 427, 476, 472, 489, 445, 414, 413, 494, 449, 502, 432, 439, 492, 401, 461, 501, 462, 492, 493, 406, 489, 445, 481, 452, 473, 484, 436, 509, 445, 418, 482, 376, 406, 461, 429, 504, 445, 464, 484, 448, 449, 331, 356, 346, 420, 408, 337, 469, 482, 476, 475, 470, 488, 452, 452, 385, 399, 334, 359, 416, 433, 405, 445, 459, 417, 400, 434, 415, 457, 541, 472, 425, 394, 373, 347, 381, 481, 387, 422, 414, 459, 447, 455, 402, 459, 390, 361, 399, 434, 367, 363, 400, 420, 431, 374, 375, 360, 367, 346, 421, 365, 410, 390, 369, 417, 463, 365, 395, 409, 375, 399, 385, 362, 296, 229, 417, 400, 319, 193, 178, 190, 180, 453, 217, 227, 239, 301, 374, 422, 310, 393, 396, 412, 390, 404, 362, 373, 419, 339, 386, 313, 361, 416, 361, 392, 413, 371, 416, 276, 373, 340, 189, 410, 457, 468, 420, 425, 424, 428, 358, 408, 389, 215, 401, 434, 415, 441, 412, 153, 412, 329, 373, 221, 376, 377, 402, 347, 211, 343, 341, 235, 296, 319, 256, 361, 283, 165, 360, 240, 229, 272, 361, 366, 112, 343, 152, 150, 173, 157, 378, 382, 262]
```

#### round4-copyright-2022-ncc

68 pages; total 25,921 native words; min/median/max 11/413/499.

```json
[115, 11, 223, 228, 229, 115, 307, 385, 439, 446, 446, 399, 426, 432, 426, 439, 438, 413, 373, 472, 383, 412, 421, 469, 480, 456, 407, 396, 418, 499, 421, 463, 448, 383, 400, 401, 439, 489, 372, 469, 434, 433, 384, 397, 423, 425, 413, 415, 368, 338, 440, 427, 431, 400, 412, 395, 373, 451, 447, 422, 413, 406, 367, 120, 413, 317, 43, 226]
```

#### round4-nigeria-tax-2025-nass

215 pages; total 73,304 native words; min/median/max 9/401/503.

```json
[113, 9, 161, 238, 242, 227, 209, 230, 118, 9, 333, 374, 412, 412, 441, 433, 419, 414, 485, 404, 438, 429, 408, 441, 424, 418, 393, 502, 450, 431, 350, 427, 428, 404, 466, 503, 421, 473, 479, 457, 445, 471, 439, 353, 346, 458, 420, 413, 442, 375, 467, 444, 444, 495, 478, 474, 415, 400, 411, 491, 478, 421, 391, 458, 475, 423, 395, 463, 464, 495, 431, 443, 450, 386, 393, 404, 435, 355, 426, 423, 440, 449, 410, 470, 379, 427, 494, 423, 338, 430, 462, 357, 445, 412, 356, 461, 399, 386, 405, 415, 376, 391, 444, 421, 397, 409, 447, 390, 329, 338, 385, 401, 392, 422, 435, 430, 380, 334, 446, 407, 398, 392, 361, 403, 401, 395, 378, 393, 287, 393, 368, 340, 406, 376, 445, 446, 423, 444, 313, 397, 409, 417, 462, 430, 379, 427, 421, 434, 412, 460, 426, 231, 420, 112, 260, 87, 393, 446, 501, 434, 440, 107, 429, 54, 334, 381, 407, 340, 296, 210, 162, 27, 157, 124, 158, 135, 122, 105, 132, 57, 102, 93, 80, 103, 115, 116, 133, 75, 102, 107, 90, 118, 116, 141, 117, 139, 104, 135, 80, 120, 130, 97, 114, 274, 449, 455, 463, 391, 139, 316, 135, 84, 263, 255, 9]
```

## Scope limits and checks

No database, Docker/container/compose, migrations, `.env`, commits or branch changes were used. No pre-existing repository file was edited. NDPA, Child’s Rights, Land Use, Labour and Employees’ Compensation source/catalogue material was neither processed nor modified. The catalogue contract was reused from prior round knowledge; excluded files were not reopened. Only the two expressly conditional new catalogue files were created under `backend/app/`; the Criminal Code catalogue was not created.

Read-only checks: existing `catalogue_titles` loads168 FCCPA titles/18Parts and18 wage titles/0Parts/0Chapters; comparison tables contain572 Code and168 FCCPA reference rows; wage evidence contains14 raw OCR pages and18 arrangement titles. The685-file baseline of this lane’s retained relevant evidence, source files, checklist and reader remains hash-identical. This is not a whole shared-checkout audit or a reconciliation of another agent’s work. No existing source file was removed, rewritten, deduplicated or renumbered. New file byte counts/hashes are recorded in the inventory.

Not established: legal currency or complete amendment history; authenticity of gazettes, copies, handwriting or signatures; issuing-authority endorsement of every hosted byte; full subsection/wording fidelity; the correct reading among OCR alternatives; present federal/state Code applicability; a VAPP source with both own arrangement and assent; an accessible full FRSC PDF; complete reliable CAMA body text given the mirrored page; current-law or ingestion acceptance. Candidate coverage and a title catalogue are evidence, not these determinations. No text was reconstructed from an expected sequence, no date alternative was chosen, and no source is marked verified or approved.

## Every repository file created

Repository root: `/Users/amosgodwin/WebstormProjects/law-padi`. All paths below are relative to that root. Processing scripts, module-cache files and scratch comparison tables under `/private/tmp/law_padi_round4/` are temporary working files outside the repository deliverable; retained raw outputs and relevant previews are listed here. The inventory includes hashes for every listed repository output except its own recursive self-hash.

- `backend/app/legal/data/federal-competition-and-consumer-protection-act-2018-section-titles.json`
- `backend/app/legal/data/national-minimum-wage-act-2019-section-titles.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-ilo/download.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/Nigeria_-_Companies_and_Allied_Matters_Act_2020.pdf`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/download.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/gap-091.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/native-pages.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/page-001.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/page-003.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/page-033.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/page-528.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/section-label-audit.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/source-defects-and-assent.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-openownership/vision-gap-detail-raw.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/CAMA-2020.pdf`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/download.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/native-pages.json`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/page-001.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/page-002.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/page-606.png`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round4-cama-2020-tnl/section-label-audit.json`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/CopyrightAct2023FinalPublication1.pdf`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/cross-law-and-assent-evidence.json`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/download.json`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/native-pages.json`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/page-001.png`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/page-007.png`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/page-060.png`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/page-068.png`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round4-copyright-2022-ncc/section-label-audit.json`
- `backend/storage/statute-review/source-tests/round4-created-files.json`
- `backend/storage/statute-review/source-tests/round4-criminal-code/division-page-ranges.json`
- `backend/storage/statute-review/source-tests/round4-criminal-code/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-001.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-031.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-032.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-034.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-207.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-208.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-209.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-210.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/page-214.png`
- `backend/storage/statute-review/source-tests/round4-criminal-code/scope-and-label-evidence.json`
- `backend/storage/statute-review/source-tests/round4-criminal-code/subsidiary-instrument-ranges.json`
- `backend/storage/statute-review/source-tests/round4-fccpa/label-evidence.json`
- `backend/storage/statute-review/source-tests/round4-fccpa/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-002.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-003.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-004.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-005.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-006.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-007.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-024.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/page-025.png`
- `backend/storage/statute-review/source-tests/round4-fccpa/raw-prefix-addendum.json`
- `backend/storage/statute-review/source-tests/round4-fccpa/vision-arrangement-detail-raw.json`
- `backend/storage/statute-review/source-tests/round4-fccpa/vision-raw.json`
- `backend/storage/statute-review/source-tests/round4-frsc-2007-official/download.json`
- `backend/storage/statute-review/source-tests/round4-frsc-judy-link-observations.json`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/arrangement-body-and-schedule-evidence.json`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/gap-007.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/ocr-lines-raw.md`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/page-002.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/page-003.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/page-006.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/page-007.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/page-013.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/page-014.png`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/vision-detail-raw.json`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/vision-raw.json`
- `backend/storage/statute-review/source-tests/round4-minimum-wage-2019/visual-label-addendum.json`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/Nigeria-Tax-Act-2025-NASS.pdf`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/download.json`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/native-pages.json`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/page-001.png`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/page-011.png`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/page-117.png`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/page-118.png`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/page-119.png`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/page-214.png`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/repeal-amendment-evidence.json`
- `backend/storage/statute-review/source-tests/round4-nigeria-tax-2025-nass/section-label-audit.json`
- `backend/storage/statute-review/source-tests/round4-research-evidence.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/detail-027.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/detail-032.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/detail-033.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/download.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/gap-018.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/native-pages.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/nigeria_prohibitionofdomesticviolence_2015_en.pdf`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/page-001.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/page-002.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/page-033.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/section-label-audit.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/source-gap-and-assent.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-acpf/vision-raw.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/1930_1433836609_556d5eb14.pdf`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/download.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/native-layout-raw.txt`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/native-pages.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/page-001.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/page-002.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/page-015.png`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/pdfinfo.txt`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/section-label-audit.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-ecoi/vision-raw.json`
- `backend/storage/statute-review/source-tests/round4-vapp-2015-gazette/download.json`
- `docs/ocr-and-source-tests-round4-2026-11-03.md`
