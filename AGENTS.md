# Repository Guidelines

## Product Context

Read `docs/architecture.md` before making product, schema, retrieval, ingestion, or UI changes. It describes the components, data model, ingestion and answer pipelines, release model and deployment. Decision records are in `docs/adr/`, operating procedures in `docs/runbooks/`.

## Project Structure & Module Organization

`backend/app/` contains the FastAPI application: routes are in `api/routes/`, SQLModel entities in `models.py`, database operations in `crud.py`, and migrations in `alembic/versions/`. Tests mirror these areas under `backend/tests/`. The React/TypeScript client is in `frontend/src/`, organized into `routes/`, `components/`, `hooks/`, and `lib/`; browser tests are in `frontend/tests/`, and static assets in `frontend/public/`. Email sources live in `packages/react-email/`; do not manually edit generated HTML in `backend/app/email-templates/`.

## Build, Test, and Development Commands

Run frontend commands from the repository root and backend commands from `backend/` unless noted.

- `docker compose up -d db mailpit` starts local PostgreSQL and email capture services.
- `cd backend && uv sync && uv run bash scripts/prestart.sh` installs dependencies and applies migrations.
- `cd backend && uv run fastapi dev` serves the API at `http://localhost:8000`.
- `bun install && bun run dev` installs workspace dependencies and starts Vite at `http://localhost:5173`.
- `bun run build` type-checks the application sources and builds the frontend.
- `bun run lint` runs Biome in check-only mode; `bun run lint:fix` applies its safe fixes. `cd backend && uv run bash scripts/lint.sh` runs mypy, ty, and Ruff checks.
- `bun run typecheck` type-checks the whole frontend project, including the browser tests; CI gates pull requests on it.
- `cd backend && uv run bash scripts/test.sh` runs Pytest with coverage; `bun run test:mocked` runs the browser specs that mock the API (no backend needed); `bun run test` runs the specs that need the backend and Compose services.

## Coding Style & Naming Conventions

Python uses four-space indentation, type annotations, `snake_case` functions/modules, and `PascalCase` classes. Ruff handles formatting/import order; mypy is strict. TypeScript uses Biome with spaces, double quotes, and semicolons only when needed. Name React components/files in `PascalCase`, hooks as `useThing`, and routes in lowercase kebab case. Do not edit `frontend/src/client/` or `frontend/src/routeTree.gen.ts`; regenerate them with `bash scripts/generate-client.sh`.

The project's design system (tokens in `frontend/src/index.css`, the constitution.ng brand kit, and the design system canvas) takes priority over any external design skill, including `landing-page-design`. Use those skills for structure and copy guidance only; never override project fonts, type sizes, spacing, radii, or colors with their values.

## Testing Guidelines

Name backend tests `test_*.py` and Playwright cases `*.spec.ts`. Add regression coverage for behavior changes and keep helpers in existing `tests/utils/` locations. Backend tests produce `htmlcov/index.html`; CI enforces an 87% floor with branch coverage on `backend/app`. `bun run test` requires the backend and Compose services; `bun run test:mocked` does not. Type browser-test API mocks against the generated client.

## Commit & Pull Request Guidelines

Use short, imperative subjects, optionally scoped (for example, `backend: validate reset tokens`). Group significant related changes into focused commits. Keep pull requests focused, explain user-visible impact, link related issues, and include screenshots for UI changes. Confirm relevant tests and linters pass. Discuss architectural changes or new dependencies before opening a PR; contributors should not modify dependency lockfiles casually.

## Security & Configuration

Copy the tracked `.env.example` to the ignored `.env` for local configuration. Never commit credentials; configure deployment secrets through the documented deployment environment.
