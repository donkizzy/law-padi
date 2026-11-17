#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/backup-common.sh"

: "${RESTORE_BACKUP_KEY:?Choose an exact private dump key for restore verification}"
python3 "$tools_py" key "$RESTORE_BACKUP_KEY"
aws_r2 s3api get-object --bucket "$R2_BACKUP_BUCKET" --key "$RESTORE_BACKUP_KEY.json" "$backup_work/manifest.json" >"$backup_work/manifest-download.json"
aws_r2 s3api head-object --bucket "$R2_BACKUP_BUCKET" --key "$RESTORE_BACKUP_KEY" >"$backup_work/head.json"
# Reject oversized downloads before fetching the archive.
python3 "$tools_py" size "$backup_work/head.json"
aws_r2 s3api get-object --bucket "$R2_BACKUP_BUCKET" --key "$RESTORE_BACKUP_KEY" "$backup_work/app.dump" >"$backup_work/download.json"
python3 "$tools_py" verify "$backup_work/app.dump" "$backup_work/head.json" "$backup_work/manifest.json"

# This vendor image supplies vector + btree_gist on PostgreSQL 18. The server
# has no network, published port, source DB credential, or R2 credential.
docker pull pgvector/pgvector:0.8.6-pg18 >/dev/null
docker run -d --rm --name "$backup_container" --network none \
  --cpus=1 --memory=1g --tmpfs /var/lib/postgresql:rw,nosuid,size=512m \
  --tmpfs /tmp:rw,nosuid,size=16m \
  --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=restore_test \
  --mount "type=bind,source=$backup_work,target=/backup,readonly" \
  pgvector/pgvector:0.8.6-pg18 >"$backup_work/container.id"
ready=false
for _ in {1..30}; do
  if docker exec "$backup_container" pg_isready -U postgres -d restore_test >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]]
docker exec "$backup_container" pg_restore -U postgres --dbname=restore_test \
  --no-owner --no-acl --exit-on-error /backup/app.dump \
  >"$backup_work/restore-output.log" 2>"$backup_work/restore-errors.log"
docker exec "$backup_container" psql -U postgres -d restore_test -X -t -A \
  --file=/backup/inventory.sql >"$backup_work/restored-inventory.json" 2>"$backup_work/inventory-errors.log"
python3 "$tools_py" inventory "$backup_work/restored-inventory.json" "$backup_work/manifest.json"
printf 'Isolated PostgreSQL 18 restore verified: %s\n' "$RESTORE_BACKUP_KEY" >>"${GITHUB_STEP_SUMMARY:-/dev/stdout}"
