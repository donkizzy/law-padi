#!/usr/bin/env bash
# Source only this reviewed code file; never source a credential dotenv bundle.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
tools_py="$script_dir/backup_tools.py"
backup_work="$(mktemp -d "${RUNNER_TEMP:-/tmp}/constitution-backup.XXXXXX")"
backup_container="constitution-backup-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
cleanup_backup() {
  docker rm -f -v "$backup_container" >/dev/null 2>&1 || true
  rm -rf -- "$backup_work"
}
trap cleanup_backup EXIT

: "${R2_BACKUP_ENDPOINT_URL:?Set the private R2 endpoint secret}"
: "${R2_BACKUP_ACCESS_KEY_ID:?Set the bucket-scoped access key}"
: "${R2_BACKUP_SECRET_ACCESS_KEY:?Set the bucket-scoped secret key}"
: "${R2_BACKUP_BUCKET:?Set the backup bucket name}"
: "${EXPECTED_NEON_HOST:?Set the authorized Neon hostname}"
export AWS_ACCESS_KEY_ID="$R2_BACKUP_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_BACKUP_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION=auto AWS_EC2_METADATA_DISABLED=true AWS_PAGER=""
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
python3 "$tools_py" endpoint
command -v aws >/dev/null
command -v docker >/dev/null

aws_r2() {
  aws --endpoint-url "$R2_BACKUP_ENDPOINT_URL" --region auto --no-cli-pager "$@"
}

cat >"$backup_work/inventory.sql" <<'SQL'
SELECT json_build_object(
  'schema_revision',(SELECT version_num FROM alembic_version),
  'release',(SELECT r.version FROM corpus_release r JOIN active_retrieval_target t ON t.release_id=r.id WHERE t.index_kind='enacted'),
  'canonical_count',(SELECT count(*) FROM provision_version),
  'vector_count',(SELECT count(*) FROM retrieval_embedding),
  'canonical_hash_errors',(SELECT count(*) FROM provision_version WHERE text_sha256<>encode(sha256(convert_to(normalized_text,'UTF8')),'hex')),
  'canonical_sha256',(SELECT encode(sha256(convert_to(coalesce(string_agg(id::text||':'||text_sha256,',' ORDER BY id),''),'UTF8')),'hex') FROM provision_version),
  'vectors_sha256',(SELECT encode(sha256(convert_to(coalesce(string_agg(id::text||':'||embedding_sha256||':'||encode(sha256(convert_to(embedding::text,'UTF8')),'hex'),',' ORDER BY id),''),'UTF8')),'hex') FROM retrieval_embedding)
);
SQL
