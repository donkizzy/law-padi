# constitution.ng SEO audit

Screenshot retention note (20 October 2026): generated Playwright and computer-use screenshots were removed at the user's request. Screenshot paths below are historical references; textual audit records are retained.


**16 October 2026 · Africa/Lagos · Read-only audit**

The product has clear, useful positioning and good source-edition disclosures, but its public deployment needs foundational SEO work before organic acquisition. Prioritize truthful public content, crawlable provision pages, document identity and correct HTTP responses ahead of additional marketing content or AI discovery formats.

## Scope and evidence

The user confirmed the Workers deployment as the audit target. Its exact hostname is **https://constitition-ng.amosgodwin500.workers.dev** (the Worker name contains `constitition`). The requested brand domain, `constitution.ng`, and `www.constitution.ng` both returned NXDOMAIN from Google Public DNS. This is a custom-domain launch prerequisite, not proof that the working Workers app is down.

The live app contradicts the local deployment-status document: the Workers homepage returns 200, and `/api/v1/conversations/capabilities` reports conversations and explanations enabled, English supported, build `source-6fad81663549db56`. This audit did not submit a question, generate an answer, create an account, change flags or publish anything. Local HEAD was `300e8b1b55109d4d1d4d208875c3554f064b16ad`; deployed asset hashes differ from the local build. Repository references explain implementation and are distinguished from live observations.

This is a bounded, site-wide template and discovery audit, **not a 500-page exhaustive crawl**. It covers raw and rendered landing, browse, provision and amendment pages; a public provision API; missing routes; robots/sitemap/discovery endpoints; desktop/mobile screenshots; and relevant source. The collapsed browse interface exposed no section links without clicks. No Firecrawl or premium SEO data connector was available. Credential checks found no Search Console, GA4, CrUX, PageSpeed API key, Matomo, Moz or Bing configuration. The unauthenticated PageSpeed mobile request returned a rate-limit error.

**Overall SEO Health Score: not issued.** A complete weighted score would misleadingly combine a nonexistent brand-domain deployment, a separate Workers origin and unmeasured CWV. Category weights below are retained from the skill, with evidence status instead of invented numbers. No confirmed ranking loss, index exclusion, manual action or Google penalty is claimed.

| Category | Weight | Assessment |
|---|---:|---|
| Technical SEO | 22% | High-priority crawl, special-file and status defects |
| Content quality | 23% | Useful reference product; public preview amendment claims and limited review transparency |
| On-page SEO | 20% | Duplicate metadata, generic provision identity, no canonicals |
| Structured data | 10% | Valid FAQPage JSON syntax; no detected site/document/breadcrumb entities |
| Performance / CWV | 10% | Unmeasured; PageSpeed rate-limited, no CrUX credentials |
| AI search readiness | 10% | Source provenance is useful; raw HTML lacks extractable content |
| Images | 5% | Text/vector-led public UI; no established public image defect |

## Findings and priorities

### Critical prerequisite for the brand domain: DNS/public routing

Both brand-domain DNS checks returned status 3 / NXDOMAIN. The app is available at Workers, so this finding concerns `constitution.ng` specifically. Once the existing launch approval process permits it, connect the intended domain, verify TLS and choose one canonical public origin. Keep the interim domain from competing with the final origin through an intentional migration/indexing policy. Domain registrar search listings are not evidence of domain ownership or registration status.

**Dependency:** Existing product launch gates and the domain decision. **Failure check:** The intended domain still fails DNS/TLS or serves a different app. **Indicator:** External DNS/HTTPS smoke check and final-origin canonical agreement. No DNS or deployment change was made.

### High: publicly reachable amendment fixtures undermine provenance

Live `/amendments` renders “Current law” cards, generic proposed-change entries and a static previous/current wording comparison. Its active route imports `AmendmentsView`, which imports hard-coded preview records from `law-padi-data.ts`. Hiding the sidebar item does not prevent direct access. This is an observed publication/provenance defect; this audit does not establish whether any named Act or legal statement is substantively correct.

Keep the fixture route outside public content until it uses reviewed, sourced instrument/proposal records. A deliberate unpublished response is preferable to searchable legal-status fixtures. Decide this before public links, sitemap entries or schema are generated for amendments. [Live page](https://constitition-ng.amosgodwin500.workers.dev/amendments); local evidence: `evidence/amendments-rendered.html`, `screenshots/amendments/` and `findings/content-sxo.md`.

**Failure check:** A clean guest can still read fixture legal-status cards or the fixed comparison. **Indicator:** Public legal-status records without reviewed provenance; target zero.

### High: important public text requires JavaScript and asynchronous data

Raw Worker HTML has a 3,670-byte shell whose body contains only `<div id="root"></div>`. The welcome page renders successfully, but its content, links and FAQ are absent before JavaScript. A sampled provision render initially captured “Checking trusted sources,” while the public Section 37 API separately returned the historical text successfully. A later real-browser inspection successfully displayed Section 37, its wording and the edition caveat; the page had no H1 and no canonical. The early loading snapshot is not proof that Google permanently misses the text. See `evidence/final-browser-verification.md`.

Prerender or server-render the public landing, browse hubs and approved provision pages with heading, wording, citation, source edition and ordinary links. Preserve the interactive app for asking questions and account workflows. Google can execute JavaScript; the issue is dependence on rendering/API completion and limited access for non-rendering readers, not automatic Google exclusion. [Google JavaScript SEO guidance](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics).

**Dependency:** Define public edition/URL policy first. **Failure check:** A plain GET still lacks the expected legal text and provenance, or raw and rendered editions differ. **Indicator:** Raw-content smoke checks and Search Console rendered URL inspection when available.

### High: incorrect success responses for missing pages and SEO files

`/robots.txt`, `/sitemap.xml`, `/sitemap_index.xml`, a random nonexistent page and a nonexistent provision all returned **200 text/html**, byte-identical to the app shell. The sitemap helper found no valid XML across four common locations. The robots response is not a valid authored crawler policy; its absence does not itself mean crawling is blocked. There is no valid observed sitemap.

Make route existence and special-file handling explicit. Return true 404/410 for missing public documents and proper temporary errors for unavailable upstreams; keep valid SPA deep links working. Serve a real plain-text robots file and XML sitemap based on approved canonical public records. Do not turn an API failure into a permanent missing-provision signal. A sitemap helps discovery but does not guarantee indexing. [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview).

**Dependency:** Public route/release inventory and response rendering layer. **Failure check:** Missing paths still return indexable 200 HTML, or robots/XML endpoints return the shell. **Indicator:** Route status/content-type checks, successful sitemap parsing and Search Console soft-404 reports.

### High: document identity and metadata need a single source

The rendered landing contains **two title elements and two description tags**, and no canonical. Sampled browse, amendment and provision pages also contain the static brand title alongside their route title. Section routes use the generic “Constitution section - constitution.ng” and the shared landing description. The page can therefore be indistinguishable from other sections in search metadata.

Give each indexable provision a specific citation/subject/edition title and description, one main heading, and one canonical URL. Resolve ownership of static versus route head tags. Choose whether the default release and a pinned release are equivalent; preserve separate canonicals for genuinely different legal wording. Never canonicalize all historical law to a newer text merely to remove a query parameter. [Google canonical guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

**Dependency:** Canonical-origin and edition publication decisions; coordinate with rendering. **Failure check:** Multiple titles/descriptions remain, two sections retain identical metadata, or the canonical identifies a different legal edition. **Indicator:** Duplicate metadata counts and canonical/content parity across the approved URL list.

### High: crawl discovery stops at collapsed chapter controls

The rendered browse page lists chapters/schedules but has **zero provision anchors** in the captured initial state. Source review shows children are mounted and fetched only after expansion. The welcome page links examples to query-driven app states, not durable answer/reference pages. A crawler should not need button clicks or question submission to discover the reading corpus.

Publish chapter/part hubs with ordinary links to approved sections, available without interaction; keep progressive disclosure for humans. Add useful, reviewed related-provision links and a small set of prominent reference links. Compare discovered URLs with the release inventory rather than blindly publishing a claimed total. Local context records a missing Section 168 and duplicate Section 189 identities; validate the live inventory before claiming complete coverage.

**Dependency:** Canonical release inventory and public rendering. **Failure check:** A link-only crawl cannot reach intended provision pages. **Indicator:** Orphaned published provisions and coverage of internal discovery versus the release inventory.

### Medium: public trust and measurement claims need linked evidence

The site clearly discloses independence, non-advice status and the 2004 edition limitation. Preserve those strengths. The public footer has no linked operator/editorial/corrections policy, and “54 of 55” / “latest test” has no dated methodology link. This metric concerns retrieval, not demonstrated answer correctness. The landing also advertises “all 320 sections” despite the source-level corpus caveats above.

Publish a concise operator/sources/review/corrections page and a dated benchmark explanation naming the test scope, corpus version and measured outcome. Verify complete-coverage and timing claims. Only name reviewers or credentials that exist. The live capabilities endpoint currently reports explanations enabled, so a disabled-service promise mismatch is **not established**; the source-level warning is a future regression case.

**Dependency:** Confirm responsible operator, actual review practice and substantiating evaluation artifact. **Failure check:** A reader cannot trace a number to its evidence or mistake retrieval success for legal correctness. **Indicator:** Unsupported numeric claims and public pages lacking accessible edition/provenance context.

### Medium: utility/query states need an indexing policy

Source has no explicit noindex policy for account screens, settings, saved items or arbitrary query/conversation states. This is not evidence that private data is exposed or that those URLs are indexed. Define an indexable document allowlist, with appropriate per-response noindex elsewhere, and keep utilities out of the sitemap. Preserve backend authentication; robots directives are not access controls. Do not blanket-noindex the shared shell and inadvertently exclude public references.

**Dependency:** Route policy and per-document response control. **Failure check:** Utilities become indexed or public legal pages inherit noindex. **Indicator:** Search Console indexed URL types and route-directive smoke tests.

### Medium opportunities: performance and entity markup

The live initial script is 233,325 decoded bytes, compressed in transit, and the shell lists 30 modulepreloads. Its fingerprinted JS uses `max-age=0, must-revalidate`. Source requests five font families with fourteen weight selections via an external stylesheet; display swapping and preconnects are already present. A returning session hint can delay mount up to the source's 3-second timeout; a fresh guest skips that wait. These are measured asset facts/source risks, not measured poor CWV.

Capture a mobile trace before optimizing imports/fonts. Consider immutable caching for truly fingerprinted public assets, retaining revalidation for HTML and private/no-store for account/API data. Preserve brand fonts/tokens. **Dependency:** Repeatable trace on the chosen origin. **Failure check:** No reduction in transfer/execution/render delay, or stale/mismatched releases. **Indicator:** Waterfall/coverage comparison and real-user LCP, INP and CLS. Threshold targets at the 75th percentile are LCP ≤2.5 s, INP ≤200 ms and CLS ≤0.1; none was measured here. [Google page experience guidance](https://developers.google.com/search/docs/appearance/page-experience).

The detected FAQPage JSON is syntactically valid and derived from the visible FAQ data. Its presence is informational: Google retired FAQ rich results, so do not expand it for that feature or remove it merely because the feature ended. After public content and identity work, describe the real site and document hierarchy with accurate WebSite/WebPage/BreadcrumbList markup; add a publisher entity only after identifying it truthfully. **Failure check:** JSON parsing, visible-content or URL/edition mismatch. **Indicator:** Validator errors and entity/canonical agreement. [Google documentation updates](https://developers.google.com/search/updates).

### Low / optional: AI discovery formats and images

`llms.txt`, `ai-catalog.json` and `/.well-known/api-catalog` return the HTML shell; requesting Markdown also returns HTML. Return 404 for unsupported resources, and add formats only for a concrete consumer need. No WebMCP or Lighthouse Agentic Browsing fraction was measured. Search-crawler behavior and training preferences are separate decisions. Google requires ordinary indexing/snippet eligibility for AI features, not special AI files or schema. [Google AI features guidance](https://developers.google.com/search/docs/appearance/ai-features).

The inspected public UI is mostly text and SVG. No missing-alt, oversized photographic hero or image-related layout defect was established. Do not add or reformat decorative images just to satisfy an SEO checklist. Desktop and 375px mobile captures show a readable hero and primary CTA; the mobile analyzer found no horizontal scroll. Its automated `cta_visible:false` conflicts with the screenshot, which clearly shows the button, so that heuristic is discarded. This is a limited visual sample, not WCAG certification.

## Execution sequence and next measurement

1. Resolve amendment publication/provenance and the intended public origin/edition policy.
2. Implement public document rendering, real statuses and one set of metadata; provide crawlable hierarchy.
3. Generate and validate robots/sitemap from the same canonical release inventory; apply utility noindex policy.
4. Publish operator/methodology evidence, then add accurate entity markup and measure performance before targeted optimization.
5. When launch gates permit the brand domain, verify DNS/TLS, redirects and canonical migration. Use Search Console to inspect landing, chapter, valid provision and missing-provision behavior, then monitor impressions and indexing by page type.

The [action plan](ACTION-PLAN.md) records dependencies and acceptance criteria. The next audit should look for raw readable provision content, zero fixture legal-status pages, complete internal discovery, valid special files, correct 404s, unique metadata and matching selected canonicals. It should also obtain mobile lab results and LCP/INP/CLS field data when available. Organic traffic, rankings, backlinks and actual AI citations remain unmeasured; no visibility gain is promised.

PDF version available on request through the SEO report workflow (`/seo google report full`).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Built by agricidaniel. Join the AI Marketing Hub community
🆓 Free  → https://www.skool.com/ai-marketing-hub
⚡ Pro   → https://www.skool.com/ai-marketing-hub-pro
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
