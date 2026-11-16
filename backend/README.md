# Backend

FastAPI application, domain logic, workers and migrations for constitution.ng.
Python 3.14, managed with [uv](https://docs.astral.sh/uv/).

| Path | What it holds |
| --- | --- |
| `app/api/routes/` | HTTP routes: public legal reads (`search.py`), conversations, accounts, admin. |
| `app/legal/` | References, parsers, evidence assembly, public corpus reads, topic guide, domain models. |
| `app/chat/` | Generation worker, answer validation, translation, spend ledger, SSE events. |
| `app/ingestion/` | Ingestion pipeline: storage, extraction, OCR, review workflow, embeddings, pgvector index, releases. |
| `app/languages/` | Reader-language detection, normalisation and glossaries. |
| `app/core/` | Settings, database engine, security, sessions, rate limits. |
| `app/deployment/render_app.py` | Single-process runtime used on Render. |
| `app/alembic/versions/` | Migrations. |
| `scripts/` | Test runner, lint, prestart, evaluation and operator scripts. |
| `tests/` | Pytest suite against a real PostgreSQL test database. |

Common commands, run from this directory:

```bash
uv sync                          # install dependencies
uv run bash scripts/prestart.sh  # migrate and create the first superuser
uv run fastapi dev               # serve the API on http://localhost:8000
uv run bash scripts/lint.sh      # mypy, ty and Ruff checks
uv run bash scripts/test.sh      # Pytest with coverage on a *_test database
```

See the [README](../README.md) for setup, [`docs/architecture.md`](../docs/architecture.md)
for how the pieces fit, and [`docs/development.md`](../docs/development.md) for
workers, Compose and tests.
