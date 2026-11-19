# Frontend

React and TypeScript client for constitution.ng, built with Vite, TanStack
Router and Query, Tailwind CSS and typed i18next catalogues.

| Path              | What it holds                                                                                             |
| ----------------- | --------------------------------------------------------------------------------------------------------- |
| `src/routes/`     | File-based routes; `src/routeTree.gen.ts` is generated.                                                   |
| `src/components/` | UI components; `Constitution/` holds the reader, chat and legal-admin screens.                            |
| `src/lib/`        | Session handling, SEO metadata, public content and shared helpers.                                        |
| `src/locales/`    | Interface catalogues per reader language.                                                                 |
| `src/client/`     | API client generated from the backend's OpenAPI schema.                                                   |
| `tests/`          | Playwright specs; `tests/fixtures/` and `tests/admin/` hold API mocks typed against the generated client. |

Run these from the repository root:

```bash
bun install          # install workspace dependencies
bun run dev          # Vite on http://localhost:5173, API from frontend/.env
bun run lint         # Biome, check only (bun run lint:fix applies safe fixes)
bun run build        # type-check application sources and build into backend/app/frontend
bun run typecheck    # type-check including the browser tests
bun run test:mocked  # Playwright specs that stub the API; no backend needed
bun run test         # Playwright specs that need the real API (login, sign-up, password reset) on the Compose stack
bun run test:cross-engine  # the mocked specs in Firefox and WebKit; run by hand after layout changes
```

Regenerate the API client with `bash scripts/generate-client.sh`; never edit
`src/client/` or `src/routeTree.gen.ts` by hand. Design tokens are in
`src/index.css`. See the [README](../README.md) and
[`docs/development.md`](../docs/development.md) for the rest of the setup.

## Server state

`src/lib/query-client.ts` sets the defaults every query inherits: a minute of
freshness, no refetch when the window regains focus, and one retry that is
skipped for client errors. Queries that need otherwise say so.

- **Legal text** read under a named release is cached for the life of the page
  (`staleTime: Infinity`); without a release it is re-read every five minutes.
- **Search** costs an embedding and sometimes a translation, so a result is
  never refreshed by itself.
- **Legal operations** (`/admin`) follows the pipeline through
  `src/lib/admin-queries.ts`. Metrics and alerts are followed while the tab is
  shown; every other query polls only while its screen is open and the pipeline
  has work in progress. Each doubles its wait for every poll that returns the
  same data. The run's event stream refreshes the selected run, and a write
  refreshes only the queries it can change.
- **Answers** are checked against the schema in `src/lib/answer.ts` before they
  are rendered, and each answer sits in an error boundary.
