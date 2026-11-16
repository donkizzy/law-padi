# Frontend

React and TypeScript client for constitution.ng, built with Vite, TanStack
Router and Query, Tailwind CSS and typed i18next catalogues.

| Path | What it holds |
| --- | --- |
| `src/routes/` | File-based routes; `src/routeTree.gen.ts` is generated. |
| `src/components/` | UI components. `LawPadi/` carries the product's former name. |
| `src/lib/` | Session handling, SEO metadata, public content and shared helpers. |
| `src/locales/` | Interface catalogues per reader language. |
| `src/client/` | API client generated from the backend's OpenAPI schema. |
| `tests/` | Playwright specs. |

Run these from the repository root:

```bash
bun install          # install workspace dependencies
bun run dev          # Vite on http://localhost:5173, API from frontend/.env
bun run lint         # Biome, check only (bun run lint:fix applies safe fixes)
bun run build        # type-check application sources and build into backend/app/frontend
bun run typecheck    # type-check including tests (not yet run in CI)
bun run test         # Playwright against the Compose stack
```

Regenerate the API client with `bash scripts/generate-client.sh`; never edit
`src/client/` or `src/routeTree.gen.ts` by hand. Design tokens are in
`src/index.css`. See the [README](../README.md) and
[`docs/development.md`](../docs/development.md) for the rest of the setup.
