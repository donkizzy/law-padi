# Contributing

constitution.ng lets people ask about Nigerian law in plain language and read the matching sections of the Constitution and other statutes, quoted with exact citations. The backend is FastAPI with PostgreSQL and pgvector retrieval; the frontend is React and TypeScript.

Read [AGENTS.md](AGENTS.md) first. It has the repository layout, the setup and run commands, and the coding conventions. [docs/architecture.md](docs/architecture.md) explains the product and the retrieval design, and you should read it before changing schema, retrieval, ingestion or the UI.

## Set up

Follow the commands under "Build, Test, and Development Commands" in `AGENTS.md`: start the database and mail capture with Docker Compose, run `uv sync` and the prestart script in `backend/`, then `bun install` at the root. Copy `.env.example` to `.env` and `frontend/.env.example` to `frontend/.env` for local settings, and never commit credentials. [docs/development.md](docs/development.md) covers the workers and the full Compose stack.

## Check your work

Run these before you open a pull request.

| What | Command |
| --- | --- |
| Frontend lint (check only) | `bun run lint` |
| Apply safe frontend fixes | `bun run lint:fix` |
| Frontend type-check and build | `bun run build` |
| Type-check the frontend including tests (not yet run in CI) | `bun run typecheck` |
| Backend types and style | `cd backend && uv run bash scripts/lint.sh` |
| Apply backend fixes | `cd backend && uv run ruff check --fix app && uv run ruff format app` |
| Backend tests with coverage | `cd backend && uv run bash scripts/test.sh` |
| Browser tests (need the full stack) | `bun run test` |
| Git hooks, on staged files | `uv run prek run` |

Install the hooks once with `uv run prek install -f`. They only report problems; they do not rewrite your code, apart from trailing whitespace and end-of-file fixes. Fix problems with the commands above.

Do not edit `frontend/src/client/`, `frontend/src/routeTree.gen.ts` or `backend/app/email-templates/` by hand. Regenerate the client with `bash scripts/generate-client.sh`.

## What CI runs

Every pull request runs these workflows, and all of them should pass before merge.

- **pre-commit**: the hooks above over the files the pull request changes, including Biome, Ruff, mypy, ty, a check that the generated frontend client is current, and zizmor.
- **Test Backend**: mypy, ty and Ruff on `backend/app`, the Pytest suite against a real PostgreSQL with an 87% floor (branch coverage), and the deployment helper tests. OCR and PDF rendering tests run with `tesseract-ocr` and `poppler-utils` installed.
- **Render CI**: the Biome check, the same-origin frontend build, the Cloudflare Worker and public page tests, and a build and smoke test of the packaged production image.
- **Playwright Tests**: the browser suite in four shards against the Compose stack. It runs when backend, frontend, packages, scripts, Compose files, lockfiles or the workflow itself change.
- **Test Docker Compose**: builds the stack and checks that the backend, frontend and Adminer start.
- **Zizmor**: static analysis of the workflow files.
- **Guard Dependencies** and **Conflict detector**: close pull requests from non-maintainers that change dependency files, and label pull requests that have merge conflicts.

A new push to a branch cancels the previous run of the same workflow on it.

The job names that must pass before a pull request merges into `master`, and the branch rules around them, are in [docs/runbooks/branch-protection.md](docs/runbooks/branch-protection.md).

## Commits and pull requests

- Write short, imperative subjects, optionally scoped, for example `backend: validate reset tokens`. Group related changes into focused commits.
- Keep pull requests focused and say what changes for users. Link related issues and include screenshots for UI changes.
- Add regression tests for behaviour changes, in the existing `tests/` folders.
- Discuss architectural changes and new dependencies in an issue before opening a pull request. Only maintainers change dependency manifests and lockfiles; open an issue if you need a dependency.
