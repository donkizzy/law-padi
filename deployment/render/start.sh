#!/bin/sh
set -eu
if [ -f /app/source-revision ]; then
  BUILD_REVISION=$(cat /app/source-revision)
  export BUILD_REVISION
fi
case "${PORT:-10000}" in
  ''|*[!0-9]*) echo "PORT must be an integer" >&2; exit 1 ;;
esac
exec uvicorn app.deployment.render_app:app --host 0.0.0.0 \
  --port "${PORT:-10000}" --workers 1 --proxy-headers \
  --forwarded-allow-ips='*' --timeout-graceful-shutdown 10 --no-access-log
