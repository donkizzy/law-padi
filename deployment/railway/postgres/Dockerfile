# syntax=docker/dockerfile:1
# PostgreSQL 18 with pgvector, the same image Compose and the restore checks
# use, plus a TLS certificate generated for each volume (start.sh).
FROM pgvector/pgvector:0.8.6-pg18@sha256:2ba9ca5f2e7daa0f0e7723cba1ee9167bab54efd3640516a44ac1a928dd67e7a
COPY start.sh /usr/local/bin/railway-postgres-start
ENTRYPOINT ["railway-postgres-start"]
CMD ["postgres"]
