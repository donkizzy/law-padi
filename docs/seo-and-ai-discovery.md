# Public SEO and AI search discovery

Implemented 16 October 2026. The confirmed public origin is
`https://constitition-ng.amosgodwin500.workers.dev` (preserve the Worker spelling).
This document describes the code in this checkout, not a completed production rollout.

## Rendering and URL policy

Cloudflare's Worker handles document requests before the assets binding. Public
landing, publisher/methodology, browse hubs and provision routes receive readable
HTML before JavaScript. The same published corpus APIs supply the browser and
server. A public-only JSON bootstrap seeds React Query, so replacing the initial
reading HTML with the interactive React app does not require a duplicate initial
corpus request. Server head tags are marked and removed when React mounts;
TanStack HeadContent then owns one metadata set. This is progressive enhancement
of public documents, not authenticated app SSR or bot-specific rendering.

Provision and chapter URLs are pinned to the backend's published release.
Unpinned reading aliases resolve with temporary redirects to the current published
release. Distinct historical wordings retain distinct canonicals. There are no
invented law-update timestamps. The Worker reads only the public enacted corpus,
forwards no visitor cookies or authorization during document rendering, and uses
a 15-second upstream timeout. Upstream failure produces 503/noindex/Retry-After,
not a false missing-provision response. All document HTML and API responses remain
private/no-store; only fingerprinted public assets receive immutable caching.

The `/amendments` fixture is no longer public content: direct requests return 410
and noindex; client navigation shows an unpublished explanation. Known gaps and
historical-source limitations remain visible. No legal data, publication state,
AI generation flags, budget or credentials were changed.

## Discovery and citation

- `/robots.txt` is real text. It explicitly permits OAI-SearchBot,
  Claude-SearchBot and PerplexityBot to read public pages. The wildcard rules
  also allow ordinary search bots. API crawling is disallowed; authentication
  continues to protect private data. These rules do not introduce a training
  preference; search and training controls are different.
- `/sitemap.xml` uses the API's release-scoped `all_nodes=true` tree projection.
  It includes public hubs and top-level reading units, excludes subsection and
  paragraph duplicates, utilities and amendment fixtures, and omits unverified
  `lastmod`. An old API without `scope=all` returns 503 instead of a partial sitemap.
- `/llms.txt` supplies a small directory, edition limits and citation guidance.
  It is optional and carries no promised Google ranking or LLM citation benefit.
- WebSite/publisher, WebPage and provision BreadcrumbList entities use real
  public URLs. The publisher is constitution.ng, per the user's choice, with the
  repository as a public reference. The retained FAQ markup stays accurate.
- `/about` names the publisher, source scope, automated-review boundary, known
  corpus gaps and GitHub corrections channel. `/methodology` links the dated
  retained retrieval benchmark and distinguishes hits from answer correctness.
- Utility, arbitrary search and error responses are noindex. Unknown URLs and
  unsupported special files return actual 404s. Search snippets remain allowed
  on approved public documents. No `nosnippet` or restrictive snippet cap is added.

Crawler access and valid markup establish accessibility, not inclusion. Provider
crawling schedules, indexing, relevance and independent source trust still determine
whether Google, ChatGPT, Claude or Perplexity cites the site. No provider submission,
indexing result, AI citation rate or model-training inclusion is claimed.

Primary references: [OpenAI crawler controls](https://developers.openai.com/api/docs/bots),
[Anthropic crawlers](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler),
[Google AI features](https://developers.google.com/search/docs/appearance/ai-features).

## Verification completed locally

- Frontend TypeScript/production build and Biome checks.
- Worker TypeScript check and Wrangler 4.151.0 dry-run bundle (no upload).
- 20 Worker/proxy tests: published content, metadata, redirects, sitemap marker,
  errors/HEAD, escaping, private-request isolation, asset cache and existing SSE.
- Eight legal API tests using the guarded dedicated `_test` database runner,
  including complete release-scoped index, hub metadata and draft rejection.
- Backend mypy, ty and Ruff checks; deployment preparation unit tests.
- 19 mocked browser regression tests cover metadata uniqueness, linked browsing and removal of amendment fixtures.
- Browser: Section 37 text/edition, single metadata tags, H1, ordinary chapter
  links and publisher/corrections page. Raw HTTP: correct 200/404/410, plain text
  robots/LLM directory and parseable XML sitemap with 550 unique URLs from the
  local published source release. Localhost is deliberately noindexed by the
  response header because it is not the configured canonical origin.

Smoke evidence: `constitution.ng-audit/implementation-smoke.json`. The source
corpus and browser checks did not generate a paid answer or write a chat.
The focused backend run's aggregate coverage is not the full-suite coverage baseline.

## Rollout order and remaining external work

1. Deploy the backend projection first. Verify `GET /api/v1/legal/provisions/tree?all_nodes=true`
   returns `scope=all` for the published edition and rejects private releases.
2. Build and deploy the matching frontend/Worker after the existing release
   controls permit it. Keep the current public-routing and AI approval choices;
   a successful dry run is not an instruction to change them. No new dependencies
   or database migrations are required. The rendering approach keeps the current
   Vite/React architecture and adds HTML at the existing Worker boundary.
3. Set `PUBLIC_SITE_URL` in Cloudflare's build environment to the canonical HTTPS
   origin. The build passes the same value to Vite and Wrangler. It defaults to
   the confirmed Workers address. When the brand domain is connected, change this
   value in one place, configure host routing/TLS and verify the chosen host's
   redirects before submitting its sitemap. Do not publish constitution.ng URLs
   while it still returns NXDOMAIN.
4. On the deployed origin, verify raw and rendered metadata, edition parity,
   source links, canonical statuses, robots, sitemap, guest/account flows and SSE.
   Inspect Cloudflare bot/WAF logs for real verified search-crawler requests;
   do not disable security globally or trust a spoofed user-agent as verification.
5. Verify the owned property in Google Search Console and Bing Webmaster Tools,
   submit its sitemap, inspect landing/hub/provision/missing pages, and check
   selected canonicals and coverage. Accounts/property verification are required;
   no credentials for these were available in this session.
6. Obtain a repeatable mobile trace/PageSpeed result and field LCP/INP/CLS when
   traffic permits before further font/import optimization. The prior PageSpeed
   request was rate-limited. Sample real citation queries after indexing and track
   actual cited URLs/referral traffic; do not treat crawler allowance as a result.

For subsequent releases, check sitemap coverage against the published inventory,
metadata uniqueness, source-edition agreement, noindex routes and the absence of
fixture legal-status content. New content should serve real research questions
and cite the published edition; do not mass-publish generated answers or change
historical text to target keywords.

The benchmark JSON is served directly at `/methodology/benchmark.json`, so its
verification does not require repository access. Signed-out checks of the GitHub
repository/issues returned 404 during this work. Corrections retain the user's
chosen repository link with an explicit access requirement; no repository visibility
setting was changed. On 17 October 2026, the user confirmed keeping GitHub as the
corrections channel with an explicit repository-access requirement. No alternative
public contact is pending.
