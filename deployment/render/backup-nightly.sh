#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/backup-common.sh"

: "${NEON_BACKUP_DATABASE_URL:?Set the private Neon connection secret}"
python3 "$tools_py" pg-env "$backup_work/postgres.env"
docker pull postgres:18 >/dev/null

source_inventory() {
  docker run --rm --read-only --user "$(id -u):$(id -g)" \
    --cpus=1 --memory=512m --tmpfs /tmp:rw,nosuid,size=16m \
    --env-file "$backup_work/postgres.env" \
    --mount "type=bind,source=$backup_work,target=/backup,readonly" \
    --mount type=bind,source=/etc/ssl/certs/ca-certificates.crt,target=/run/neon-ca.crt,readonly \
    postgres:18 psql -X -t -A --file=/backup/inventory.sql
}

source_inventory >"$backup_work/inventory-before.json" 2>"$backup_work/source-errors.log"
docker run --rm --name "$backup_container" --read-only \
  --user "$(id -u):$(id -g)" --cpus=1 --memory=512m \
  --ulimit fsize=104857600:104857600 --tmpfs /tmp:rw,nosuid,size=16m \
  --env-file "$backup_work/postgres.env" \
  --mount "type=bind,source=$backup_work,target=/backup" \
  --mount type=bind,source=/etc/ssl/certs/ca-certificates.crt,target=/run/neon-ca.crt,readonly \
  --entrypoint sh postgres:18 -c \
  'umask 077; exec pg_dump --format=custom --compress=gzip:6 --no-owner --no-acl --lock-wait-timeout=30s --file=/backup/app.dump' \
  >"$backup_work/dump-output.log" 2>"$backup_work/dump-errors.log"
source_inventory >"$backup_work/inventory-after.json" 2>>"$backup_work/source-errors.log"
cmp -s "$backup_work/inventory-before.json" "$backup_work/inventory-after.json"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_id="${GITHUB_RUN_ID:?Expected GitHub run ID}"
attempt="${GITHUB_RUN_ATTEMPT:?Expected GitHub run attempt}"
[[ "$run_id" =~ ^[0-9]+$ && "$attempt" =~ ^[0-9]+$ ]]
backup_key="postgres/app/$(date -u +%Y/%m/%d)/app-$stamp-$run_id-$attempt.dump"
python3 "$tools_py" manifest "$backup_work/app.dump" "$backup_work/inventory-after.json" "$backup_key" "$backup_work/manifest.json"
digest="$(python3 "$tools_py" digest "$backup_work/app.dump")"
aws_r2 s3api put-object --bucket "$R2_BACKUP_BUCKET" --key "$backup_key" \
  --body "$backup_work/app.dump" --storage-class STANDARD \
  --content-type application/octet-stream --metadata "sha256=$digest" \
  >"$backup_work/upload.json"
aws_r2 s3api head-object --bucket "$R2_BACKUP_BUCKET" --key "$backup_key" >"$backup_work/head.json"
aws_r2 s3api get-object --bucket "$R2_BACKUP_BUCKET" --key "$backup_key" "$backup_work/verified.dump" >"$backup_work/download.json"
python3 "$tools_py" verify "$backup_work/verified.dump" "$backup_work/head.json" "$backup_work/manifest.json"
# A completed manifest is published only after full read-back verification.
aws_r2 s3api put-object --bucket "$R2_BACKUP_BUCKET" --key "$backup_key.json" \
  --body "$backup_work/manifest.json" --storage-class STANDARD --content-type application/json \
  >"$backup_work/manifest-upload.json"
printf 'Verified private backup: %s\nSHA-256: %s\n' "$backup_key" "$digest" >>"${GITHUB_STEP_SUMMARY:-/dev/stdout}"
