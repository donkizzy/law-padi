#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
bun install --frozen-lockfile
revision=$(python3 scripts/build_revision.py)
export VITE_API_URL=''
export VITE_PUBLIC_SITE_URL="${PUBLIC_SITE_URL:-https://constitition-ng.amosgodwin500.workers.dev}"
export VITE_BUILD_REVISION="$revision"
bun run --filter frontend build

# Keep the initial build private. Enable this only after the current AI review.
case "${CLOUDFLARE_PUBLIC_LAUNCH:-false}" in
  false) python3 deployment/cloudflare/prepare.py --revision "$revision" --site-url "$VITE_PUBLIC_SITE_URL" ;;
  true) python3 deployment/cloudflare/prepare.py --revision "$revision" --site-url "$VITE_PUBLIC_SITE_URL" --public ;;
  *) echo 'CLOUDFLARE_PUBLIC_LAUNCH must be true or false' >&2; exit 1 ;;
esac
