#!/bin/sh
# Start PostgreSQL with TLS for Railway.
#
# The services reach the database over Railway's private network. Operators,
# corpus releases and the backup workflow reach it through Railway's TCP proxy,
# which forwards raw TCP, so the server must offer TLS itself. The stock image
# only carries the Debian "snakeoil" certificate, whose key ships in every copy
# of the image, so this script generates a key pair for this volume and names
# the private and TCP proxy hosts in it. Clients pin the certificate
# (sslmode=verify-full with sslrootcert set to it); see
# deployment/railway/README.md.
#
# The certificate is kept on the volume, beside PGDATA, so it stays the same
# across deploys. It is regenerated only when the set of host names changes,
# for example when the TCP proxy is created or replaced; pinned copies must
# then be refreshed.
set -eu

tls_dir=/var/lib/postgresql/tls
names="DNS:localhost"
for host in "${RAILWAY_PRIVATE_DOMAIN:-}" "${RAILWAY_TCP_PROXY_DOMAIN:-}"; do
  if [ -n "$host" ]; then
    names="$names,DNS:$host"
  fi
done

if [ ! -s "$tls_dir/server.key" ] || [ ! -s "$tls_dir/server.crt" ] ||
  [ "$(cat "$tls_dir/names" 2>/dev/null || true)" != "$names" ]; then
  mkdir -p "$tls_dir"
  # A subshell keeps the restrictive umask away from the image's entrypoint,
  # which creates PGDATA's parent directories after this script.
  (
    umask 077
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
      -days 3650 -subj "/CN=constitution-ng-postgres" \
      -addext "subjectAltName=$names" \
      -keyout "$tls_dir/server.key.new" -out "$tls_dir/server.crt.new" 2>/dev/null
  )
  mv "$tls_dir/server.key.new" "$tls_dir/server.key"
  mv "$tls_dir/server.crt.new" "$tls_dir/server.crt"
  printf '%s' "$names" >"$tls_dir/names"
  echo "railway-postgres-start: generated a TLS certificate for $names" >&2
fi
chown -R postgres:postgres "$tls_dir"
chmod 700 "$tls_dir"
chmod 600 "$tls_dir/server.key"
chmod 644 "$tls_dir/server.crt"

if [ "${1:-}" = postgres ]; then
  shift
  set -- postgres -c ssl=on -c "ssl_cert_file=$tls_dir/server.crt" \
    -c "ssl_key_file=$tls_dir/server.key" "$@"
fi
exec docker-entrypoint.sh "$@"
