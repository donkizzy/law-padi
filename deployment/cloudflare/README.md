# Cloudflare frontend

The existing Worker uses the legacy name `constitition-ng`. Set
`PUBLIC_SITE_URL` to its existing bare HTTPS origin and leave
`CLOUDFLARE_WORKER_NAME` unset to retain it. The generated configuration defaults
to the existing name; set `CLOUDFLARE_WORKER_NAME=constitution-ng` only during
the migration below. `API_ORIGIN` names the API service the Worker proxies to:
the Railway `api` service's public domain.

The main hostname and version URLs stay disabled while the AI launch evaluation
and human review are pending. Cloudflare can still build and deploy the assets
and API proxy. A successful build alone does not approve public AI generation.

## Native GitHub builds

Use the repository root, production branch `master`, and these commands:

- Build: `bash deployment/cloudflare/build.sh`
- Deploy: `bunx wrangler@4.151.0 deploy --config deployment/wrangler.generated.json`

Set the build variables in the table below and leave
`CLOUDFLARE_PUBLIC_LAUNCH=false`. Keep non-production branch builds disabled until
an isolated preview backend is configured. These builds run on Cloudflare, not
GitHub Actions. Dependencies use the committed Bun lockfile.

The build script compiles the frontend with a same-origin API URL and the exact
packaged source revision, then generates the ignored Wrangler configuration.
Use the existing account's native build credential; do not copy database, AI or
R2 credentials into this Worker. The only required Worker secret is
`ORIGIN_PROXY_SECRET`, matching the API's `ORIGIN_PROXY_SECRET` variable.

For a local build, install locked dependencies with `bun install --frozen-lockfile`,
then run `bash deployment/cloudflare/build.sh`. An operator can supply the secret
privately for the initial upload through Wrangler's `--secrets-file` option.
Subsequent deploys retain existing Worker secrets.

## Build variables

No deployment hostname is tracked in this repository. `wrangler.json` is a
template; `prepare.py` writes `PUBLIC_SITE_URL` and `API_ORIGIN` into the
generated, ignored configuration and refuses any value that is not a bare HTTPS
origin (no credentials, port, path, query or fragment). `API_ORIGIN` must also
be a `.up.railway.app` host, the same rule `worker.ts` applies when it proxies
(`API_HOST_SUFFIXES` in both files).

The Worker sends the client address to the API in `X-Origin-Client-IP` as well
as `X-Forwarded-For`, and drops any copy of either that the browser sent.
Railway's edge may rewrite `X-Forwarded-For` with the Worker's own address, so
the API's per-address limits read the dedicated header first.

| Variable | Required | Meaning |
| --- | --- | --- |
| `PUBLIC_SITE_URL` | yes | The canonical public origin. Passed to Vite as `VITE_PUBLIC_SITE_URL` and to the Worker. |
| `API_ORIGIN` | yes | The API origin: the Railway `api` service's public domain, for example `https://<service>.up.railway.app`. `build.sh` stops if it is unset; `prepare.py` also accepts `--api-origin`. |
| `CLOUDFLARE_WORKER_NAME` | no | `constitition-ng` (the legacy name, the default) or `constitution-ng`. |
| `CLOUDFLARE_PUBLIC_LAUNCH` | no | `false` (default) or `true`; see "Launch and verification". |
| `BUN_VERSION` | yes | `1.3.12`. |

The API's `FRONTEND_HOST` must equal `PUBLIC_SITE_URL`; see
[`deployment/railway/README.md`](../railway/README.md).

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

After the matching 200-case evaluation and human review pass, verify the API's
`FRONTEND_HOST` in Railway matches this Worker address, enable its approved AI controls,
and test a bounded answer and budget accounting. Set
`CLOUDFLARE_PUBLIC_LAUNCH=true` in Cloudflare's build environment and rebuild the
approved commit. This enables the main workers.dev address while keeping version
URLs disabled. Then verify SPA deep links, guest cookies, login, history, source
PDFs and SSE replay through the public origin.

To test the prepared Worker locally against the Railway API without publishing a route,
use `wrangler dev --local` with the generated config and the private proxy
credential. Do not set paid generation flags or use a production chat session
for load or destructive tests.

## Public document rendering and discovery

See [the SEO/AI discovery rollout](../../docs/seo-and-ai-discovery.md). The Worker
now runs before static assets and serves real public HTML, robots, sitemap and
LLM directory responses. Deploy the backend's release-scoped full-tree support
before this Worker; the sitemap intentionally rejects an incomplete old response.
`PUBLIC_SITE_URL` is a required build variable for the bare canonical HTTPS origin;
it is passed to both Vite and the Worker configuration. The Worker has no
fallback: without it, public routes answer 503. Changing it does not configure
DNS, TLS or public routing.

The Worker's public pages are built from three layers:
`frontend/src/lib/public-pages.ts` and `seo.ts` hold the metadata and copy that the
React routes also use, `pages.ts` holds the page bodies and `html.ts` the escaping
template. `seo-output.test.ts` pins the rendered output (`bun test
deployment/cloudflare/`; update its snapshots only for an intended change).

Before enabling this configuration, set `PUBLIC_SITE_URL` and `API_ORIGIN` on the
existing Cloudflare build to their current values. `FRONTEND_HOST` and
`R2_BUCKET_NAME` for the API are Railway shared variables, set in the Railway
dashboard.

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
3. In Railway, set the `FRONTEND_HOST` shared variable to the new origin and
   redeploy the services that read it; verify login and CORS through the new
   origin.
4. Deploy the redirect to the legacy Worker, passing the verified new origin as
   a variable (`wrangler.redirect.json` carries none, and the redirect answers
   500 until one is set):
   `bunx wrangler@4.151.0 deploy --config deployment/cloudflare/wrangler.redirect.json --var PUBLIC_SITE_URL:<new origin>`. Verify an old URL redirects with its path and query to
   the new origin, and verify sitemap and canonical URLs. Keep the legacy Worker
   and its workers.dev route active for existing links.
