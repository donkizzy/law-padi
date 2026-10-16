#! /usr/bin/env bash

set -e
set -x

cd backend
FASTAPI_ENV=development uv run --frozen python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/
bun run --filter frontend generate-client
find frontend/src/client -type f -name '*.ts' -exec perl -pi -e 's/[[:blank:]]+$//' {} +
cd frontend
bunx biome format --write --no-errors-on-unmatched src/client
