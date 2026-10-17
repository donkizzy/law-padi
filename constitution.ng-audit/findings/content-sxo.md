# Content and search experience readiness — constitution.ng

Date: 16 October 2026. Scope: read-only source review of the current checkout, applying `seo-content` and `seo-sxo`. This is **launch-readiness evidence**, not an observation of a publicly served website, a ranking audit, legal verification, or a live SEO/SXO score. Parent audit found `constitution.ng` unavailable (NXDOMAIN), but subsequently confirmed HTTP 200 from the separate deployment hostname `https://constitition-ng.amosgodwin500.workers.dev`. Parent is handling live rendering; this subreview makes source-level findings only. `docs/deployment-status.md:34`–`41` describes workers.dev and preview URLs as disabled; that statement is stale relative to the observed HTTP 200. `PROJECT_CONTEXT.md` was read before review; it identifies the corpus as historical/source wording, not certified current consolidated law.

## Final live verification superseding source-only uncertainty

The parent subsequently verified the live `/amendments` route renders the fixture cards/static diff; `evidence/amendments-rendered.html` and the amendment screenshot substantiate H1. It also verified the capability endpoint reports explanations enabled (see `evidence/chat-capabilities.json`), so H3 is a **source regression scenario, not an observed current promise/capability mismatch** and is not counted as a current High issue in the unified report. A real browser eventually loaded Section 37 wording and edition notice; its primary heading was H2, with no H1 and no canonical. Source statements below describe the initial subreview and should be read with this update.

## Assessment

The application already serves three useful intentions in source: ask an everyday question, find an exact provision, and read the original wording with provenance. Those are a better product fit than forcing all informational queries onto the marketing landing page. The highest content risks before launch are reachable preview amendment data, an incomplete public explanation of responsibility/review, and promises of generated answers that remain unconditional when generation is unavailable. Discovery of reading pages is also weak because chapter children only load on clicks.

No numeric content, E-E-A-T or SXO score is assigned: no public rendering, Google result sample, Search Console, live output review or keyword-volume evidence was available. In particular, no claim is made about SERP consensus, ranking loss, legal correctness, mobile usability or Google penalties.

## High-priority findings

### H1. A registered amendment route renders preview content as legal-status information

**Observation/evidence:** `frontend/src/routes/_layout/amendments.tsx:5` registers `/amendments` directly without a route guard and renders `AmendmentsView`. `frontend/src/components/LawPadi/AmendmentsView.tsx:14` imports a hard-coded array; lines 50–54 promise enacted/historical/proposed separation, and lines 84–100 show a fixed effective-date statement and text comparison. `frontend/src/lib/law-padi-data.ts:367`–`431` supplies preview “current” alteration entries and generic proposal entries. This is an active import chain, not merely an unused design fixture. `frontend/src/components/Sidebar/AppSidebar.tsx:32`–`33` hides its sidebar link, but does not disable direct navigation. Whether this is currently exposed through any unpublished environment was not tested.

**Why it matters:** An informational legal page needs verifiable identities and provenance for each status claim. A hidden navigation item cannot establish that boundary. This is a trust/launch risk; no assertion is made that any named Act is inaccurate.

**Action:** Keep this route outside the public release until it reads reviewed instrument/proposal records, source links and last-verified status. Return a deliberate unavailable/not-published result in the public app while records remain fixtures. Do not solve trust by adding schema to preview claims.

**Dependency:** Decide amendment publication scope before generating sitemaps or public amendment links.

**Failure check:** A clean guest browser can still load any hard-coded preview legal-status card or fixed comparison at `/amendments`.

**Leading indicator:** Count public legal-status entries lacking a reviewed source record; target zero.

### H2. Public content explains “what” and “why,” but gives limited evidence of “who” and “how”

**Observation/evidence:** Landing FAQs disclose independence and no legal advice (`frontend/src/components/Landing/LandingPage.tsx:46`–`78`); the footer repeats independence (`:938`–`955`). Its footer routes include no About, editorial policy, source methodology or corrections page. Active routes likewise have no corresponding page. The process claim at `:68`–`69` explains retrieval briefly, but not editorial responsibility or review scope. `frontend/src/components/LawPadi/PrivacyNotice.tsx:154`–`165` shows the contact email only if a build variable is present; deployment configuration was not inspected for its value. Provision provenance is available in an initially closed Source panel (`frontend/src/components/LawPadi/ProvisionDetail.tsx:20`, `:49`–`64`; `SourcePanel.tsx:119`–`148`).

**Why it matters:** People deciding whether to rely on a constitutional explanation need to know the operator, exact corpus edition, review responsibility, amendment scope and how to report an error. This is especially relevant to the site's own rights-focused examples. Credentials must be real; an About page alone does not confer authority.

**Action:** Publish one concise linked About/sources-and-review page naming the responsible operator, accurately describing any human legal review, how generated explanations are checked, source provenance, edition limitations, update cadence and a working corrections contact. Put a short source/edition line beside the main reading content rather than relying only on opening a panel. Preserve the existing fuller source panel.

**Dependency:** Confirm responsible parties and actual review practice before writing credentials or “reviewed by” claims. This can follow the decision to publish historical wording and need not wait for current-law consolidation.

**Failure check:** A guest cannot identify the operator, corpus scope or corrections channel within two links from a reading page; metadata claims human review that did not occur.

**Leading indicator:** Percentage of public legal reading pages linking to source/review policy and exposing edition/source identity; target 100%.

### H3. Landing promises do not respond to capability availability

**Observation/evidence:** The static hero promises a plain-English explanation (`LandingPage.tsx:461`–`464`), submit says “Get my answer” (`:395`–`401`), and how-it-works says “about ten seconds” (`:755`). Landing submission navigates to a query URL (`:353`). In contrast, `frontend/src/components/LawPadi/LawPadiHome.tsx:37`–`39` and `:75`–`89` choose search when conversations are disabled, and `frontend/src/components/LawPadi/ProvisionView.tsx:203`–`219` conditionally exposes explanation actions. These establish a potential promise/capability mismatch, not the current public flag value.

**Why it matters:** A rights question visitor who expects an explanation but receives retrieval results may not recognize that finding source wording succeeded.

**Action:** Match acquisition copy and primary CTA to the release's enabled service, or state plainly that finding sections is always available and explanations are available when enabled. Validate timing claims under the actual production path. Retain the clear Ask/Find task split.

**Dependency:** Decide launch generation flags and verify the allowed production answer path before advertising it.

**Failure check:** With explanations off, a new guest still receives unconditional explanation and timing promises, then lands on a different task without explanation.

**Leading indicator:** Landing-submit-to-successful-result rate, segmented by enabled/disabled explanations and request failure reason; avoid treating a successful retrieval as a successful explanation.

## Medium-priority findings

### M1. Provision pages share a generic search title and lack a page-level H1

**Evidence:** `frontend/src/routes/_layout/constitution.$sectionId.tsx:9`–`14` returns the same “Constitution section” title for every path. The page component (`ProvisionDetail.tsx:22`–`66`) supplies no H1; its primary provision title is H2 (`ProvisionView.tsx:152`–`159`). Search text identity is available via `provisionTitle`, citation and edition, so no generated summary is required.

**Action:** Once the technical rendering/indexing strategy is selected, emit a stable specific title, main H1 and short accurate description from the loaded provision/citation/edition. Example pattern: “Section [number]: [source heading] — 2004 edition | constitution.ng”. Treat heading fixes as semantic clarity, not a stand-alone ranking guarantee.

**Dependency:** Public document/canonical URL policy and server/pre-render strategy. Do not edit generated client or route tree files.

**Failure check:** Two different section URLs still have indistinguishable rendered titles or a missing main heading after loading; a historical text title implies certified current law.

**Leading indicator:** Duplicate title count and missing primary heading count across the released provision URL set.

### M2. A chapter click is required before section links exist

**Evidence:** `frontend/src/components/LawPadi/BrowseConstitution.tsx:82` initializes collapsed state, `:110`–`112` mounts children only after expansion, and `:124` fetches them on mounting. The eventual section links are real links (`:87`–`95`), but they are absent before those actions. Source-to-related navigation uses a button that launches semantic search (`ProvisionView.tsx:231`–`237`; `ProvisionDetail.tsx:53`–`54`).

**Action:** Give published chapters and sections a crawlable reading hierarchy available without expansion actions; provide reviewed related-provision anchors where useful. Preserve progressive disclosure for the interface. Do not label all constitutional text “thin content” or pad short sections to arbitrary word counts.

**Dependency:** Approved public corpus URL list and rendering plan; sitemap coverage complements, rather than replaces, internal links.

**Failure check:** A link-only crawl of the rendered browse page cannot discover released section pages without simulating button clicks.

**Leading indicator:** Orphaned released-section count and proportion reachable in a bounded internal link crawl.

### M3. Original benchmark claims lack a public method/date link

**Evidence:** `LandingPage.tsx:784`–`813` states “54 of 55” everyday questions put the right section first “in our latest test,” while “here is where it stands today” has no specific benchmark date/version or method link in the section. This appears to be retrieval testing, not evidence of generated-answer legal correctness.

**Action:** Link a brief dated benchmark methodology with corpus version, sample selection and the precise measured outcome. Explicitly distinguish retrieval hit rate from explanation accuracy. Keep numbers synchronized with the published evidence rather than auto-changing dates.

**Dependency:** Confirm which retained benchmark artifact substantiates the displayed numerator/denominator.

**Failure check:** A visitor reasonably reads the metric as a 98% answer-correctness claim, or the public numerator cannot be reproduced from the named test set.

**Leading indicator:** Number of numeric quality claims without a dated, reproducible evidence link; target zero.

## Strengths to preserve

- Guest access, clear free/no-account language and both everyday/Pidgin-style questions and exact citations are already represented (`LandingPage.tsx:37`–`78`). No claim of multilingual generated answers beyond English is needed.
- Provision identity and release survive links, copy and saved actions (`ProvisionView.tsx:40`–`46`, `:68`–`85`; `frontend/src/lib/legal-provisions.ts:3`–`4`, `:68`–`72`).
- Historical edition notices are prominent in provision reading and copied text (`ProvisionView.tsx:166`–`169`; `legal-provisions.ts:26`–`41`, `:72`).
- Original wording is separated from explanations, and reading display joins PDF wraps while retaining structured breaks (`ProvisionView.tsx:161`–`165`; `legal-provisions.ts:44`–`57`).
- Source panel supplies authority, document title, page locations and an original-PDF anchor (`SourcePanel.tsx:119`–`148`).
- Answer copy includes cited sources and a no-legal-advice notice; the chat warns explanations can miss details (`ChatHome.tsx:100`–`122`, `:1389`–`1392`).

## Search experience hypothesis, requiring live validation

The skill taxonomy classifies `/welcome` as a **Landing Page** and the query interface as a **Tool**. Constitution reading pages are primary legal/reference documents, outside that taxonomy's narrow commercial types; classifying them as blog posts would be misleading. Persona needs below derive from product context and actual interface, **not observed SERPs**:

| Visitor goal | Existing fit | Gap to validate |
|---|---|---|
| Understand an everyday rights question | Plain-English promise, guest question form, citations | Does the enabled service answer or clearly disclose retrieval-only availability? |
| Find a known section | Exact citation search, reading view, copy citation | Can the section itself be discovered through public search with a descriptive title? |
| Study or quote the text | Original wording, hierarchy, pinned release, PDF link | Can readers immediately identify source edition and amendment limits? |
| Check current consolidated wording or an alteration | Historical caveats, hidden amendment navigation | Do acquisition copy and every reachable route avoid unsupported current-law expectations? |

After the intended domain is public, sample results for “Nigeria Constitution”, specific section references and the site's everyday questions; record result type and edition currency rather than inventing search volume or consensus. Prioritize publication truth and discoverable reference pages before manufacturing generic blog content. Validate both the successful experience and disabled-generation experience in a clean guest session. No wireframe or score is justified by the present evidence.
