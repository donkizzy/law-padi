#!/usr/bin/env python3
# ruff: noqa: T201 -- Operator status contains no credentials.
"""Copy one verified local corpus release into Neon, then switch readers to it.

copy      adds the release's laws, sources, provisions, versions, entries, search
          passages and vectors. Rows already in Neon must match exactly; nothing is
          updated or deleted. The release lands `approved` with a `ready` index
          build, so readers keep the current release.
activate  points the enacted search target at a release already in Neon and
          retires the current one. Activating the previous release is the rollback.

Each command runs in one transaction and rolls it back unless --apply is given.
Review evidence (ingestion runs, candidates, issues, accounts) stays local, as in
the initial seed; the release must already be published locally, where the app's
source, review and composition gates passed.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent

LOCAL_HOSTS = {"localhost", "127.0.0.1"}
REHEARSAL_PREFIX = "app_neon_rehearsal_"
NULL_COLUMNS = {
    "source_document": {"verified_by", "created_by"},
    "corpus_release": {"approved_by"},
    "corpus_release_entry": {"ingestion_run_id"},
}
# Copied in dependency order. Shared rows (the Constitution and its source) are
# compared, never rewritten; release-scoped rows must all be new.
SHARED_TABLES = (
    "legal_instrument",
    "source_document",
    "provision",
    "provision_version",
)
RELEASE_TABLES = (
    "corpus_release",
    "corpus_release_entry",
    "embedding_run",
    "retrieval_index_build",
    "retrieval_segment",
    "retrieval_embedding",
)


def database_url(env_file: Path) -> str:
    url = dotenv_values(env_file).get("DATABASE_URL")
    if not url:
        raise ValueError(f"{env_file.name} has no DATABASE_URL")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def check_identities(source_url: str, target_url: str, expected_host: str) -> bool:
    """Return whether the target is production Neon; refuse anything else."""
    source = urlparse(source_url)
    target = urlparse(target_url)
    if source.hostname not in LOCAL_HOSTS or source.path != "/app":
        raise ValueError("Source must be the local app database")
    if target.hostname == expected_host and bool(expected_host) and target.path == "/app":
        return True
    if target.hostname in LOCAL_HOSTS and target.path.startswith(
        f"/{REHEARSAL_PREFIX}"
    ):
        return False
    raise ValueError(
        f"Target must be production Neon or a local {REHEARSAL_PREFIX}* copy"
    )


def verified_tls(url: str) -> str:
    """Neon requires verify-full; macOS Python has no system CA bundle."""
    import certifi

    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    query["sslmode"] = "verify-full"
    query["sslrootcert"] = certifi.where()
    return urlunparse(parts._replace(query=urlencode(query)))


def columns(connection, table: str) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name=%s
                 AND is_generated='NEVER' ORDER BY ordinal_position""",
            (table,),
        )
    ]


def expressions(table: str, names: list[str], bucket: str) -> list[sql.Composable]:
    """Column values as copied: local-only references cleared, storage remapped."""
    values: list[sql.Composable] = []
    for name in names:
        if table == "corpus_release" and name == "status":
            # Retrieval rows can only be inserted while the release is building.
            values.append(sql.SQL("'building'"))
        elif table == "retrieval_index_build" and name == "status":
            values.append(sql.SQL("'ready'"))
        elif name in NULL_COLUMNS.get(table, set()):
            values.append(sql.SQL("NULL"))
        elif table == "source_document" and name == "storage_backend":
            values.append(sql.Literal("r2"))
        elif table == "source_document" and name == "storage_bucket":
            values.append(sql.Literal(bucket))
        else:
            values.append(sql.Identifier(name))
    return values


def release_closure(source, release_id: str) -> dict[str, list[str]]:
    """IDs of every row the release needs, including each provision's ancestors."""
    ids: dict[str, list[str]] = {}

    def fetch(table: str, query: str) -> None:
        params = {"release": release_id, "provisions": ids.get("provision")}
        ids[table] = [row[0] for row in source.execute(query, params).fetchall()]

    fetch(
        "provision_version",
        """SELECT DISTINCT provision_version_id::text FROM corpus_release_entry
           WHERE release_id=%(release)s ORDER BY 1""",
    )
    fetch(
        "provision",
        """WITH RECURSIVE tree AS (
               SELECT p.id, p.parent_id FROM provision p
               JOIN provision_version v ON v.provision_id=p.id
               JOIN corpus_release_entry e ON e.provision_version_id=v.id
               WHERE e.release_id=%(release)s
               UNION
               SELECT p.id, p.parent_id FROM provision p JOIN tree t ON p.id=t.parent_id)
           SELECT id::text FROM tree ORDER BY 1""",
    )
    fetch(
        "legal_instrument",
        """SELECT DISTINCT instrument_id::text FROM provision
           WHERE id = ANY(%(provisions)s::uuid[]) ORDER BY 1""",
    )
    fetch(
        "source_document",
        """SELECT source_document_id::text FROM corpus_release_entry
           WHERE release_id=%(release)s AND source_document_id IS NOT NULL
           UNION SELECT v.source_document_id::text FROM provision_version v
           JOIN corpus_release_entry e ON e.provision_version_id=v.id
           WHERE e.release_id=%(release)s
           UNION SELECT source_document_id::text FROM retrieval_segment
           WHERE release_id=%(release)s ORDER BY 1""",
    )
    return ids


def row_digests(connection, table: str, ids: list[str], bucket: str) -> dict[str, str]:
    names = columns(connection, table)
    query = sql.SQL(
        "SELECT id::text, md5(ROW({})::text) FROM {} WHERE id = ANY(%s::uuid[])"
    ).format(
        sql.SQL(",").join(expressions(table, names, bucket)), sql.Identifier(table)
    )
    return dict(connection.execute(query, (ids,)).fetchall())


def copy_rows(source, target, table: str, where: sql.Composable, params, bucket):
    names = columns(source, table)
    if names != columns(target, table):
        raise ValueError(f"{table} schema differs; migrate Neon to the local head")
    source_sql = sql.SQL("COPY (SELECT {} FROM {} WHERE {}) TO STDOUT (FORMAT BINARY)")
    target_sql = sql.SQL("COPY {} ({}) FROM STDIN (FORMAT BINARY)")
    with source.cursor().copy(
        source_sql.format(
            sql.SQL(",").join(expressions(table, names, bucket)),
            sql.Identifier(table),
            where,
        ),
        params,
    ) as reader:
        with target.cursor().copy(
            target_sql.format(
                sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, names))
            )
        ) as writer:
            for block in reader:
                writer.write(block)


def release_fingerprint(connection, release_id: str) -> dict[str, dict]:
    """Counts and hashes that must match on both sides after a copy."""
    queries = {
        "versions": """SELECT v.id::text, v.text_sha256,
            encode(sha256(convert_to(v.normalized_text,'UTF8')),'hex')
            FROM provision_version v JOIN corpus_release_entry e
              ON e.provision_version_id=v.id
            WHERE e.release_id=%(release)s ORDER BY 1""",
        "entries": """SELECT id::text, provision_version_id::text,
            source_document_id::text FROM corpus_release_entry
            WHERE release_id=%(release)s ORDER BY 1""",
        "segments": """SELECT id::text, retrieval_text_sha256,
            encode(sha256(convert_to(retrieval_text,'UTF8')),'hex'),
            authoritative_text_sha256 FROM retrieval_segment
            WHERE release_id=%(release)s ORDER BY 1""",
        "vectors": """SELECT id::text, embedding_sha256,
            encode(sha256(convert_to(embedding::text,'UTF8')),'hex')
            FROM retrieval_embedding WHERE release_id=%(release)s ORDER BY 1""",
    }
    report = {}
    for name, query in queries.items():
        rows = connection.execute(query, {"release": release_id}).fetchall()
        if name in {"versions", "segments"} and any(row[1] != row[2] for row in rows):
            raise ValueError(f"Stored {name} text hashes fail verification")
        report[name] = {
            "count": len(rows),
            "sha256": hashlib.sha256(
                json.dumps(rows, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    return report


def missing_sources(source, ids: list[str], bucket: str) -> list[str]:
    """Storage keys of the release's source PDFs that are absent from R2."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.ingestion.r2_blob_store import R2BlobStore

    credentials = {
        **dotenv_values(ROOT / ".env"),
        **{k: v for k, v in dotenv_values(ROOT / "deployment/r2.env").items() if v},
    }
    store = R2BlobStore(
        endpoint_url=credentials["R2_ENDPOINT_URL"] or "",
        bucket_name=bucket,
        access_key_id=credentials["R2_ACCESS_KEY_ID"] or "",
        secret_access_key=credentials["R2_SECRET_ACCESS_KEY"] or "",
    )
    missing = []
    for key, sha256 in source.execute(
        "SELECT storage_key, sha256 FROM source_document WHERE id = ANY(%s::uuid[])",
        (ids,),
    ).fetchall():
        try:
            head = store.head(key)
        except FileNotFoundError:
            missing.append(key)
            continue
        if head.sha256 and head.sha256 != sha256:
            raise ValueError(f"R2 object differs from its recorded hash: {key}")
    return missing


def copy_release(source, target, version: str, bucket: str, production: bool) -> dict:
    found = source.execute(
        """SELECT id::text, status FROM corpus_release WHERE version=%s""", (version,)
    ).fetchall()
    if len(found) != 1 or found[0][1] not in {"production", "approved"}:
        raise ValueError("Copy only a release that is approved or published locally")
    release_id = found[0][0]
    if target.execute(
        "SELECT 1 FROM corpus_release WHERE id=%s OR version=%s", (release_id, version)
    ).fetchone():
        raise ValueError("Neon already has this release; nothing to copy")
    head = "SELECT version_num FROM alembic_version"
    if source.execute(head).fetchall() != target.execute(head).fetchall():
        raise ValueError("Neon schema is not at the local migration head")
    if source.execute(
        """SELECT count(*) FROM provision_version v JOIN corpus_release_entry e
           ON e.provision_version_id=v.id WHERE e.release_id=%s
           AND (v.created_by_amendment_id IS NOT NULL OR v.supersedes_id IS NOT NULL)""",
        (release_id,),
    ).fetchone()[0]:
        raise ValueError("Review amendment/history dependency closure before copying")
    builds = source.execute(
        """SELECT b.id::text, b.embedding_run_id::text, b.profile_id::text
           FROM retrieval_index_build b JOIN embedding_run r ON r.id=b.embedding_run_id
           WHERE b.release_id=%s AND b.backend='pgvector'
             AND b.status IN ('ready','promoted') AND r.status='succeeded'
             AND b.stored_segment_count=b.expected_segment_count
             AND b.stored_embedding_count=b.expected_segment_count
             AND (b.validation_report->>'is_valid')::boolean""",
        (release_id,),
    ).fetchall()
    if len(builds) != 1:
        raise ValueError("Release needs exactly one validated pgvector index build")
    build_id, run_id, profile_id = builds[0]
    if not target.execute(
        "SELECT 1 FROM embedding_profile WHERE id=%s", (profile_id,)
    ).fetchone():
        raise ValueError("Neon lacks the release's embedding profile")

    closure = release_closure(source, release_id)
    if production:
        missing = missing_sources(source, closure["source_document"], bucket)
        if missing:
            raise ValueError(f"Upload these sources to R2 first: {missing}")
    plan: dict[str, dict[str, int]] = {}
    for table in SHARED_TABLES:
        ids = closure[table]
        local = row_digests(source, table, ids, bucket)
        remote = row_digests(target, table, ids, bucket)
        changed = sorted(key for key in remote if remote[key] != local.get(key))
        if changed:
            raise ValueError(f"{table} rows differ in Neon: {changed[:5]}")
        new = [key for key in ids if key not in remote]
        plan[table] = {"existing": len(remote), "new": len(new)}
        if new:
            copy_rows(
                source,
                target,
                table,
                sql.SQL("id = ANY(%s::uuid[])"),
                (new,),
                bucket,
            )
    for table in RELEASE_TABLES:
        key = "id" if table == "corpus_release" else "release_id"
        where = sql.SQL("{} = %s").format(sql.Identifier(key))
        params: tuple = (release_id,)
        if table in {"embedding_run", "retrieval_index_build"}:
            where = sql.SQL("id = %s")
            params = (run_id if table == "embedding_run" else build_id,)
        copy_rows(source, target, table, where, params, bucket)
        plan[table] = {
            "new": target.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE {}").format(
                    sql.Identifier(table), where
                ),
                params,
            ).fetchone()[0]
        }
    target.execute(
        "UPDATE corpus_release SET status='approved' WHERE id=%s", (release_id,)
    )
    expected = release_fingerprint(source, release_id)
    copied = release_fingerprint(target, release_id)
    if copied != expected:
        raise ValueError("Copied release fingerprint differs from the local release")
    return {"release_id": release_id, "rows": plan, "fingerprint": copied}


def activate_release(target, version: str) -> dict:
    found = target.execute(
        "SELECT id::text, status FROM corpus_release WHERE version=%s FOR UPDATE",
        (version,),
    ).fetchall()
    if len(found) != 1:
        raise ValueError("Neon has no such release; copy it first")
    release_id, status = found[0]
    if status not in {"approved", "retired"}:
        raise ValueError(f"Release is {status}; only approved or retired can go live")
    if not target.execute(
        """SELECT 1 FROM corpus_release_entry e
           JOIN provision_version v ON v.id=e.provision_version_id
           JOIN provision p ON p.id=v.provision_id
           JOIN legal_instrument i ON i.id=p.instrument_id
           WHERE e.release_id=%s AND i.instrument_type='constitution' LIMIT 1""",
        (release_id,),
    ).fetchone():
        raise ValueError("Only a release that contains the Constitution can go live")
    builds = target.execute(
        """SELECT b.id::text, b.embedding_run_id::text, b.profile_id::text,
                  b.index_kind, b.expected_segment_count
           FROM retrieval_index_build b
           WHERE b.release_id=%s AND b.backend='pgvector'
             AND b.status IN ('ready','promoted')
             AND (b.validation_report->>'is_valid')::boolean
           ORDER BY b.updated_at DESC LIMIT 1""",
        (release_id,),
    ).fetchall()
    if not builds:
        raise ValueError("Release has no validated pgvector index build in Neon")
    build_id, run_id, profile_id, index_kind, expected = builds[0]
    stored = target.execute(
        """SELECT (SELECT count(*) FROM retrieval_segment WHERE release_id=%(r)s),
                  (SELECT count(*) FROM retrieval_embedding
                   WHERE release_id=%(r)s AND embedding_run_id=%(run)s)""",
        {"r": release_id, "run": run_id},
    ).fetchone()
    if stored != (expected, expected):
        raise ValueError(f"Index build expects {expected} rows; Neon holds {stored}")
    pointer = target.execute(
        """SELECT t.release_id::text, r.version FROM active_retrieval_target t
           JOIN corpus_release r ON r.id=t.release_id
           WHERE t.index_kind=%s FOR UPDATE""",
        (index_kind,),
    ).fetchall()
    if len(pointer) != 1:
        raise ValueError("Neon has no active retrieval target to switch")
    previous_id, previous_version = pointer[0]
    if previous_id == release_id:
        raise ValueError("Release is already live")
    target.execute(
        """UPDATE corpus_release SET status='retired', lock_version=lock_version+1
           WHERE status='production' AND id<>%s""",
        (release_id,),
    )
    target.execute(
        """UPDATE corpus_release SET status='production', lock_version=lock_version+1,
           approved_at=coalesce(approved_at, now()) WHERE id=%s""",
        (release_id,),
    )
    target.execute(
        """UPDATE active_retrieval_target SET release_id=%s, embedding_run_id=%s,
           retrieval_index_build_id=%s, profile_id=%s, lock_version=lock_version+1,
           activated_by=NULL, activated_at=now(), updated_at=now()
           WHERE index_kind=%s""",
        (release_id, run_id, build_id, profile_id, index_kind),
    )
    target.execute(
        "UPDATE retrieval_index_build SET status='promoted', updated_at=now() WHERE id=%s",
        (build_id,),
    )
    target.execute(
        """INSERT INTO release_promotion_attempt
           (id, release_id, retrieval_index_build_id, index_kind, status,
            previous_release_id, rollback_completed, started_at, completed_at,
            created_at)
           VALUES (gen_random_uuid(), %s, %s, %s, 'succeeded', %s, false,
                   now(), now(), now())""",
        (release_id, build_id, index_kind, previous_id),
    )
    return {"live": version, "previous": previous_version, "index_kind": index_kind}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("copy", "activate"))
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--target-env", type=Path, default=ROOT / "deployment/neon.env")
    parser.add_argument("--source-bucket", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source_url = database_url(ROOT / ".env")
    target_url = database_url(args.target_env)
    expected_host = dotenv_values(args.target_env).get("EXPECTED_NEON_HOST") or ""
    production = check_identities(source_url, target_url, expected_host)
    if args.command == "copy" and not args.source_bucket:
        parser.error("--source-bucket is required for copy")
    if production:
        target_url = verified_tls(target_url)
    with (
        psycopg.connect(source_url, connect_timeout=20) as source,
        psycopg.connect(target_url, connect_timeout=20) as target,
    ):
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        target.execute("SET LOCAL lock_timeout = '5s'")
        if args.command == "copy":
            report = copy_release(
                source, target, args.release_version, args.source_bucket, production
            )
        else:
            report = activate_release(target, args.release_version)
        if args.apply:
            target.commit()
        else:
            target.rollback()
    label = "Applied" if args.apply else "Dry run (rolled back)"
    where = "Neon" if production else urlparse(target_url).path.lstrip("/")
    print(f"{label}: {args.command} {args.release_version} on {where}")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
