# Technical, structured-data and sitemap readiness — constitution.ng

Audit date: 16 October 2026 (Africa/Lagos). Scope: read-only repository review plus bounded public HTTP checks on the existing Workers hostname. No Search Console coverage, Core Web Vitals or rich-result eligibility is inferred. No live score is assigned.

The parent audit verified DNS failure for constitution.ng (Google DNS status 3 / NXDOMAIN). The existing hostname `https://constitition-ng.amosgodwin500.workers.dev` is nevertheless publicly reachable; note the spelling `constitition`. Repository documentation says public publication is pending (`docs/deployment-status.md:58–65`), while tracked workers.dev/preview settings are false (`deployment/cloudflare/wrangler.json:5–6`). Those files do not describe the current observable Workers exposure. No routing or service was enabled by this audit. `deployment/cloudflare/prepare.py:1–5` ties publication to AI evaluation and human review; reconcile observed exposure with the operator's intended launch state.

### Live evidence summary

At 14:33 UTC, seven document/special-file probes on the Workers hostname all returned HTTP 200 `text/html`, exactly 3,670 bytes and identical SHA-256 `7d03863adba826f4965b1a384926da1097062625c9afd1950f5c04b32aaf3639`: `/welcome`, `/robots.txt`, `/sitemap.xml`, `/sitemap_index.xml`, `/seo-audit-does-not-exist-20261016`, `/constitution/constitution-1999.chapter4.section37`, and `/constitution/seo-audit-does-not-exist`. The Section 37 API returned 200 JSON containing the historical/source LFN 2004 edition. Individual headers/bodies and hashes are retained in `constitution.ng-audit/evidence/tech-live-*` and `tech-live-responses.json`.

Parent-provided rendered evidence (`home-rendered.html`, `home-jsonld.json`) verifies actual landing text, FAQPage JSON-LD and duplicate metadata after JavaScript execution. The served raw HTML is an empty app shell. Production uses a different built bundle from the current local artifact, so source findings are compared with live evidence, not assumed to be an exact deployed commit match.

## Findings and sequence

### T1 — High, before launch: primary public content is absent from initial HTML

- Evidence: `frontend/index.html:24–26` contains an empty `#root` and a module script. The existing compiled artifact `backend/app/frontend/index.html:1` is only 3,752 bytes and retains that shell. `frontend/src/main.tsx:94–104` starts React after session initialization; route metadata is emitted by React's `HeadContent` (`frontend/src/routes/__root.tsx:10–14`). Legal wording is loaded by a browser query (`frontend/src/hooks/useLegalCorpus.ts:41–54`) and displayed only after it resolves (`frontend/src/components/LawPadi/ProvisionDetail.tsx:35–56`). The build uses Vite without a prerender/SSR step (`frontend/vite.config.ts:8–25`; `frontend/package.json:7–10`).
- Live corroboration: `/welcome` and Section 37 return the same 3,670-byte empty-root shell, while parent-rendered `/welcome` contains the full landing content. No legal wording is present in the raw provision document.
- First principle: the initial response should carry public legal wording, citation, edition caveat and page identity. Google can render JavaScript, so CSR alone is not a finding of non-indexability; it introduces rendering/API dependencies and excludes readers that do not execute JavaScript.
- Recommendation: prerender or server-render the welcome page, browse hubs and approved public provision URLs, with matching client hydration and metadata. Keep release identity and historical/current status intact. Architecture selection requires discussion under repository guidance; this audit does not prescribe a framework migration.
- Dependency: agree the intended indexable URL/edition policy (T3), then implement public rendering before sitemap rollout.
- Failure check: fetch representative HTML with JavaScript disabled and confirm that the exact section, citation, edition disclosure, title, canonical and working internal links are present; compare rendered text for parity. The change has failed if any of those still requires a session/API call after load.
- Leading indicator: percentage of public URLs whose initial HTML includes their unique provision text and citation; initial target 100% of intended indexable provision pages.

### T2 — High, before launch: browse discovery depends on clicking collapsed buttons

- Evidence: `frontend/src/components/LawPadi/BrowseConstitution.tsx:82` initializes each structural node collapsed. Structural controls are buttons (`:98–109`); child queries and links are mounted only after expansion (`:110–112`, `:124–146`). Leaf nodes correctly use router links (`:87–95`), but many of those links do not exist until a chapter/part is clicked.
- First principle: each public section should be discoverable from links available without user interactions. A crawler should not have to expand a navigation tree to discover the corpus.
- Recommendation: provide static chapter/part hubs with ordinary `<a href>` links to sections in the initial HTML. The interactive tree can continue as an interface feature. Link headings, important rights and edition overviews from relevant hubs. Avoid relying on a sitemap as the only discovery path.
- Dependency: T1 public rendering plus the URL policy in T3.
- Failure check: crawl from the public landing page without clicks or scripted expansion; compare discovered section URLs with the approved release inventory. Any intended section absent from crawl discovery is a failure.
- Leading indicator: proportion of approved section pages reachable through ordinary hyperlinks and maximum hub-to-section click depth.

### T3 — High, before launch: release URL canonicalization and distinct provision metadata are missing

- Evidence: `frontend/src/routes/_layout/constitution.$sectionId.tsx:7` supports optional `release`, but `:9–15` gives every provision the same title, "Constitution section - constitution.ng". No canonical declarations were found in `frontend/src`, `frontend/index.html` or the Worker. Shared provision links intentionally include `?release=...` (`frontend/src/lib/legal-provisions.ts:3–4`; `frontend/src/components/LawPadi/BrowseConstitution.tsx:87–90`); the same path without `release` requests the active edition (`frontend/src/hooks/useLegalCorpus.ts:41–49`).
- First principle: immutable historical editions and a changing default version require explicit, consistent page identity. Parameters are not inherently bad URLs, and different legal versions must not be collapsed just because their path is shared.
- Recommendation: choose which editions are indexable, set truthful self-canonicals on distinct indexable editions, and canonicalize only genuinely equivalent duplicates. Emit citation, subject and edition in unique titles/descriptions, for example "Section 37: private and family life | 2004 edition | constitution.ng" when that is the served edition. Never imply the historical source is current law. Align canonical tags, internal links, redirects and sitemap entries. Do not canonicalize all historical wording to a current version by default.
- Dependency: explicit corpus/edition publication policy before T1/T2/T5 implementation.
- Failure check: compare no-release, active-release and historical-release requests; their visible content and canonical targets must match the agreed policy. No different legal text may be labeled as an equivalent duplicate. Inspect Google's selected canonical after launch when Search Console is available.
- Leading indicator: 100% unique public provision titles; zero conflicting or nonexistent canonical targets; number of Google-selected canonical mismatches.

### T4 — High, measured on Workers: SPA fallback hides missing pages behind success responses

- Evidence: Cloudflare assets use `not_found_handling: "single-page-application"` (`deployment/cloudflare/wrangler.json:7–11`); the Worker delegates all non-API paths to assets (`deployment/cloudflare/worker.ts:54–55`). Unknown client routes render a visual 404 (`frontend/src/routes/__root.tsx:16`; `frontend/src/components/Common/NotFound.tsx:10–20`). Missing provision/API results render "Provision unavailable" (`frontend/src/components/LawPadi/ProvisionDetail.tsx:35–47`) and do not control the document HTTP status. Live HTTP checks confirmed that a random nonexistent page and nonexistent provision document both return 200 with exactly the same shell as the valid section. This establishes the HTTP problem; Google Search Console's soft-404 classification was not measured.
- First principle: a nonexistent document should not look like a successful public content page to a crawler.
- Recommendation: route public SEO documents through a layer that returns a real 404/410 for nonexistent pages and provisions, and suitable temporary errors for unavailable upstreams. Preserve valid SPA deep links. Treat `/robots.txt` and sitemap endpoints explicitly so unknown special files never fall back to HTML.
- Dependency: public route inventory plus T1 rendering/routing design.
- Failure check: request a random URL, a nonexistent section, a nonexistent release and a valid section directly; verify document statuses/content types and rendered states. Valid section must succeed; nonexistent section must not return indexable 200 content. Check mobile/document Accept headers too.
- Leading indicator: Search Console soft-404 count and unexpected 200 responses in periodic route smoke checks.

### T5 — Medium, before launch: no repository sitemap or robots endpoint is implemented

- Evidence: `rg --files frontend/public` lists icons and a web manifest, with no robots or sitemap file. Searches across frontend and Worker sources found no sitemap generation, `Sitemap:` directive or robots handler. Vite copies the public directory into the static output (`frontend/vite.config.ts:9–12`); the Worker has no special-file routes (`deployment/cloudflare/worker.ts:54–55`). The existing compiled output likewise has no robots/sitemap file. Live `/robots.txt`, `/sitemap.xml` and `/sitemap_index.xml` return 200 HTML containing the identical SPA shell, not valid robots text or XML. The SEO skill's canonical `sitemap_discovery.py` helper also checked `/sitemap-index.xml` and `/wp-sitemap.xml`; all four sitemap candidates returned 200 but failed XML validation (`DOCTYPE is not allowed in sitemap XML`), with `declared: []` and `found: []`. Evidence: `constitution.ng-audit/evidence/tech-sitemap-discovery.json`. No working sitemap was found by bounded declared/common-path discovery; this is not a claim that every conceivable URL was tried.
- First principle: the corpus needs an explicit inventory of canonical, indexable pages and an unambiguous crawler policy. Missing robots.txt alone does not block crawling or incur a penalty; a sitemap is a discovery aid, not an indexing guarantee.
- Recommendation: generate an XML sitemap from approved indexable release/section records, including only canonical HTTPS URLs that return 200. Add actual significant-modification dates only when reliable, otherwise omit `lastmod`; do not use deployment timestamps for unchanged law text. Add a valid root robots file with the sitemap location and permit resources needed for public rendering. Use noindex/authentication for nonpublic surfaces rather than robots.txt as a security boundary.
- Dependency: T3 canonical/edition policy and T4 correct statuses; the sitemap cannot cure T2 discovery gaps on its own.
- Failure check: after authorized launch, discover both declared and common sitemap locations, require parseable XML with correct content type, and verify each entry against status, canonical and robots/noindex policy. `/robots.txt` must be plain text, not the SPA shell. Check the 50,000-URL / 50-MB per-file limits only if relevant to actual inventory size.
- Leading indicator: zero noncanonical, noindexed, redirected or non-200 sitemap entries; intended-versus-submitted page count and successful sitemap processing in Search Console.

### T6 — Medium: utility and parameter-driven pages have no explicit indexing policy

- Evidence: no `noindex`, robots meta or X-Robots-Tag declaration was found in frontend/Worker sources. Utility routes set only titles (`frontend/src/routes/_layout/settings.tsx:5–14`; `frontend/src/routes/_layout/saved.tsx:5–14`). Admin has a browser guard (`frontend/src/routes/_layout/admin.tsx:8–13`) and a title (`:15–21`); homepage search admits conversation IDs, queries, modes, releases and selection IDs (`frontend/src/routes/_layout/index.tsx:9–16`). This review does not claim private account data is exposed; backend authentication is a separate boundary.
- First principle: navigable utility screens and arbitrary internal-search states are not automatically useful search landing pages.
- Recommendation: document an allowlist of indexable public document types. Send appropriate noindex on account/auth/settings/saved/internal-search/error states and keep them out of sitemaps. Preserve direct share links and authenticated access. Do not blanket-noindex a shared initial SPA shell if public pages depend on it; emit per-document directives through T1/T4.
- Dependency: indexable route policy and per-document response capability.
- Failure check: sample utility and query-state URLs with a raw HTTP fetch and Search Console inspection when available; ensure public legal pages remain indexable and utility content does not enter the public index. Do not block crawlers from reading a noindex directive with a disallow rule.
- Leading indicator: indexed utility/internal-search URLs; unexpected robots directive changes on public legal documents.

### T7 — Medium: bare-home landing redirect occurs only in the browser

- Evidence: fresh signed-out bare `/` navigation redirects to `/welcome` using router logic (`frontend/src/routes/_layout/index.tsx:18–24`); behavior depends on navigation/session state (`frontend/src/lib/landing.ts:1–9`). Both server responses originate from the generic shell, with no corresponding HTTP redirect in `deployment/cloudflare/worker.ts:54–55`.
- First principle: a public search landing page should have stable URL identity and predictable initial content. Contextual app navigation can remain dynamic, but should not be the sole source of public routing semantics.
- Recommendation: select the primary public landing URL and make its static/server response and canonical explicit. If permanently consolidating one URL, implement one-hop HTTP redirection only where it preserves the intended signed-in/deep-link flows. This is a product/routing decision, not a reason to force every chat URL onto `/welcome`.
- Dependency: T3 policy and T1/T4 document rendering.
- Failure check: compare raw and rendered `/` and `/welcome` for guests and signed-in navigation; canonical, redirect and content must match the intended flow without loops or broken query links.
- Leading indicator: duplicate homepage canonical clusters and redirect errors; direct landing-page conversion/engagement once analytics is available.

### T8 — Medium, measured: duplicate landing titles and descriptions after rendering

- Evidence: `constitution.ng-audit/evidence/home-rendered.html` contains two title elements (`constitution.ng · Nigeria's Constitution in plain English` and `constitution.ng`) and two different description tags. The source defines a static title/description (`frontend/index.html:6–10`) plus route metadata (`frontend/src/routes/welcome.tsx:11–20`) through `HeadContent` (`frontend/src/routes/__root.tsx:12`). No canonical is present in the rendered evidence.
- First principle: each document should express one consistent page identity and snippet summary.
- Recommendation: use one metadata owner for the initial rendered document and client navigation; emit one title and one relevant description, with the same values before and after hydration. Implement with T1 and T3 rather than stacking more tags onto the shell.
- Dependency: rendering/head architecture (T1).
- Failure check: count title/description elements on raw and rendered landing/provision pages and after client navigation; require exactly one of each and matching page identity.
- Leading indicator: zero duplicate metadata elements in a representative route smoke check.

### S1 — Medium opportunity: structured data does not identify the site or public legal documents

- Evidence: repository scan detected one JSON-LD producer: `frontend/src/routes/welcome.tsx:23–34`, which builds FAQPage. No WebSite, Organization, WebPage or BreadcrumbList markup, Microdata or RDFa implementation was found in the inspected frontend. `frontend/src/components/LawPadi/ProvisionView.tsx:137–151` already has a visible citation hierarchy that could support truthful breadcrumbs. Initial HTML contains no structured data (`frontend/index.html:3–26`). The parent-rendered live JSON-LD evidence contains one syntactically valid 2,201-byte FAQPage block with eight questions (`home-jsonld.json`); no WebSite/Organization identity markup appears. Schema.org/Rich Results Test validation was not run.
- First principle: structured data should describe real visible entities and relationships; it does not replace public text or establish legal authority.
- Recommendation: after rendering/indexability work, add a WebSite entity with the verified brand/domain and WebPage/BreadcrumbList on public document pages using the actual citation hierarchy and canonical URLs. Add Organization only if an actual named responsible publisher can be truthfully identified; do not imply government ownership, invent credentials/reviews or label historical material current law. Avoid promising rich results for general legal-document schema.
- Dependency: T3 canonical policy, T1 initial HTML and content/publisher verification.
- Failure check: parse JSON-LD, check absolute URLs, `@context`/`@type`, visible-content agreement and real hierarchy links; use Schema Markup Validator and Google's Rich Results Test for supported types. A test pass is eligibility/syntax evidence, not a guarantee of a search feature.
- Leading indicator: zero schema parsing errors and 100% agreement between document canonical, JSON-LD URL and visible edition/citation.

### S2 — Informational: existing FAQPage is not a Google FAQ rich-result tactic

- Evidence: `frontend/src/routes/welcome.tsx:25–33` emits FAQPage from the same `faqs` data imported for visible landing content. Google documents that the feature ceased appearing on 7 May 2026. No removal is required solely for that reason; no confirmed AI-citation benefit is inferred.
- Recommendation: keep useful visible FAQ content and keep markup accurate if retaining it. Do not spend launch effort expanding FAQPage for Google SERP features; prioritize T1–T5.
- Dependency: none; maintain alongside content updates.
- Failure check: FAQ schema/visible answers diverge or project planning promises a FAQ rich-result feature.
- Leading indicator: data-to-visible-content parity; no launch KPI tied to FAQ rich results.

## Positive source-level signals

- English language and responsive viewport are declared (`frontend/index.html:2–5`); English-only implementation matches current product context. No hreflang is needed for languages that are not implemented.
- Provision links use distinct document paths, not fragment routing (`frontend/src/components/LawPadi/BrowseConstitution.tsx:87–90`). Release-pinned share links support reproducible citations (`frontend/src/lib/legal-provisions.ts:3–4`).
- Edition/current-versus-historical caveats are explicit in helpers (`frontend/src/lib/legal-provisions.ts:26–41`) and rendered below legal wording (`frontend/src/components/LawPadi/ProvisionView.tsx:161–169`). Preserve them in prerendered content and metadata.
- API responses deliberately use private/no-store caching (`deployment/cloudflare/worker.ts:94–96`). Do not weaken this to improve a synthetic SEO result.
- The compiled initial HTML is small (3,752 bytes), so no HTML fetch-size issue was identified. This is not a full page-weight or performance measurement.

## Unmeasured and not scored

constitution.ng/www availability is blocked by observed DNS failure. The Workers HTTP document and special-file statuses, raw shell, rendered landing metadata and FAQ JSON syntax are measured above. Certificate policy/security-header effectiveness, www/non-www redirects, rendered Googlebot behavior, mobile layout, field/lab CWV, selected canonicals/indexing and rich-result eligibility remain unmeasured by this sub-review. No SEO Health Score or category score is assigned.

## Primary references checked

- [Google JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics): Google rendering, crawlable links, prerendering and soft-404 handling.
- [Google's developer guide](https://developers.google.com/search/docs/fundamentals/get-started-developers): discoverable hyperlinks and sitemap role.
- [Google Search documentation updates](https://developers.google.com/search/updates): FAQ rich-result retirement on 7 May 2026; documentation removed 15 June 2026.
- [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap): canonical URLs and accurate significant-modification dates.

No production resources, application code, dependencies, generated client files or deployment settings were changed. Only audit findings and read-only evidence were authored by this review.
