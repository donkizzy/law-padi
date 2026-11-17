#!/usr/bin/env python3
"""Small stdlib-only helpers; never emit database or object-store credentials."""

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

MAX_BYTES = 100 * 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def valid_size(value):
    if not 0 < int(value) <= MAX_BYTES:
        raise ValueError("Backup must be nonempty and at most 100 MiB")


def main():
    operation, *args = sys.argv[1:]
    if operation == "endpoint":
        endpoint = urlparse(os.environ["R2_BACKUP_ENDPOINT_URL"])
        if (
            endpoint.scheme != "https"
            or not re.fullmatch(
                r"[a-f0-9]{32}\.r2\.cloudflarestorage\.com", endpoint.hostname or ""
            )
            or endpoint.path not in {"", "/"}
            or endpoint.query
            or endpoint.fragment
            or endpoint.username
            or endpoint.port
        ):
            raise ValueError("Expected one HTTPS Cloudflare R2 endpoint")
    elif operation == "pg-env":
        # The NEON_* names are those used before the move to Railway.
        parsed = urlparse(
            os.environ.get("BACKUP_DATABASE_URL")
            or os.environ["NEON_BACKUP_DATABASE_URL"]
        )
        expected_host = (
            os.environ.get("EXPECTED_DATABASE_HOST") or os.environ["EXPECTED_NEON_HOST"]
        )
        if (
            parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}
            or parsed.hostname != expected_host
            or parsed.path != "/app"
            or not parsed.username
            or not parsed.password
        ):
            raise ValueError("Expected the explicitly authorized app database")
        query = parse_qs(parsed.query)
        values = {
            "PGHOST": parsed.hostname,
            "PGPORT": str(parsed.port or 5432),
            "PGUSER": unquote(parsed.username),
            "PGPASSWORD": unquote(parsed.password),
            "PGDATABASE": "app",
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": "/run/database-ca.crt",
            "PGCONNECT_TIMEOUT": "20",
            "PGAPPNAME": "constitution-private-backup",
            "PGOPTIONS": "-c default_transaction_read_only=on",
            "PGCHANNELBINDING": query.get("channel_binding", ["prefer"])[0],
        }
        if any("\n" in value or "\r" in value for value in values.values()):
            raise ValueError("Credential values must not contain newlines")
        descriptor = os.open(args[0], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            for key, value in values.items():
                handle.write(f"{key}={value}\n")
    elif operation == "key":
        if not re.fullmatch(
            r"postgres/app/\d{4}/\d{2}/\d{2}/app-\d{8}T\d{6}Z-\d+-\d+\.dump", args[0]
        ):
            raise ValueError("Choose an exact backup object key")
    elif operation == "digest":
        print(digest(args[0]))  # noqa: T201 -- Only a non-secret hash.
    elif operation == "manifest":
        dump, inventory_path, key, output = args
        size = Path(dump).stat().st_size
        valid_size(size)
        inventory = json.loads(Path(inventory_path).read_text())
        if (
            inventory["canonical_hash_errors"]
            or not inventory["canonical_count"]
            or not inventory["vector_count"]
            or not inventory["release"]
        ):
            raise ValueError("Source corpus inventory failed verification")
        manifest = {
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "object_key": key,
            "size_bytes": size,
            "sha256": digest(dump),
            "postgres_major": 18,
            "inventory": inventory,
        }
        Path(output).write_text(json.dumps(manifest, indent=2) + "\n")
    elif operation == "size":
        valid_size(json.loads(Path(args[0]).read_text())["ContentLength"])
    elif operation == "verify":
        dump, head_path, manifest_path = args
        head = json.loads(Path(head_path).read_text())
        manifest = json.loads(Path(manifest_path).read_text())
        size = Path(dump).stat().st_size
        valid_size(size)
        checksum = digest(dump)
        if (
            size != head["ContentLength"]
            or size != manifest["size_bytes"]
            or checksum != head["Metadata"]["sha256"]
            or checksum != manifest["sha256"]
            or manifest["postgres_major"] != 18
        ):
            raise ValueError("Downloaded backup size/hash verification failed")
    elif operation == "inventory":
        inventory = json.loads(Path(args[0]).read_text())
        manifest = json.loads(Path(args[1]).read_text())
        if inventory != manifest["inventory"] or inventory["canonical_hash_errors"]:
            raise ValueError("Restored schema/corpus/vector inventory differs")
    else:
        raise ValueError("Unknown backup operation")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # URL parsers and transport failures can contain private connection text.
        print(f"Backup validation failed ({type(error).__name__})", file=sys.stderr)  # noqa: T201
        sys.exit(1)
