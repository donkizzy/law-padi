#!/bin/sh
set -eu

APP_RUNTIME_ROLE="${APP_RUNTIME_ROLE:-api}"
export APP_RUNTIME_ROLE
case "$APP_RUNTIME_ROLE" in
  api) app_module=app.main:app ;;
  tasks) app_module=app.deployment.worker_app:app ;;
  *) echo "APP_RUNTIME_ROLE must be api or tasks" >&2; exit 1 ;;
esac
case "${PORT:-8080}" in
  ''|*[!0-9]*) echo "PORT must be an integer" >&2; exit 1 ;;
esac
# Await task execution inside the request. There is no polling process or
# detached background worker in this runtime.
exec uvicorn "$app_module" --host 0.0.0.0 --port "${PORT:-8080}" \
  --workers 1 --proxy-headers --forwarded-allow-ips='*' \
  --timeout-graceful-shutdown 10 --no-access-log
