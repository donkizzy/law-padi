# Published Constitution integration

Implemented and verified on 6 October 2026. Home, Browse, Provision Detail, and Saved now read the published Constitution through the generated OpenAPI client and TanStack Query.

## User behavior

- A single exact reference opens its stored wording immediately. Supported forms include `Section 33`, `Section 33(2)`, `Section 33(2)(a)`, `s.33(2)(a)`, `§33(2)(a)`, and explicit subsection/paragraph wording. A reference inside a question is resolved deterministically.
- Topic searches show ranked choices. Selecting a choice opens its wording, ancestor context, children, and source evidence. Scores are ordering signals and are not displayed as confidence percentages.
- Missing references are not replaced with semantic guesses. Multiple or unsupported references receive an explicit message. Section 168 remains missing; Section 189 offers the two stored source identities, distinguished by chapter, part, and page.
- Full citations come from stored ancestry. Paragraph wording is displayed separately from collapsible parent context. Direct section paragraphs remain supported, and Roman clauses stay inside their paragraph text.
- Copy includes actual wording, citation, edition, authority, document, page range, and release. Share copies a detail URL pinned to canonical path and release version. Save stores the same identity in this browser. Clipboard/storage errors are reported; unreadable bookmark data is retained.
- Stored version history contains only published editions. An explicit message explains when no additional version is stored. Related provisions uses the enclosing section heading as a semantic query.
- The source panel links to the original PDF at its recorded page. The mobile sheet traps focus, dismisses with Escape, and restores the opener's focus.
- English is the supported language. Translation, proposed-change cards, and mock conversation history are hidden. New clears the search. AI explanations, account bookmarks, and persistent conversations remain future work.

## API contract

All paths below are under `/api/v1/legal`.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/search` | Exact reference first; otherwise dense + lexical retrieval. `mode: "semantic"` explicitly bypasses reference lookup for related searches. |
| GET | `/releases/current` | Active published release, edition, legal statuses, availability, and index identity. |
| GET | `/provisions/tree` | Ordered roots or children selected by `parent_path`. |
| GET | `/provisions/{canonical_path}` | Canonical stored text, full citation, source evidence, ancestor context, and children. |
| GET | `/provision-history` | Distinct stored versions from published releases, selected by `canonical_path`. |
| GET | `/sources/{source_document_id}/content` | Original PDF only when it belongs to the selected published corpus. |

Provision, tree, history, and source reads accept `release_version`. Omission selects the active target. Previously published retired releases remain readable for stable bookmarks; draft and unpublished releases return 404. Tree is registered before the catch-all provision route.

Search responses retain the existing result fields and add `outcome`, `retrieval_mode`, `message`, edition/release identifiers, provision/version identifiers, complete citations, source metadata, ancestry, and children. Outcomes are `exact`, `matches`, `ambiguous`, `not_found`, and `unsupported_reference`.

Exact lookup reads release entries and canonical versions independently of embedding providers. Semantic search embeds only the incoming query with the selected profile, reuses the saved corpus vectors, deduplicates by provision version before limiting, and reloads wording from `ProvisionVersion`. Provider errors yield keyword results with `retrieval_mode: "lexical"` and an explicit fallback message. Missing publication/index state and database unavailability return 503; missing identities return a lookup outcome or 404 as appropriate.

## Verified release and rollout

The local app is available at `http://localhost:8000/`. The release was already production when checked; no Validate/Publish bypass or publication mutation was performed. The existing review and actor-separation workflow remains in force for future releases.

| Item | Verified value |
| --- | --- |
| Release | `draft-c8d50d87fae9` (status `production`; the version name is an immutable ingestion identifier) |
| Edition | Historical/source Constitution compilation (LFN 2004) |
| Public hierarchy | 1,850 provision identities, including structural ancestors |
| Stored text versions | 1,811, all labelled historical |
| Saved retrieval index | 1,829 segments and 1,829 vectors, 1,024 dimensions |
| Active embedding run | `28ec1c64-ee69-41cd-840e-b63b4c71463b` |
| Active index build | `3333d1fb-0437-420a-82a6-8bc3bb261b10` |

The historical label is visible on Home, selected wording, detail pages, saved cards, and source evidence. Publication of this source edition does not certify a current consolidated Constitution. Source anomalies, original wording, index text, embeddings, and the original PDF are preserved.

## Validation

- 131 backend tests passed across legal API/reference/parser, retrieval/structure, embedding/worker, and admin ingestion suites. The final legal API/reference/parser subset was rerun after the last backend change: 35 passed.
- 23 Chromium Playwright tests passed: 9 public integration cases covering desktop/mobile workflows, ambiguity/missing/unsupported references, fallback/unavailability, cancellation, browse/detail, bookmark persistence, filtering, and browser failures; 14 existing admin cases also passed.
- Backend mypy, ty, Ruff, frontend Biome, and the production frontend build passed. The OpenAPI client was regenerated through `scripts/generate-client.sh`.
- Tests used a disposable database, never the retained corpus database. No new dependencies, migrations, or lockfile changes were required.
- The retained 50-query benchmark was replayed using stored query vectors: Recall@10 **0.98**, nDCG@10 **0.977246**. No corpus or benchmark-query embeddings were regenerated.
- Read-only index validation confirmed counts, dimensions, and checksums. Hybrid smoke queries covered the right to life, freedom of expression, and Judicial Oath, with ten distinct provision versions per result list.
- A live browser check exercised exact lookup, desktop/mobile source panels, original PDF access (HTTP 200), save/reload/detail, and live hybrid topic search, with no browser errors. The original PDF SHA-256 remained unchanged.

Machine-readable retained-corpus evidence is in [public-corpus-integration-evidence-2026-10-06.json](public-corpus-integration-evidence-2026-10-06.json).
