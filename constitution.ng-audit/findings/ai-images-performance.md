# AI access, images and performance audit

Checked 16 October 2026 at 15:32 WAT. Read-only live GETs against the discovered public preview `https://constitition-ng.amosgodwin500.workers.dev` and repository review; no generation request or production mutation. The requested constitution.ng domain does not resolve per the parent audit. This is a preview/readiness review, not evidence that constitution.ng is indexed. Deployment documentation is stale: `docs/deployment-status.md:41` and `:61` say frontend URLs are disabled, while the preview currently returns HTTP 200. Repository and deployed asset hashes differ; live conclusions below are backed by captured HTML and headers, while code conclusions are identified separately.

No Lighthouse, CrUX, PageSpeed, accessibility-tree heuristic, AI citation tracking or external brand-presence measurement was run. No numeric readiness or CWV score is justified. LCP, INP and CLS are **not measured**.

## High — public reading content requires JavaScript and API completion

**Observation:** Live root HTML contains only `<div id="root"></div>` in its body. Local source matches this architecture in `frontend/index.html:25`, `frontend/src/main.tsx:94` and `frontend/src/hooks/useLegalCorpus.ts:41`. Live evidence is `../evidence/ai-images/constitution-audit-live.html`. The landing copy, provision wording, provenance and internal links are absent from the raw HTML.

**Implication:** Non-rendering fetchers have no passages to extract. Google can execute JavaScript, so this is not proof of Google exclusion; it creates rendering and API dependencies that need validation. [Google explicitly recommends server rendering or prerendering because some bots cannot run JavaScript.](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)

**Action/dependency:** Decide canonical public reading URLs and the published release policy, then prerender or server-render the marketing page and provision reading routes with source edition, citation, wording and real links. Preserve access control for private conversations and drafts. This unblocks reliable raw-HTML discovery, metadata, and subsequent AI-search checks.

**Failure check:** A plain GET to the landing page and sampled provision URL still lacks the expected visible heading, exact text, edition and source link, or rendered and raw text disagree. **Leading indicator:** A release smoke check counting raw-HTML content and links for these routes, plus Search Console URL Inspection after the real domain launches.

## Medium — discovery URLs are false successful HTML responses

Live `/llms.txt`, `/ai-catalog.json`, and `/.well-known/api-catalog` each returned HTTP 200 `text/html`, byte-identical to the root shell (SHA-1 `0ccc7d09aa5d12fe1797ad64804ba11d638c79ea`). `Accept: text/markdown` on `/` also returned that HTML with no Markdown negotiation. Relevant headers are saved in `../evidence/ai-images/`.

This follows the configured SPA fallback at `deployment/cloudflare/wrangler.json:10`; the Worker forwards non-API paths to assets in `deployment/cloudflare/worker.ts:55`. The problem is false success at missing machine-readable endpoints, not a need to implement every optional format.

**Action/dependency:** After defining valid public routes, return a true 404 for unsupported discovery files and unknown URLs. If a supported format is intentionally provided later, return its real media type. Defer llms.txt, API catalogs, Markdown and WebMCP investment until accessible HTML and crawler access work. Their absence is informational; do not promise ranking or AI citation improvements from them. [Google's AI features documentation says no additional special markup or machine-readable AI files are required.](https://developers.google.com/search/docs/appearance/ai-features)

**Failure check:** Repeating these GETs still yields root HTML with 200 for unsupported resources. **Leading indicator:** A simple status/content-type smoke check in deployments. Catalogs and WebMCP were not found in source, and no runtime tool registry was inspected.

## Medium — font request and startup prerequisites deserve measured optimization

`frontend/index.html:17–22` requests five font families and fourteen weight selections in a blocking third-party stylesheet: Lexend 4, Literata 3, IBM Plex Mono 2, Noto Sans 3 and Noto Serif 2. Preconnects and `display=swap` are already present. This is a dependency/risk observation; actual downloaded font files depend on the returned CSS, glyph use and browser, and were not measured. Preserve the project's type tokens and brand faces while comparing self-hosted subsets, used-weight selection and noncritical fallback loading. [web.dev discusses reducing the critical path and controlling font loading.](https://web.dev/articles/optimize-webfont-loading)

Separately, `frontend/src/main.tsx:94` waits for `initSession` before mounting the whole UI. In local source a returning browser with the session hint may wait up to the 3,000 ms timeout (`frontend/src/lib/session.ts:20`, `:144–159`); guests without a hint skip this network wait. This is a code-path bound, not a measured delay or CWV result. After public HTML is available, consider rendering it independently while authenticated state resolves.

**Dependency:** Capture a repeatable mobile network/CPU trace on the correct public origin, for both first guest and returning signed-in flows. **Failure check:** Changes do not reduce time to visible useful content or font bytes, produce fallback layout instability, or break routing/session guards. **Leading indicator:** Trace comparisons of font requests, render timing and returning-session wait time; real-user LCP, INP and CLS once traffic permits.

## Medium — fingerprinted script revalidates on each reuse

Live `/assets/index-BFONK1Dk.js` returns HTTP 200, `content-encoding: gzip`, `cf-cache-status: HIT`, and `cache-control: public, max-age=0, must-revalidate`. The decoded script is 233,325 bytes. Root HTML lists 30 modulepreloads. These are response and file observations, not compressed transfer totals or evidence of poor CWV. Current production HTML includes schema, authentication and UI chunks among the preload list, so route splitting alone does not establish a small initial dependency graph. Local `frontend/vite.config.ts:19–22` already enables automatic route code splitting.

**Action/dependency:** Once the release pipeline confirms fingerprinted URLs are immutable, consider long-lived immutable caching only for fingerprinted assets; keep HTML revalidating. Inspect the network/coverage trace before altering eager imports or preload behavior. Keep account/conversation/API private/no-store behavior (`deployment/cloudflare/worker.ts:95`) intact.

**Failure check:** A same-version repeat navigation still revalidates assets unnecessarily, or a new release serves stale HTML/asset mismatches. **Leading indicator:** Hashed-asset response headers, cache reuse in a repeat-visit waterfall, total initial JS transfer/execution by route.

## Medium — trust and test claims need a public evidence trail

The landing page honestly states independence and lack of government affiliation (`frontend/src/components/Landing/LandingPage.tsx:76–78`, `:952–955`) and the historical edition limitation (`:60–62`, `:530–535`). This is useful context. It also advertises "54 of 55" successful queries and "latest test" (`:784–789`) without a linked report, evaluation date, evaluated revision or methodology in its proof section (`:800–833`). Its footer routes (`:938–944`) do not expose an About/editorial/methodology page.

**Action/dependency:** Once the current release and launch evaluation are approved, publish a concise operator/methodology/corrections page and link the dated evaluation scope from the proof claim. Explain who maintains and reviews material, how sources/versions are selected, how issues are reported, and the boundary between historical statute wording and generated explanation. This builds verifiability; no citation/ranking gain is promised.

**Failure check:** Readers still cannot trace a quantitative claim to a dated, reproducible report or identify the current corpus edition. **Leading indicator:** Content-release checklist for claim/report parity, source edition notices and correction contact availability.

## Strengths and non-findings

- Provision detail retains original text, edition and hierarchy (`frontend/src/components/LawPadi/ProvisionView.tsx:137–168`). Source details include document, authority, printed page and original PDF link (`frontend/src/components/LawPadi/SourcePanel.tsx:119–147`). Chat evidence has a real full-section anchor and PDF anchor (`frontend/src/components/LawPadi/ChatEvidencePanel.tsx:85–95`). Preserve these in public HTML.
- Static accessibility patterns are promising: landing skip link/main landmark (`LandingPage.tsx:84–91`), labelled question form (`:363–385`), native FAQ details/summary (`:872–890`), named menu and expanded state (`:194–200`), named icon buttons (`primitives.tsx:80–101`) and textarea/send labels (`ChatComposer.tsx:71–74`, `:120–126`). This is source evidence, not an accessibility pass. Keyboard, focus, mobile tree, contrast and action completion remain for rendered testing.
- The landing content uses text and inline SVG rather than large hero photography. `frontend/src/components/Common/Logo.tsx:26–47` uses vector artwork with a sized viewBox; its wrappers supply accessible brand names (`:70`, `:80`). Public routes have no `<img>` elements found by source search; image elements are in the private admin workspace. Therefore no public missing-alt, oversized-hero, responsive-image or lazy-LCP defect is established. Favicons/PWA icons are present. Do not convert these to WebP reflexively or add decorative images solely for SEO.
- Reduced-motion transitions are addressed in `frontend/src/index.css:265–271`. Reveal blocks start transparent until observed (`LandingPage.tsx:275–300`, `useInView.ts:6–24`); validate that prerendered content remains visible before hydration and with script failure if prerendering is adopted.

## Access-policy boundary

The technical audit owns actual robots.txt evidence. No claim about training, search crawler access or WAF behavior follows from this subreview. Search access (for example Googlebot or OAI-SearchBot) and training preference (for example GPTBot) must be reported separately. No spoofed user-agent/WAF requests were sent. Optional emerging discovery protocols are not mandatory launch or SEO requirements.
