# Prioritized SEO action plan

Audit: 16 October 2026. Target confirmed by user: `https://constitition-ng.amosgodwin500.workers.dev`. These are recommendations, not changes or deployment authorization. Source-level findings and live artifacts are in [the report](FULL-AUDIT-REPORT.md).

| Order | Priority | Work | Depends on | Failure / acceptance check | Leading indicator |
|---|---|---|---|---|---|
| A | High, immediate | Remove public fixture amendment claims until sourced records are reviewed | Amendment publication scope | Clean guest can no longer read fixture cards/static diff; verified records require source identity | Unsourced public legal-status records = 0 |
| B | High, immediate design decision | Decide canonical origin, public URL inventory and historical-release policy | Product/source-edition decision | Two distinct legal wordings never canonicalize as equivalent; final-origin plan documented | Canonical/content mismatches = 0 |
| C | High, next implementation | Prerender or server-render public landing, chapter hubs and provision reading content | B | Plain GET contains heading, wording, citation, source edition and links; no private/account content rendered publicly | Raw-content smoke check coverage |
| D | High, alongside C | Correct document statuses and explicit special-file routing | B, C response layer | Valid provision 200; nonexistent page/provision 404/410; upstream outage uses suitable temporary error; special files never shell HTML | Unexpected 200s; soft-404 count |
| E | High, alongside C | Give head tags one owner; unique section title/description/H1/canonical | B, C | Exactly one title/description/canonical; section and edition correctly identified | Duplicate metadata and canonical conflicts = 0 |
| F | High, discovery | Publish ordinary chapter/part/section links without expansion clicks | B, C | Link-only crawl reaches released provision set; reconcile known corpus gaps before completeness claims | Orphan count; discovery/release coverage |
| G | Medium, before indexing rollout | Generate real robots.txt and XML sitemap from canonical release records | B, D, F | Correct content type; parseable; only canonical indexable 200 URLs; truthful lastmod or omit | Sitemap processing success; bad entries = 0 |
| H | Medium, before indexing rollout | Apply per-route noindex to utility/account/internal-search states | B, C, D | Public law pages remain indexable; utilities excluded without using robots as security | Indexed utility URL count |
| I | Medium, within a month | Publish operator, sources/review and corrections policy; dated benchmark evidence | Confirm real owner/review process/test artifact | Reader can trace claims and edition in ≤2 links; retrieval metric not framed as answer correctness | Unsupported claims = 0 |
| J | Medium, after C/E/I | Add accurate site/document/breadcrumb schema | B, C, E, I | JSON parses; URL, hierarchy and visible edition agree; no invented publisher/reviewer | Validator errors = 0 |
| K | Medium, measure before optimization | Capture mobile trace; test fonts/JS preloads and immutable hashed-asset caching | Stable target/build | Repeat visit improves without stale deployments, typography regressions or private caching | Initial transfer/execution; LCP/INP/CLS |
| L | Critical brand-domain prerequisite, when launch gates permit | Connect constitution.ng, verify TLS and origin migration/redirect policy | B and existing launch gates | External DNS resolves; HTTPS works; canonical redirects preserve page/release identity | External reachability; selected canonical parity |
| M | Ongoing | Verify Search Console, submit sitemap, inspect templates and monitor | Public authorized origin, G/H | Google can fetch/render samples; chosen canonical and intended edition agree | Submitted/indexed provision trends; impressions/CTR by type |

The DNS prerequisite is Critical for the brand domain but does not block implementing C–K against the confirmed working deployment. A–B can proceed as decisions before publication. C–F should share one route/release model; G and J follow that model rather than creating competing URL definitions.

Effort is not estimated without choosing the rendering approach. Rendering may require an architecture change: discuss that choice before opening a PR, per repository guidance. No lockfile, application, deployment, DNS or generation settings were modified for this audit.

Preserve historical/source-edition notices, source PDF provenance, guest access, brand design tokens, backend authorization and private API caching. Do not pad short legal provisions to arbitrary word counts, claim current consolidation, invent review credentials, promise rich-result/AI citation gains, or publish generated answer pages without provenance and an editorial decision.

Recheck route/content acceptance criteria on the next release. Once the final domain is live, repeat live discovery and URL Inspection; obtain actual mobile lab and field measurements rather than carrying forward this audit's unmeasured performance category.
