#!/usr/bin/env python3
# ruff: noqa: T201 -- Operator status contains no credentials.
"""Seed only the published corpus into the authorized new, empty Neon database.

Run with the repository .venv Python. The local source transactions are read-only.
No account rows, password hashes, conversations, ingestion jobs, or API keys are
copied. A separate random production bootstrap is saved in a private dotenv file.
"""

import argparse
import gzip
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import certifi
import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_HOST = "ep-soft-firefly-b8cpxico.c-14.us-east-1.aws.neon.tech"
EXPECTED_RELEASE = "draft-c8d50d87fae9"
EXPECTED_SPEND = 1_385_829
LEDGER_DATABASE = "app_live_validation_20261009"
NULL_COLUMNS = {
    "source_document": {"verified_by", "created_by"},
    "corpus_release": {"approved_by"},
    "corpus_release_entry": {"ingestion_run_id"},
    "active_retrieval_target": {"activated_by"},
    "generation_reservation": {"run_id"},
}


def readonly(url: str):
    connection = psycopg.connect(url, connect_timeout=20)
    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    return connection


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


def fingerprint(connection) -> dict:
    queries = {
        "canonical": """SELECT id::text, text_sha256,
            encode(sha256(convert_to(normalized_text,'UTF8')),'hex'),
            encode(sha256(convert_to(text,'UTF8')),'hex')
            FROM provision_version ORDER BY id""",
        "segments": """SELECT id::text,retrieval_text_sha256,
            encode(sha256(convert_to(retrieval_text,'UTF8')),'hex'),
            authoritative_text_sha256 FROM retrieval_segment ORDER BY id""",
        "vectors": """SELECT id::text,embedding_sha256,
            encode(sha256(convert_to(embedding::text,'UTF8')),'hex')
            FROM retrieval_embedding ORDER BY id""",
        "sources": """SELECT id::text,storage_key,sha256,file_size
            FROM source_document ORDER BY id""",
        "pointer": """SELECT index_kind,release_id::text,embedding_run_id::text,
            retrieval_index_build_id::text,profile_id::text
            FROM active_retrieval_target ORDER BY index_kind""",
    }
    report = {}
    for name, query in queries.items():
        rows = connection.execute(query).fetchall()
        if name in {"canonical", "segments"} and any(row[1] != row[2] for row in rows):
            raise ValueError(f"Stored {name} text hashes fail verification")
        report[name] = {
            "count": len(rows),
            "sha256": hashlib.sha256(
                json.dumps(rows, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    return report


def copy_table(source, target, archive, table, where, params, source_bucket):
    names = columns(source, table)
    if not names or not set(names).issubset(columns(target, table)):
        raise ValueError(f"Unexpected schema for {table}")
    expressions = []
    for name in names:
        if table == "corpus_release" and name == "status":
            # The destination's immutable-release trigger correctly rejects
            # inserting vectors into a production release. Keep this private
            # transaction building until all exact data is verified, then
            # restore its existing production status before committing.
            expressions.append(sql.SQL("'building' AS status"))
        elif name in NULL_COLUMNS.get(table, set()):
            expressions.append(sql.SQL("NULL AS {}").format(sql.Identifier(name)))
        elif table == "source_document" and name in {
            "storage_backend",
            "storage_bucket",
        }:
            value = "r2" if name == "storage_backend" else source_bucket
            expressions.append(
                sql.SQL("{} AS {}").format(sql.Literal(value), sql.Identifier(name))
            )
        else:
            expressions.append(sql.Identifier(name))
    source_sql = sql.SQL("COPY (SELECT {} FROM {} WHERE {}) TO STDOUT").format(
        sql.SQL(",").join(expressions), sql.Identifier(table), sql.SQL(where)
    )
    target_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, names))
    )
    archive.write(target_sql.as_string(target).encode() + b";\n")
    if table == "retrieval_embedding":
        # Float text is several times larger than PostgreSQL's binary vector
        # representation. Keep the portable SQL artifact textual, then stream
        # binary directly between matching PostgreSQL 18 servers over TLS.
        with source.cursor().copy(source_sql, params) as reader:
            for block in reader:
                archive.write(block)
        binary_source = source_sql + sql.SQL(" (FORMAT BINARY)")
        binary_target = target_sql + sql.SQL(" (FORMAT BINARY)")
        with source.cursor().copy(binary_source, params) as reader:
            with target.cursor().copy(binary_target) as writer:
                for block in reader:
                    writer.write(block)
    else:
        with source.cursor().copy(source_sql, params) as reader:
            with target.cursor().copy(target_sql) as writer:
                for block in reader:
                    writer.write(block)
                    archive.write(block)
    archive.write(b"\\.\n")


def ensure_empty(connection):
    for (table,) in connection.execute(
        """SELECT tablename FROM pg_tables WHERE schemaname='public'
           AND tablename <> 'alembic_version'"""
    ).fetchall():
        if table == "generation_capacity" and connection.execute(
            "SELECT id,active_count FROM generation_capacity"
        ).fetchall() == [(1, 0)]:
            # This singleton is inserted by the checked-in schema migration.
            continue
        if connection.execute(
            sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(
                sql.Identifier(table)
            )
        ).fetchone()[0]:
            raise ValueError(f"Destination is not empty: {table}")


def bootstrap_file(local: dict, path: Path):
    if path.exists():
        if path.stat().st_mode & 0o077:
            raise ValueError("Bootstrap dotenv permissions must be 600")
        return dotenv_values(path)
    email = local.get("FIRST_SUPERUSER")
    if not email:
        raise ValueError("Local configuration has no selected admin email")
    values = {
        "PROJECT_NAME": "constitution.ng",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "FIRST_SUPERUSER": email,
        "FIRST_SUPERUSER_PASSWORD": secrets.token_urlsafe(36),
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("# Private new production bootstrap; never commit or print.\n")
        for key, value in values.items():
            handle.write(f"{key}={json.dumps(value)}\n")
    return values


def backend_command(destination_url, bootstrap_path, *arguments):
    environment = {
        **os.environ,
        "DATABASE_URL": destination_url,
        "APP_RUNTIME_ENV_FILE": str(bootstrap_path),
        "CHAT_ENABLED": "false",
        "CHAT_GENERATION_ENABLED": "false",
        "CHAT_GENERATION_KILL_SWITCH": "true",
        "EMBEDDING_QUERY_ENABLED": "false",
        "SERVE_FRONTEND": "false",
    }
    environment.pop("FASTAPI_ENV", None)
    environment.pop("APP_RUNTIME_ROLE", None)
    subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT / "backend",
        env=environment,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-bucket", default="lawpadi")
    args = parser.parse_args()
    local = dotenv_values(ROOT / ".env")
    destination = dotenv_values(ROOT / "deployment/neon.env")
    source_url = local["DATABASE_URL"]
    target_url = destination["DATABASE_URL"]
    target_parts = urlparse(target_url)
    if (
        target_parts.hostname != EXPECTED_HOST
        or target_parts.path != "/app"
        or target_parts.username != "app_owner"
        or urlparse(source_url).hostname not in {"localhost", "127.0.0.1"}
        or urlparse(source_url).path != "/app"
    ):
        raise ValueError(
            "Source/destination identity differs from the authorized databases"
        )
    if sys.platform == "darwin":
        query = dict(parse_qsl(target_parts.query))
        query["sslrootcert"] = certifi.where()
        target_url = urlunparse(target_parts._replace(query=urlencode(query)))
    ledger_url = make_conninfo(source_url, dbname=LEDGER_DATABASE)
    with readonly(source_url) as source, readonly(ledger_url) as ledger:
        active = source.execute(
            """SELECT t.release_id,t.embedding_run_id,t.retrieval_index_build_id,
                      t.profile_id,r.version,r.status FROM active_retrieval_target t
               JOIN corpus_release r ON r.id=t.release_id WHERE t.index_kind='enacted'"""
        ).fetchall()
        if len(active) != 1 or active[0][4:] != (EXPECTED_RELEASE, "production"):
            raise ValueError("Expected approved production release is not active")
        release_id, run_id, build_id, profile_id, *_ = active[0]
        if source.execute(
            """SELECT count(*) FROM provision_version
               WHERE created_by_amendment_id IS NOT NULL OR supersedes_id IS NOT NULL"""
        ).fetchone()[0]:
            raise ValueError(
                "Review amendment/history dependency closure before copying"
            )
        baseline = fingerprint(source)
        if (
            baseline["canonical"]["count"] != 1811
            or baseline["segments"]["count"] != 1829
            or baseline["vectors"]["count"] != 1829
        ):
            raise ValueError("Corpus differs from the reviewed recovery evidence")
        spend = ledger.execute(
            "SELECT coalesce(sum(spent_micro_usd),0),coalesce(sum(reserved_micro_usd),0) FROM generation_budget_day"
        ).fetchone()
        reservation_spend = ledger.execute(
            "SELECT coalesce(sum(actual_micro_usd),0),count(*) FILTER (WHERE status<>'settled') FROM generation_reservation"
        ).fetchone()
        if spend != (EXPECTED_SPEND, 0) or reservation_spend != (EXPECTED_SPEND, 0):
            raise ValueError(
                "Prior provider ledger changed; audit it before transferring"
            )
        with psycopg.connect(target_url, connect_timeout=20) as target:
            ensure_empty(target)
        print(
            "Verified published corpus, empty Neon destination and $1.385829 prior spend."
        )
        if not args.apply:
            print(
                "No changes made. Use --apply for the authorized empty-database seed."
            )
            return
        private_bootstrap = ROOT / "deployment/bootstrap.env"
        bootstrap_file(local, private_bootstrap)
        backend_command(
            target_url, private_bootstrap, "-m", "alembic", "upgrade", "head"
        )
        print("Applied schema migrations to the empty destination.")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dump_path = ROOT / f"deployment/corpus-{timestamp}.sql.gz"
        descriptor = os.open(dump_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as archive:
                with psycopg.connect(target_url, connect_timeout=20) as target:
                    ensure_empty(target)
                    archive.write(
                        b"-- Published corpus and detached spend evidence only.\nBEGIN;\n"
                    )
                    # Only the active release and its exact references are copied.
                    selected_versions = "SELECT provision_version_id FROM corpus_release_entry WHERE release_id=%s"
                    selected_sources = f"SELECT source_document_id FROM provision_version WHERE id IN ({selected_versions})"
                    selections = [
                        (
                            "legal_instrument",
                            "id IN (SELECT legal_instrument_id FROM source_document WHERE id IN ("
                            + selected_sources
                            + "))",
                            (release_id,),
                        ),
                        (
                            "source_document",
                            "id IN (" + selected_sources + ")",
                            (release_id,),
                        ),
                        (
                            "provision",
                            "id IN (WITH RECURSIVE selected AS (SELECT p.id,p.parent_id FROM provision p JOIN provision_version v ON v.provision_id=p.id WHERE v.id IN ("
                            + selected_versions
                            + ") UNION SELECT p.id,p.parent_id FROM provision p JOIN selected s ON p.id=s.parent_id) SELECT id FROM selected)",
                            (release_id,),
                        ),
                        (
                            "provision_version",
                            "id IN (" + selected_versions + ")",
                            (release_id,),
                        ),
                        ("corpus_release", "id=%s", (release_id,)),
                        ("corpus_release_entry", "release_id=%s", (release_id,)),
                        ("embedding_profile", "id=%s", (profile_id,)),
                        ("embedding_run", "id=%s", (run_id,)),
                        (
                            "retrieval_segment",
                            "release_id=%s AND index_kind='enacted'",
                            (release_id,),
                        ),
                        (
                            "retrieval_embedding",
                            "release_id=%s AND embedding_run_id=%s",
                            (release_id, run_id),
                        ),
                        ("retrieval_index_build", "id=%s", (build_id,)),
                        ("active_retrieval_target", "index_kind='enacted'", ()),
                    ]
                    for table, where, params in selections:
                        copy_table(
                            source,
                            target,
                            archive,
                            table,
                            where,
                            params,
                            args.source_bucket,
                        )
                        print(f"Transferred {table}.")
                    for table in ("generation_budget_day", "generation_reservation"):
                        copy_table(
                            ledger,
                            target,
                            archive,
                            table,
                            "true",
                            (),
                            args.source_bucket,
                        )
                    month_sql = """INSERT INTO generation_budget_month (month,reserved_micro_usd,spent_micro_usd)
                        SELECT date_trunc('month',day)::date,SUM(reserved_micro_usd),SUM(spent_micro_usd)
                        FROM generation_budget_day GROUP BY 1"""
                    target.execute(month_sql)
                    archive.write(month_sql.encode() + b";\n")
                    if fingerprint(target) != baseline:
                        raise ValueError(
                            "Target corpus differs; seed transaction rolled back"
                        )
                    production_sql = sql.SQL(
                        "UPDATE corpus_release SET status='production' WHERE id={}"
                    ).format(sql.Literal(release_id))
                    target.execute(production_sql)
                    archive.write(production_sql.as_string(target).encode() + b";\n")
                    target_spend = target.execute(
                        "SELECT sum(spent_micro_usd),sum(reserved_micro_usd) FROM generation_budget_month"
                    ).fetchone()
                    if target_spend != (EXPECTED_SPEND, 0):
                        raise ValueError(
                            "Target spend ledger does not match audited prior usage"
                        )
                    archive.write(b"COMMIT;\n")
        print(
            "Committed corpus after exact canonical, segment, vector and source hash comparison."
        )
        backend_command(target_url, private_bootstrap, "-m", "app.initial_data")
        with readonly(target_url) as target:
            report = {
                "completed_at": datetime.now(UTC).isoformat(),
                "destination_host": EXPECTED_HOST,
                "database": "app",
                "release": EXPECTED_RELEASE,
                "fingerprints": fingerprint(target),
                "counts": {
                    table: target.execute(
                        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
                    ).fetchone()[0]
                    for table in (
                        "legal_instrument",
                        "source_document",
                        "provision",
                        "provision_version",
                        "corpus_release_entry",
                        "retrieval_segment",
                        "retrieval_embedding",
                        "user",
                        "conversation",
                        "generation_reservation",
                    )
                },
                "schema_head": target.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0],
                "extensions": target.execute(
                    "SELECT extname,extversion FROM pg_extension WHERE extname IN ('vector','btree_gist') ORDER BY extname"
                ).fetchall(),
                "sources": target.execute(
                    "SELECT id::text,storage_backend,storage_bucket,storage_key,sha256,file_size FROM source_document ORDER BY id"
                ).fetchall(),
                "spend_carry_micro_usd": EXPECTED_SPEND,
                "unresolved_reservations": 0,
                "section_identity_counts": {
                    number: target.execute(
                        """SELECT count(*) FROM provision p
                           JOIN provision_version v ON v.provision_id=p.id
                           WHERE p.kind='section' AND p.number=%s""",
                        (number,),
                    ).fetchone()[0]
                    for number in ("168", "189")
                },
                "source_transactions_read_only": True,
                "dump_file": str(dump_path.relative_to(ROOT)),
                "dump_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
                "bootstrap_credentials_file": "deployment/bootstrap.env",
            }
        report_path = ROOT / "deployment/seed.report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Seed stopped: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Database and subprocess exceptions can include connection details.
        descriptor = os.open(
            ROOT / "deployment/seed-error.report.json",
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(descriptor, "w") as handle:
            json.dump(
                {"error_type": type(exc).__name__, "private_diagnostic": str(exc)},
                handle,
            )
        print(
            f"Seed stopped ({type(exc).__name__}); inspect the failed phase privately.",
            file=sys.stderr,
        )
        sys.exit(1)
