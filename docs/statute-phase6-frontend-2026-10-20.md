# Phase 6: laws as peers in the public interface

The law picker, instrument-filtered Browse and Find flows, canonical law routes, citations, source panels, saved sections, exports and public metadata are implemented. The interface uses only instruments in the selected published release. **The real ACJA 2015 and Police Act 2020 remain unpublished and `needs_review`.** Their extraction defects, verification and human review remain the activation gates.

Post-review: source-context, reference-scope and mixed-release ranking regressions have been repaired and separately checked. The earlier Constitution benchmark measured search rankings only. See [the review response and expanded validation](statute-review-fixes-2026-10-20.md).

## Published law navigation

`GET /api/v1/legal/instruments` returns each available instrument's slug, titles, type, edition label and notice, section count and legal statuses, together with the selected release version. It reads the selected public release's canonical membership. An instrument record or private ingestion run cannot place a draft law in the picker. Previously published retired releases retain their own law lists; draft release reads return 404.

The tree endpoint accepts `instrument`. Roots, full indices, parents and children are scoped to that law. A parent from another law is rejected. Calls without an instrument retain the Constitution default or infer the law from an explicitly qualified parent path.

Browse provides a law switcher and preserves the release when navigating between laws. Reading and hierarchy links use `/laws/<instrument-slug>/<canonical-path>?release=<version>`, with law hubs at `/laws/<instrument-slug>`. Existing `/constitution` reading and Browse links still render; their canonical metadata and outgoing links use the new routes. A detail URL that names two different laws shows an unavailable state and noindex metadata.

Find offers all published laws or one selected law. Bare section references use the picker, defaulting to the Constitution when all laws are selected. A named law in an exact reference takes priority, so `ACJA s.9` still resolves to ACJA when another law is picked. Bare numeric input in both Browse and Find is converted to a section reference. Semantic dense, lexical and topic candidates are filtered before ranking; a single-law search does not inherit the mixed-law cap of three sections per instrument. Query caches include both release and instrument.

## Presentation, copy and discovery

Compact chips use `short_citation`, while cards and source details retain full law-qualified citations. Provision and source panels identify the law and use that instrument's edition notice. Act badges say “As enacted” and their notice remains **“As enacted, may have been amended.”** Constitution wording retains its historical 2004 caveat. A composite release label is no longer presented as a Constitution edition in chat.

Existing bookmarks keep their canonical path and pinned release; their storage format is unchanged. Saved links, copied source citations and answer exports use canonical law URLs and retain law-specific source editions. Browser tests also cover old Constitution bookmarks.

Landing, navigation, footer, FAQ and SEO copy now refer to the Constitution and published laws while preserving the constitution.ng brand and project design tokens. The landing page names the laws actually available in the published release. About/FAQ copy distinguishes published sources from laws under review. The methodology page distinguishes the original 55-case recorded run from the expanded 57-case downloadable dataset.

The Cloudflare public renderer serves new law hubs and detail URLs, including readable wording and law-specific metadata before JavaScript. Legacy URLs remain supported. The sitemap obtains the published instrument list, fetches each instrument's complete index pinned to that same release and rejects incomplete or mismatched responses. It cannot discover private draft instruments through the catalog. The browser bootstrap cache now includes the tree's instrument scope. No hosting deployment was performed.

## Validation

- Backend: **627 passed, 4 skipped**, **89% coverage**. Mypy, ty, Ruff lint and formatting passed. Seven new backend cases cover published membership/counts, retired releases, filtered trees, explicit-reference precedence, lexical fallback, dense/hybrid filtering before limits and invalid slugs. The dedicated `_test` database was used.
- Frontend production build and Biome passed. The API client was generated with `bash scripts/generate-client.sh`; TanStack routes were generated with `tsr generate`.
- The affected Playwright suite covers admin, legal-home, chat-home and the new laws flows, on desktop and mobile. The complete suite passed **58 tests**, with no automatic retries. All **23 affected Browse/Find and reading tests** also passed after the final bare-number consistency fix. Results are recorded in [the validation summary](statute-phase6-validation-2026-10-20.json). Earlier attempts exposed stale assertions for the intentionally changed breadcrumb and saved-link URLs; those assertions were updated. Legacy input URLs remain explicitly tested.
- Cloudflare public-render/proxy tests: **21 passed**; Worker TypeScript check passed. Act text, metadata, canonical links, sitemap inclusion and wrong-law/unpublished-law 404/noindex behavior are exercised with synthetic API responses.
- All **97 Constitution retrieval results** match Phase 5 exactly, including individual ranking signals and misses. The fourteen real-statute cases remain explicitly blocked because the Acts are absent from the active release. [Retrieval comparison](statute-phase6-retrieval-validation-2026-10-20.json).
- The read-only preflight confirms that only `constitution-1999` appears in the actual public instrument list. The active release remains `draft-c8d50d87fae9`, with **1,829 segments and 1,829 embeddings**, a valid index and unchanged stored checksums. Both Act sources have zero materialised versions and no approved member releases. [Preflight evidence](statute-phase6-local-preflight-2026-10-20.json).

Desktop and mobile screenshots were visually inspected, then removed at the user's request on 20 October 2026. All Act UI fixtures explicitly use synthetic wording; these checks establish presentation and routing behavior, not legal accuracy or approval of the real documents. Query-embedding calls were used by the existing retrieval benchmark. No live language-model calls, source approvals, publication actions, deployment, dependency changes or lockfile changes were performed.

Phase 7 evaluation and rollout still require verified source/amendment metadata, corrected and approved extraction, passing full-PDF acceptance checks, a validated composite release, fresh live answer captures and human grounding review. Infrastructure readiness does not clear those gates.
