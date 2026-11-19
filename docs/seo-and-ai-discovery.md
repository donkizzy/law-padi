# Public pages, search and AI discovery

How public law pages are rendered for search engines and AI search crawlers,
and what to check when releasing them. The Worker code is
`deployment/cloudflare/worker.ts` and `deployment/cloudflare/public-pages.ts`.

## Rendering and URL policy

The Cloudflare Worker handles document requests before the static-assets
binding. Public landing, publisher and methodology pages, browse hubs and
provision routes are returned as readable HTML before JavaScript runs, built
from the same published corpus API as the browser app. A public-only JSON
bootstrap seeds React Query, so the interactive app does not repeat the first
corpus request. Server head tags are removed when React mounts, leaving one
metadata set. This is progressive enhancement of public documents; authenticated
pages are not server-rendered, and crawlers get the same HTML as people.

- Provision and chapter URLs are pinned to the published release. Unpinned
  reading aliases redirect temporarily to the current release. Distinct
  historical wordings keep distinct canonical URLs, and no law-update timestamps
  are invented.
- During document rendering the Worker reads only the public enacted corpus,
  forwards no visitor cookies or authorisation, and uses a 15-second upstream
  timeout. An upstream failure returns 503 with `noindex` and `Retry-After`,
  not a false "missing provision".
- Document HTML and API responses are `private, no-store`; only fingerprinted
  assets are cached as immutable. Public API reads have their own edge-cache
  rules (`deployment/cloudflare/README.md`).
- `/amendments` returns 410 with `noindex`: no amendment content is published.

## Discovery and citation

- `/robots.txt` allows ordinary search crawlers and the search crawlers of AI
  providers (OAI-SearchBot, Claude-SearchBot, PerplexityBot) to read public
  pages, and disallows the API. These rules express no training preference;
  search and training controls are separate.
- `/sitemap.xml` is built from the API's release-scoped full tree. It lists
  public hubs and top-level reading units, excludes subsection and paragraph
  duplicates and utility pages, and omits unverified `lastmod`. An API that
  cannot return the full tree produces a 503 rather than a partial sitemap.
- `/llms.txt` gives a short directory, the edition limits and citation guidance.
  It is optional and promises no ranking or citation benefit.
- Structured data (WebSite and publisher, WebPage, provision BreadcrumbList) uses
  real public URLs.
- `/about` names the publisher, the source scope, the automated-review boundary,
  known corpus gaps and the corrections channel. `/methodology` links the
  retrieval benchmark, which is served at `/methodology/benchmark.json`, and
  distinguishes retrieval hits from answer correctness.
- Utility, arbitrary-search and error responses are `noindex`; unknown URLs
  return 404.

Crawler access and valid markup make the pages readable; they do not establish
inclusion. Indexing, relevance and whether any search or AI provider cites the
site are outside the project's control, and no such result is claimed.

References: [OpenAI crawler controls](https://developers.openai.com/api/docs/bots),
[Anthropic crawlers](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler),
[Google AI features](https://developers.google.com/search/docs/appearance/ai-features).

## Release checklist

1. Deploy the backend first when the Worker depends on a new API projection,
   and check that `GET /api/v1/legal/provisions/tree?all_nodes=true` returns the
   full tree for the published edition and rejects private releases.
2. Build and deploy the Worker. `PUBLIC_SITE_URL` (a bare HTTPS origin) is the
   canonical origin passed to both Vite and the Worker; there is no default, and
   the Worker answers 503 without it. Changing it does not configure DNS,
   TLS or routing, so attach and verify the domain before switching it.
3. On the deployed origin, check raw and rendered metadata, edition labels,
   source links, status codes, `robots.txt`, the sitemap and SSE.
4. When a domain is attached, verify it in Google Search Console and Bing
   Webmaster Tools and submit the sitemap.
5. For each new release, check sitemap coverage against the published
   inventory, metadata uniqueness and `noindex` routes. Do not publish generated
   answers as pages or change historical text to target keywords.

## Open items

- The canonical origin is still the Workers address configured in the
  `PUBLIC_SITE_URL` build variable; moving to the project's own domain needs DNS, TLS, redirects
  from the old origin (it is the canonical URL in the current sitemap) and a
  single `PUBLIC_SITE_URL` change.
- The corrections link opens an email to `CONTACT_EMAIL` (`CORRECTIONS_URL` in
  `frontend/src/lib/seo.ts`), so readers need no GitHub access to report a
  mistake.
- Field performance (LCP, INP, CLS) has not been measured.
