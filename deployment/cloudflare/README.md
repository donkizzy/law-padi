# Cloudflare frontend

The existing Worker `constitition-ng` belongs to the personal Cloudflare account
and is already connected to `donkizzy/law-padi`. Preserve that existing spelling;
the eventual free address is `https://constitition-ng.amosgodwin500.workers.dev`.
Its API origin is `https://constitution-ng-api.onrender.com`.

The main hostname and version URLs stay disabled while the AI launch evaluation
and human review are pending. Cloudflare can still build and deploy the assets
and API proxy. A successful build alone does not approve public AI generation.

## Native GitHub builds

Use the repository root, production branch `master`, and these commands:

- Build: `bash deployment/cloudflare/build.sh`
- Deploy: `bunx wrangler@4.151.0 deploy --config deployment/wrangler.generated.json`

Set `BUN_VERSION=1.3.12` in Cloudflare's build variables and leave
`CLOUDFLARE_PUBLIC_LAUNCH=false`. Keep non-production branch builds disabled until
an isolated preview backend is configured. These builds run on Cloudflare, not
GitHub Actions. Dependencies use the committed Bun lockfile.

The build script compiles the frontend with a same-origin API URL and the exact
packaged source revision, then generates the ignored Wrangler configuration.
Use the existing account's native build credential; do not copy database, AI or
R2 credentials into this Worker. The only required Worker secret is
`ORIGIN_PROXY_SECRET`, matching Render's private environment.

For a local build, install locked dependencies with `bun install --frozen-lockfile`,
then run `bash deployment/cloudflare/build.sh`. An operator can supply the secret
privately for the initial upload through Wrangler's `--secrets-file` option.
Subsequent deploys retain existing Worker secrets.

## Launch and verification

After the matching 200-case evaluation and human review pass, verify Render's
frontend origin matches this Worker address, enable its approved AI controls,
and test a bounded answer and budget accounting. Set
`CLOUDFLARE_PUBLIC_LAUNCH=true` in Cloudflare's build environment and rebuild the
approved commit. This enables the main workers.dev address while keeping version
URLs disabled. Then verify SPA deep links, guest cookies, login, history, source
PDFs and SSE replay through the public origin.

To test the prepared Worker locally against Render without publishing a route,
use `wrangler dev --local` with the generated config and the private proxy
credential. Do not set paid generation flags or use a production chat session
for load or destructive tests.

## Public document rendering and discovery

See [the SEO/AI discovery rollout](../../docs/seo-and-ai-discovery.md). The Worker
now runs before static assets and serves real public HTML, robots, sitemap and
LLM directory responses. Deploy the backend's release-scoped full-tree support
before this Worker; the sitemap intentionally rejects an incomplete old response.
`PUBLIC_SITE_URL` is an optional build variable for a bare canonical HTTPS origin;
it defaults to the confirmed Workers address and is passed to both Vite and the
Worker configuration. Changing it does not configure DNS, TLS or public routing.
