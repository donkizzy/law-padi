# Render deployment files

> **Being retired.** The API and database are moving to Railway
> ([ADR 0007](../../docs/adr/0007-railway-api-and-database-hosting.md), [migration runbook](../../docs/runbooks/railway-migration.md)). This stays in
> place until the migration's rollback window ends, then is removed as the
> runbook's last step lists.

The production API runs on Render. The operating procedure is in
[`docs/runbooks/render.md`](../../docs/runbooks/render.md), and every production
setting is in [`render.yaml`](../../render.yaml).

| File | Purpose |
| --- | --- |
| `Dockerfile` | Production image: locked dependencies, computed source revision, unprivileged user. |
| `start.sh` | Starts one Uvicorn process for `app.deployment.render_app:app`. |
| `prepare_env.py` | Combines private credential bundles into the ignored `deployment/render.env` for import into Render. |
| `sync_spend.py` | Carries spend from an isolated evaluation database into the production ledger. |

The database backup scripts moved to [`deployment/backup/`](../backup/); see
[`docs/runbooks/backup-restore.md`](../../docs/runbooks/backup-restore.md).
`sync_spend.py` is not specific to Render; move it before deleting this
directory.
