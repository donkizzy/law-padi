#!/bin/sh
# Entry point for the Railway application services.
#
#   run.sh api
#       One Uvicorn process for app.main:app on $PORT.
#   run.sh worker HEARTBEAT_FILE POLL_SECONDS INTERVALS -- COMMAND [ARGS...]
#       Runs COMMAND and restarts the container when its heartbeat goes stale.
#
# Railway's health check only gates the start of a deploy and cannot run a
# command, so it cannot see a worker loop that hangs while its process stays
# up. The worker mode runs the same check the Compose health check runs
# (python -m app.core.heartbeat) and, once the heartbeat is older than
# INTERVALS poll intervals, stops COMMAND and exits non-zero; Railway's
# restart policy then starts a fresh container. Leases return any task or run
# the stopped worker held.
#
# Worker settings (environment):
#   WORKER_ENABLED=false     exit 0 at once, so the service stays stopped
#                            under an ON_FAILURE restart policy
#   WORKER_STOP_TIMEOUT=30   seconds to wait after that signal before SIGKILL
set -eu

if [ -f /app/source-revision ]; then
  BUILD_REVISION=$(cat /app/source-revision)
  export BUILD_REVISION
fi

log() {
  # One JSON line, matching the services' LOG_FORMAT=json output.
  printf '{"timestamp":"%s","level":"%s","logger":"railway.run","message":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >&2
}

is_number() {
  case "$1" in
    '' | *[!0-9.]* | *.*.*) return 1 ;;
    *) return 0 ;;
  esac
}

run_api() {
  port=${PORT:-8000}
  case "$port" in
    '' | *[!0-9]*) log ERROR "PORT must be an integer"; exit 64 ;;
  esac
  # One process: the chat worker runs as its own service. The Worker and
  # Railway's edge are the only callers, so forwarded headers are trusted;
  # the per-address limits read the Worker's own header (app/core/rate_limit.py).
  exec uvicorn app.main:app --host 0.0.0.0 --port "$port" --workers 1 \
    --proxy-headers --forwarded-allow-ips '*' \
    --timeout-graceful-shutdown 10 --no-access-log
}

run_worker() {
  if [ "$#" -lt 5 ] || [ "$4" != "--" ]; then
    log ERROR "usage: run.sh worker HEARTBEAT_FILE POLL_SECONDS INTERVALS -- COMMAND"
    exit 64
  fi
  heartbeat=$1
  interval=$2
  intervals=$3
  shift 4
  if ! is_number "$interval" || ! is_number "$intervals"; then
    log ERROR "POLL_SECONDS and INTERVALS must be numbers"
    exit 64
  fi
  if [ "${WORKER_ENABLED:-true}" = false ]; then
    log INFO "worker_disabled"
    exit 0
  fi
  stop_timeout=${WORKER_STOP_TIMEOUT:-30}
  # The same threshold app.core.heartbeat applies: a one-second floor on the
  # poll interval, times the number of intervals.
  stale=$(awk -v i="$interval" -v n="$intervals" \
    'BEGIN { if (i < 1) i = 1; printf "%d", i * n + 0.999 }')
  check_every=30
  rm -f "$heartbeat"

  "$@" &
  child=$!
  stop_requested=
  on_stop() {
    if [ -z "$stop_requested" ]; then
      stop_requested=$(date +%s)
      kill -s TERM "$child" 2>/dev/null || true
    fi
  }
  trap on_stop TERM INT

  started=$(date +%s)
  last_check=$started
  while kill -0 "$child" 2>/dev/null; do
    # A short, interruptible sleep: a stop signal ends the wait at once, and
    # a child that exits is noticed within a few seconds.
    sleep 1 &
    wait $! 2>/dev/null || true
    now=$(date +%s)
    if [ -n "$stop_requested" ]; then
      if [ $((now - stop_requested)) -ge "$stop_timeout" ]; then
        kill -s KILL "$child" 2>/dev/null || true
      fi
      continue
    fi
    if [ $((now - started)) -lt "$stale" ] ||
      [ $((now - last_check)) -lt "$check_every" ]; then
      continue
    fi
    last_check=$now
    if kill -0 "$child" 2>/dev/null &&
      ! python -m app.core.heartbeat "$heartbeat" --interval "$interval" \
        --intervals "$intervals" >/dev/null 2>&1; then
      log ERROR "worker_heartbeat_stale"
      on_stop
      stale_exit=true
    fi
  done
  status=0
  wait "$child" || status=$?
  if [ "${stale_exit:-false}" = true ]; then
    exit 70
  fi
  if [ -z "$stop_requested" ]; then
    log ERROR "worker_exited"
  fi
  exit "$status"
}

case "${1:-}" in
  api) run_api ;;
  worker) shift; run_worker "$@" ;;
  *) log ERROR "usage: run.sh api | run.sh worker ..."; exit 64 ;;
esac
