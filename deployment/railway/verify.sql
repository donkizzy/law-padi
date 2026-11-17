-- Database fingerprint for the Neon to Railway move
-- (docs/runbooks/railway-migration.md). Run it against both databases with
--   psql "<url>" -X -A -t -q -f deployment/railway/verify.sql > <side>.txt
-- and compare the two files with diff: they must be identical. It reads only;
-- every statement is a SELECT, and it prints no credentials.

-- Schema revision.
SELECT 'alembic', version_num FROM alembic_version;

-- Extensions the migrations need. The vector version may differ between
-- providers; anything else differing is a failure.
SELECT 'extension', extname FROM pg_extension ORDER BY extname;

-- Exact row count of every table.
SELECT 'rows', table_name,
       (xpath('/row/c/text()',
              query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name),
                           false, true, '')))[1]::text
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Embedding column type and the dimensions actually stored.
SELECT 'vector_column', format_type(atttypid, atttypmod)
FROM pg_attribute
WHERE attrelid = 'public.retrieval_embedding'::regclass AND attname = 'embedding';
SELECT 'vector_dims', vector_dims(embedding), count(*)
FROM retrieval_embedding GROUP BY 2 ORDER BY 2;

-- Indexes and constraints, including the exclusion constraint on provision
-- validity periods.
SELECT 'index', indexname, indexdef
FROM pg_indexes WHERE schemaname = 'public' ORDER BY indexname;
SELECT 'constraint', conrelid::regclass::text, conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
ORDER BY conrelid::regclass::text, conname;

-- Live corpus, the same values the backup manifest records
-- (deployment/backup/backup-common.sh).
SELECT 'active_release', r.version, t.index_kind
FROM active_retrieval_target t JOIN corpus_release r ON r.id = t.release_id
ORDER BY t.index_kind;
SELECT 'canonical_hash_errors', count(*)
FROM provision_version
WHERE text_sha256 <> encode(sha256(convert_to(normalized_text, 'UTF8')), 'hex');
SELECT 'canonical_sha256',
       encode(sha256(convert_to(coalesce(string_agg(id::text || ':' || text_sha256, ','
                                                    ORDER BY id), ''), 'UTF8')), 'hex')
FROM provision_version;
SELECT 'vectors_sha256',
       encode(sha256(convert_to(coalesce(string_agg(
           id::text || ':' || embedding_sha256 || ':'
           || encode(sha256(convert_to(embedding::text, 'UTF8')), 'hex'),
           ',' ORDER BY id), ''), 'UTF8')), 'hex')
FROM retrieval_embedding;

-- Spend carried into the new host: the month's ledger must not reset.
SELECT 'budget_month', to_jsonb(m) - 'updated_at' - 'created_at'
FROM generation_budget_month m ORDER BY 2::text;
