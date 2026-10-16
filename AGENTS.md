# Repository Guidelines

## Product Context

Read `PROJECT_CONTEXT.md` before making product, schema, retrieval, ingestion, or UI changes. It captures the Nigerian Constitution RAG architecture and schema plan distilled from the project chat export.

## Project Structure & Module Organization

`backend/app/` contains the FastAPI application: routes are in `api/routes/`, SQLModel entities in `models.py`, database operations in `crud.py`, and migrations in `alembic/versions/`. Tests mirror these areas under `backend/tests/`. The React/TypeScript client is in `frontend/src/`, organized into `routes/`, `components/`, `hooks/`, and `lib/`; browser tests are in `frontend/tests/`, and static assets in `frontend/public/`. Email sources live in `packages/react-email/`; do not manually edit generated HTML in `backend/app/email-templates/`.

## Build, Test, and Development Commands

Run frontend commands from the repository root and backend commands from `backend/` unless noted.

- `docker compose up -d db mailpit` starts local PostgreSQL and email capture services.
- `cd backend && uv sync && uv run bash scripts/prestart.sh` installs dependencies and applies migrations.
- `cd backend && uv run fastapi dev` serves the API at `http://localhost:8000`.
- `bun install && bun run dev` installs workspace dependencies and starts Vite at `http://localhost:5173`.
- `bun run build` type-checks and builds the frontend.
- `bun run lint` runs Biome; `cd backend && uv run bash scripts/lint.sh` runs mypy, ty, and Ruff checks.
- `cd backend && uv run bash scripts/test.sh` runs Pytest with coverage; `bun run test` runs Playwright against the full stack.

## Coding Style & Naming Conventions

Python uses four-space indentation, type annotations, `snake_case` functions/modules, and `PascalCase` classes. Ruff handles formatting/import order; mypy is strict. TypeScript uses Biome with spaces, double quotes, and semicolons only when needed. Name React components/files in `PascalCase`, hooks as `useThing`, and routes in lowercase kebab case. Do not edit `frontend/src/client/` or `frontend/src/routeTree.gen.ts`; regenerate them with `bash scripts/generate-client.sh`.

The project's design system (tokens in `frontend/src/index.css`, the constitution.ng brand kit, and the design system canvas) takes priority over any external design skill, including `landing-page-design`. Use those skills for structure and copy guidance only; never override project fonts, type sizes, spacing, radii, or colors with their values.

## Testing Guidelines

Name backend tests `test_*.py` and Playwright cases `*.spec.ts`. Add regression coverage for behavior changes and keep helpers in existing `tests/utils/` locations. Backend tests produce `htmlcov/index.html`; no minimum threshold is configured. Playwright requires the backend and Compose services.

## Commit & Pull Request Guidelines

History currently contains only an initial commit, so no mature commit convention exists. Use short, imperative subjects, optionally scoped (for example, `backend: validate reset tokens`). Keep pull requests focused, explain user-visible impact, link related issues, and include screenshots for UI changes. Confirm relevant tests and linters pass. Discuss architectural changes or new dependencies before opening a PR; contributors should not modify dependency lockfiles casually.

## Security & Configuration

Copy the tracked `.env.example` to the ignored `.env` for local configuration. Never commit credentials; configure deployment secrets through the documented deployment environment.
