# SEO action-plan implementation

Implemented 16 October 2026; deployed and verified on Cloudflare and Render on 17 October 2026. Implementation commit: `4b071ac`; backend projection: `306d7c8`. Source revision: `source-ae38247178f9bdd8`.

| Plan item | Status |
|---|---|
| A | Amendment fixtures removed from public route; HTTP 410/noindex |
| B | Canonical origin configurable; distinct legal releases have pinned identities |
| C | Worker renders public reading HTML; React progressively replaces it using shared public data |
| D | Correct unknown-resource 404s and upstream-failure 503s |
| E | Shared per-page metadata, one head owner, provision H1 and breadcrumbs |
| F | Ordinary chapter/part/section links available without expansion clicks |
| G | Real robots.txt and release-derived XML sitemap; 550 unique URLs in local corpus |
| H | Utility/query/error noindex; backend authentication retained |
| I | Brand-named About/sources/review/corrections and dated methodology; benchmark JSON on-site. User confirmed on 17 October 2026: keep GitHub corrections with the repository-access notice |
| J | WebSite/publisher, WebPage and provision BreadcrumbList markup; existing FAQ retained |
| K | Hashed assets cache immutably; no unmeasured font/CWV claims. Mobile lab/field measurement pending |
| L | Bare HTTPS canonical-origin configuration ready; brand domain DNS/TLS connection pending |
| M | Rollout and Search Console/Bing verification/submission checklist prepared; live submissions/indexing/citations not performed |

AI search access is explicit for OAI-SearchBot, Claude-SearchBot and PerplexityBot.
`llms.txt` provides a directory and citation/edition guidance. Accessible HTML,
provenance, internal links and ordinary search indexing do the foundational work;
these changes do not guarantee citation or model-training inclusion.

Validation: frontend production build/Biome, Worker TypeScript and Wrangler dry-run,
20 Worker/proxy tests, 19 mocked browser tests, eight dedicated-test-database legal
API tests, four deployment-preparation tests, backend mypy/ty/Ruff, source-revision
staging parity and local HTTP/XML/browser smoke checks. The full backend suite passed: 479 tests, two skipped, 88% coverage. No paid generation,
chat write, DNS change or repository visibility change occurred.

Backend deployed first, followed by the matching Worker/frontend, preserving existing public routing and AI settings. Live checks passed for 16 endpoints, including a 550-URL sitemap and 1,850-node published index. Browser metadata and Section 37 source text verified without console errors. See [the deployment record and remaining indexing work](../docs/seo-and-ai-discovery.md).
