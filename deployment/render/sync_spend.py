#!/usr/bin/env python3
# ruff: noqa: T201 -- Reports contain aggregate spend and database identities only.
"""Carry local AI evaluation usage into the still-private Neon beta.

Stop the paid collector before --apply. This command never modifies the source.
The destination must have generation disabled and no conversations or runs.
Reservation IDs are preserved and run IDs detached, so rerunning is idempotent.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import certifi
import httpx
import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SOURCE = "app_live_validation_20261015_v8"
EXPECTED_HOST = "ep-soft-firefly-b8cpxico.c-14.us-east-1.aws.neon.tech"
TABLES = ("generation_budget_day", "generation_budget_month", "generation_reservation")
RESERVATION_COLUMNS = (
    "id",
    "day",
    "purpose",
    "reserved_micro_usd",
    "actual_micro_usd",
    "status",
    "created_at",
)
Snapshot = dict[str, list[dict[str, Any]]]


def _amount(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Spend amounts must be nonnegative integers")
    return value


def validate_snapshot(snapshot: Snapshot) -> dict[str, int]:
    """Reconcile both aggregate ledgers with every retained reservation."""
    days = {row["day"]: row for row in snapshot[TABLES[0]]}
    months = {row["month"]: row for row in snapshot[TABLES[1]]}
    reservations = {row["id"]: row for row in snapshot[TABLES[2]]}
    if any(
        len(mapping) != len(snapshot[table])
        for mapping, table in zip((days, months, reservations), TABLES, strict=True)
    ):
        raise ValueError("Spend snapshot contains duplicate primary keys")
    calculated_days: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for row in reservations.values():
        if row["day"] not in days:
            raise ValueError("Reservation has no daily ledger")
        reserved = _amount(row["reserved_micro_usd"])
        actual = row["actual_micro_usd"]
        status = row["status"]
        if status == "settled":
            calculated_days[row["day"]][0] += _amount(actual)
        elif status in {"reserved", "uncertain"}:
            if actual is not None:
                raise ValueError("Unresolved reservation has conflicting actual usage")
            calculated_days[row["day"]][1] += reserved
        elif status == "released":
            if actual != 0:
                raise ValueError("Released reservation has conflicting actual usage")
        else:
            raise ValueError("Unknown reservation status")
    calculated_months: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for day, row in days.items():
        amounts = [_amount(row["spent_micro_usd"]), _amount(row["reserved_micro_usd"])]
        if amounts != calculated_days[day]:
            raise ValueError("Daily ledger differs from reservation evidence")
        calculated_months[day.replace(day=1)][0] += amounts[0]
        calculated_months[day.replace(day=1)][1] += amounts[1]
    if set(months) != set(calculated_months):
        raise ValueError("Monthly ledger coverage differs from daily evidence")
    for month, row in months.items():
        if (
            month.day != 1
            or [
                _amount(row["spent_micro_usd"]),
                _amount(row["reserved_micro_usd"]),
            ]
            != calculated_months[month]
        ):
            raise ValueError("Monthly ledger differs from daily evidence")
    return {
        "days": len(days),
        "months": len(months),
        "reservations": len(reservations),
        "spent_micro_usd": sum(row["spent_micro_usd"] for row in days.values()),
        "held_micro_usd": sum(row["reserved_micro_usd"] for row in days.values()),
        "unresolved_reservations": sum(
            row["status"] in {"reserved", "uncertain"} for row in reservations.values()
        ),
    }


def assert_target_subset(source: Snapshot, target: Snapshot) -> None:
    """Never overwrite independent target charges or change reservation identity."""
    validate_snapshot(source)
    validate_snapshot(target)
    for table, key in zip(TABLES[:2], ("day", "month"), strict=True):
        if not {r[key] for r in target[table]}.issubset(r[key] for r in source[table]):
            raise ValueError("Target has ledger dates absent from the source")
    by_id = {row["id"]: row for row in source[TABLES[2]]}
    transitions = {
        "reserved": {"reserved", "uncertain", "settled", "released"},
        "uncertain": {"uncertain", "settled"},
        "settled": {"settled"},
        "released": {"released"},
    }
    immutable = ("id", "day", "purpose", "reserved_micro_usd", "created_at")
    for row in target[TABLES[2]]:
        replacement = by_id.get(row["id"])
        if replacement is None:
            raise ValueError("Target has independent reservation IDs")
        if any(row[key] != replacement[key] for key in immutable):
            raise ValueError("Target reservation identity differs from source")
        if replacement["status"] not in transitions[row["status"]]:
            raise ValueError("Source would reverse target reservation accounting")
        if row["status"] in {"settled", "released"} and (
            row["actual_micro_usd"] != replacement["actual_micro_usd"]
        ):
            raise ValueError("Source would change an already settled target charge")


def load_snapshot(connection: psycopg.Connection) -> Snapshot:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT day,reserved_micro_usd,spent_micro_usd FROM generation_budget_day ORDER BY day"
        )
        days = cursor.fetchall()
        cursor.execute(
            "SELECT month,reserved_micro_usd,spent_micro_usd FROM generation_budget_month ORDER BY month"
        )
        months = cursor.fetchall()
        cursor.execute(
            "SELECT id,day,purpose,reserved_micro_usd,actual_micro_usd,status,created_at "
            "FROM generation_reservation ORDER BY id"
        )
        reservations = cursor.fetchall()
    return dict(zip(TABLES, (days, months, reservations), strict=True))


def synchronize(
    source: Snapshot, connection: psycopg.Connection, *, apply: bool
) -> dict:
    if connection.execute(
        "SELECT EXISTS (SELECT 1 FROM conversation) OR EXISTS (SELECT 1 FROM generation_run)"
    ).fetchone()[0]:
        raise ValueError(
            "Destination has conversations or runs; prelaunch sync is closed"
        )
    if connection.execute(
        "SELECT EXISTS (SELECT 1 FROM generation_reservation WHERE run_id IS NOT NULL)"
    ).fetchone()[0]:
        raise ValueError("Destination contains attached generation reservations")
    if apply:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('law-padi-prelaunch-spend-sync'))"
        )
        for table in TABLES:
            connection.execute(
                psycopg.sql.SQL("SELECT 1 FROM {} FOR UPDATE").format(
                    psycopg.sql.Identifier(table)
                )
            )
    current = load_snapshot(connection)
    assert_target_subset(source, current)
    before = validate_snapshot(current)
    if not apply:
        return before
    for row in source[TABLES[0]]:
        connection.execute(
            "INSERT INTO generation_budget_day(day,reserved_micro_usd,spent_micro_usd) VALUES (%s,%s,%s) "
            "ON CONFLICT(day) DO UPDATE SET reserved_micro_usd=excluded.reserved_micro_usd,spent_micro_usd=excluded.spent_micro_usd",
            (row["day"], row["reserved_micro_usd"], row["spent_micro_usd"]),
        )
    for row in source[TABLES[2]]:
        connection.execute(
            "INSERT INTO generation_reservation(id,day,purpose,reserved_micro_usd,actual_micro_usd,status,created_at,run_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,NULL) ON CONFLICT(id) DO UPDATE SET "
            "actual_micro_usd=excluded.actual_micro_usd,status=excluded.status,run_id=NULL",
            tuple(row[key] for key in RESERVATION_COLUMNS),
        )
    for row in source[TABLES[1]]:
        connection.execute(
            "INSERT INTO generation_budget_month(month,reserved_micro_usd,spent_micro_usd) VALUES (%s,%s,%s) "
            "ON CONFLICT(month) DO UPDATE SET reserved_micro_usd=excluded.reserved_micro_usd,spent_micro_usd=excluded.spent_micro_usd",
            (row["month"], row["reserved_micro_usd"], row["spent_micro_usd"]),
        )
    after = load_snapshot(connection)
    validate_snapshot(after)
    if after != source:
        raise ValueError(
            "Post-sync evidence differs; destination transaction rolled back"
        )
    return before


def _private_values(path: Path) -> dict:
    if path.stat().st_mode & 0o077:
        raise ValueError("Credential files must have private filesystem permissions")
    return dict(dotenv_values(path))


def _connection_urls(source_values: dict, target_values: dict) -> tuple[str, str]:
    source = source_values["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    target = target_values["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    a, b = urlparse(source), urlparse(target)
    if a.hostname not in {"localhost", "127.0.0.1"} or a.path != f"/{EXPECTED_SOURCE}":
        raise ValueError("Unexpected isolated source database")
    if b.hostname != EXPECTED_HOST or b.path != "/app" or b.username != "app_owner":
        raise ValueError("Unexpected Neon destination identity")
    query = dict(parse_qsl(b.query))
    if query.get("sslmode") != "verify-full":
        raise ValueError("Neon requires certificate and hostname verification")
    if sys.platform == "darwin":
        query["sslrootcert"] = certifi.where()
    return source, urlunparse(b._replace(query=urlencode(query)))


def verify_generation_disabled(api_url: str, runtime: dict) -> None:
    parts = urlparse(api_url)
    if (
        parts.scheme != "https"
        or not (parts.hostname or "").endswith(".onrender.com")
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        raise ValueError("Use the HTTPS Render service origin")
    secret = runtime.get("ORIGIN_PROXY_SECRET")
    if not secret:
        raise ValueError("Private Render origin credential is missing")
    with httpx.Client(timeout=120, follow_redirects=False, trust_env=False) as client:
        response = client.get(
            f"{api_url.rstrip('/')}/api/v1/conversations/capabilities",
            headers={"X-Origin-Proxy-Secret": secret},
        )
        response.raise_for_status()
        if response.json().get("explanations_enabled") is not False:
            raise ValueError("Actual Render generation must remain disabled")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--api-url")
    parser.add_argument("--collection-stopped", action="store_true")
    args = parser.parse_args()
    if args.apply and (not args.collection_stopped or not args.api_url):
        parser.error("--apply requires --collection-stopped and --api-url")
    source_values = _private_values(
        ROOT / "backend/storage/evaluations/current-v8-lexical.env"
    )
    target_values = _private_values(ROOT / "deployment/neon.env")
    runtime = _private_values(ROOT / "deployment/render.env")
    if (
        runtime.get("CHAT_GENERATION_ENABLED") != "false"
        or runtime.get("CHAT_GENERATION_KILL_SWITCH") != "true"
    ):
        raise ValueError(
            "Render environment must retain generation disabled and kill switch on"
        )
    source_url, target_url = _connection_urls(source_values, target_values)
    if args.apply:
        verify_generation_disabled(args.api_url, runtime)
    with psycopg.connect(source_url, connect_timeout=20) as source:
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        active = source.execute(
            "SELECT count(*) FROM generation_run WHERE status IN ('pending','running')"
        ).fetchone()[0]
        if args.apply and active:
            raise ValueError(
                "Stop collection and let active source runs finish before applying"
            )
        snapshot = load_snapshot(source)
        totals = validate_snapshot(snapshot)
        with psycopg.connect(target_url, connect_timeout=20) as target:
            if not args.apply:
                target.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
            before = synchronize(snapshot, target, apply=args.apply)
        report = {
            "at": datetime.now(UTC).isoformat(),
            "applied": args.apply,
            "source_database": EXPECTED_SOURCE,
            "target_host": EXPECTED_HOST,
            "source_active_runs": active,
            "source": totals,
            "target_before": before,
            "source_sha256": hashlib.sha256(
                json.dumps(snapshot, default=str, sort_keys=True).encode()
            ).hexdigest(),
            "source_read_only": True,
            "target_run_ids_detached": True,
        }
    (ROOT / "deployment/render/spend-sync.report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
