# Observability runbook

How to follow a request through the API, the chat worker and the ingestion
worker, and what the health probes mean.

## Request IDs

Every API response carries an `X-Request-ID` header. A caller may send its own
`X-Request-ID`; it is kept only when it is 1 to 64 characters of letters,
digits, `.`, `_` and `-`, starting with a letter or digit. Anything else is
replaced by a generated 32-character identifier.

The identifier is:

- on every log line written while the request is handled (`request_id`);
- a Sentry tag on any error reported for the request;
- stored on the chat run the request created (`generation_run.request_id`),
  and bound to every log line the chat worker writes for that run, together
  with `run_id`.

To investigate a failed explanation, take the request ID from the reader's
browser (network tab, response headers) or from an error response, then
search the logs for it. The worker's lines for the run share the same
`request_id`; `run_id` links them to the database row.

An unexpected server error returns:

```json
{"detail": "Internal Server Error", "code": "internal_error", "request_id": "…"}
```

and is logged once as `unhandled_exception` with the request ID, the route
template and the error type. Errors the application expects (validation,
authentication, rate limits, domain errors) keep their `{detail, code}` shape.

## Logs

The API, the chat worker and the ingestion worker share one configuration
(`app/core/logs.py`).

| Setting | Effect |
| --- | --- |
| `LOG_FORMAT=json` | One JSON object per line. The default outside development. |
| `LOG_FORMAT=text` | `timestamp level logger message key=value …`. The default when `FASTAPI_ENV=development`. |
| `LOG_LEVEL` | `DEBUG`, `INFO` (default), `WARNING` or `ERROR`. The ingestion worker also honours `INGESTION_WORKER_LOG_LEVEL`. |

Each JSON line has `timestamp` (UTC), `level`, `logger`, `message`, and
`request_id`, `run_id` or `task_id` when known, followed by the fields the call
site supplies. Exceptions are kept in an `exception` field, so a traceback stays
on one line. Uvicorn's server and access lines use the same format.

Logs never contain secrets, email addresses or a reader's question text. Log
identifiers, counts, outcomes and error types instead; a test on the chat path
enforces this for the question. As a backstop, the shared handler replaces any
email address in a message with `[email]`; this covers Uvicorn's access line
for password recovery, whose path holds the address.

## Sentry

Error reporting is off unless `SENTRY_DSN` is set, and is always off with
`FASTAPI_ENV=development`. When on:

- `release` is `BUILD_REVISION` and `environment` is `SENTRY_ENVIRONMENT`
  (default `production`);
- the API, the standalone chat worker and the Render runtime report; the
  ingestion worker image does not include the Sentry SDK;
- request bodies and cookies are never sent, frame local variables are not
  collected, and fields named like `email`, `question`, `password`, `token` or
  `secret` are replaced by `[Filtered]` anywhere in an event. Email addresses
  in URLs and messages are filtered too.

## Health probes

| Path | Checks | Use |
| --- | --- | --- |
| `/livez` | Nothing beyond the process answering; on Render also that the in-process chat worker is running. No I/O. | Restart decisions. |
| `/healthz` | Same as `/livez`. | Render's `healthCheckPath`. |
| `/readyz` | The database answers within 3 seconds, and its Alembic revision is this build's head (cached once seen). | Routing decisions; the Compose `backend` health check, which Traefik follows. |
| `/api/v1/utils/health-check/` | Unchanged: database and the `vector` extension. | Existing scripts and CI. |

`/healthz` deliberately does not touch the database. Render restarts a service
or holds back a deploy when its health check fails; a restart cannot fix a
database outage or a pending migration, and a database probe on every check
would keep a suspended Neon database awake. On Render, `/readyz` sits behind
the origin credential like the rest of the API.

`/readyz` answers `503` with a `reason` of `database_unavailable`,
`database_timeout` or `migrations_pending`. After a deploy, `migrations_pending`
means the release migrations have not run yet; see [`release.md`](release.md).

## Worker heartbeats (Compose)

The chat and ingestion workers touch a heartbeat file on every loop iteration,
including idle polls; the ingestion worker also touches it after each task and
at each stage checkpoint (pages, embedding batches). The Compose health check
runs:

```sh
python -m app.core.heartbeat <file> --interval <poll seconds> --intervals <N>
```

and fails when the file is missing or older than N poll intervals:

| Service | File | Poll interval | N (variable, default) | Stale after |
| --- | --- | --- | --- | --- |
| `chat-worker` | `/tmp/chat-worker.heartbeat` | 2 s | `CHAT_WORKER_HEARTBEAT_INTERVALS`, 30 | 60 s |
| `ingestion-worker` | `/tmp/ingestion-worker.heartbeat` | `INGESTION_WORKER_POLL_INTERVAL_SECONDS`, 5 s | `INGESTION_WORKER_HEARTBEAT_INTERVALS`, 60 | 5 min |

A stage step that runs longer than the ingestion threshold without a
checkpoint, such as a slow managed OCR call, can mark the worker unhealthy while
it is still working; raise `INGESTION_WORKER_HEARTBEAT_INTERVALS` if that is
expected. Docker marks a stale worker `unhealthy` in `docker compose ps`; it
does not restart it. Check the worker's last log lines, then
`docker compose restart <service>`. Leases return any interrupted task or run
to the queue.

On Render the chat worker runs inside the API process; `/livez` covers it and no
heartbeat file is written.
