# Cloudflare frontend

The existing Worker uses the legacy name `constitition-ng`. Set
`PUBLIC_SITE_URL` to its existing bare HTTPS origin and leave
`CLOUDFLARE_WORKER_NAME` unset to retain it. The generated configuration defaults
to the existing name; set `CLOUDFLARE_WORKER_NAME=constitution-ng` only during
the migration below. The API origin remains the configured Render service.

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

## Public read cache

The Worker caches successful public `GET`s under `/api/v1/legal/`: instruments,
the current release, the tree, provisions, citations and history. Reads pinned
with `release_version` stay for one hour and current reads for five minutes;
browsers keep either for one minute. Search, source redirects, errors, unknown
query parameters and every account or conversation route bypass the cache.
Cookies and `Authorization` are removed from these reads, so a stored response
cannot depend on a visitor.

The Cache API needs a custom domain or route. On `workers.dev` it stores nothing:
responses report `x-edge-cache: miss` and only the browser cache applies. After
attaching a domain, request one provision twice and expect `hit` on the second.

Each Cloudflare location holds its own copy and a deploy does not clear it. To
drop stale reads everywhere at once, raise `EDGE_CACHE_VERSION` in `worker.ts`
and deploy. A published change otherwise appears within the times above.

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
`PUBLIC_SITE_URL` is a required build variable for the bare canonical HTTPS origin;
it is passed to both Vite and the Worker configuration. Changing it does not configure DNS, TLS or public routing.

Before enabling this configuration, set `PUBLIC_SITE_URL` on the existing
Cloudflare build to its current origin. In Render, retain the existing values
for the now-unsynced `FRONTEND_HOST` and `R2_BUCKET_NAME` environment variables.

## Rename the Worker

Do not deploy the redirect until the new Worker is verified. Preserve the legacy
Worker and its URL throughout setup.

1. In Cloudflare, create a new Worker named `constitution-ng`, connect the same
   repository and branch, and configure the build and deploy commands above.
   Set `CLOUDFLARE_WORKER_NAME=constitution-ng`, `PUBLIC_SITE_URL` to the new
   bare HTTPS origin, and the existing launch and Bun build variables. Copy the
   `ORIGIN_PROXY_SECRET` Worker secret securely to the new Worker.
2. Deploy the new Worker and enable its workers.dev address or attach the chosen
   custom domain. Verify public pages, API proxy, login, cookies and SSE.
3. In Render, set `FRONTEND_HOST` to the new origin and deploy; verify login and
   CORS through the new origin. Ensure the Blueprint's unsynced values, including
   `R2_BUCKET_NAME`, retain their existing values.
4. Set `PUBLIC_SITE_URL` in `wrangler.redirect.json` to the verified new origin,
   then deploy `bunx wrangler@4.151.0 deploy --config deployment/cloudflare/wrangler.redirect.json`
   to the legacy Worker. Verify an old URL redirects with its path and query to
   the new origin, and verify sitemap and canonical URLs. Keep the legacy Worker
   and its workers.dev route active for existing links.
