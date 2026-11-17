# Render deployment files

The production API runs on Render. The operating procedure is in
[`docs/runbooks/render.md`](../../docs/runbooks/render.md), and every production
setting is in [`render.yaml`](../../render.yaml).

| File | Purpose |
| --- | --- |
| `Dockerfile` | Production image: locked dependencies, computed source revision, unprivileged user. |
| `start.sh` | Starts one Uvicorn process for `app.deployment.render_app:app`. |
| `prepare_env.py` | Combines private credential bundles into the ignored `deployment/render.env` for import into Render. |
| `sync_spend.py` | Carries spend from an isolated evaluation database into the production ledger. |
| `backup-*.sh`, `backup_tools.py`, `backup-lifecycle.s3.json`, `backup-workflow.yml` | Database backup and restore verification; see [`docs/runbooks/backup-restore.md`](../../docs/runbooks/backup-restore.md). |

Set the private backup repository variables `R2_BACKUP_BUCKET` and
`EXPECTED_NEON_HOST` to the authorized bucket and database hostname before
running its workflow. The database URL remains a secret.
