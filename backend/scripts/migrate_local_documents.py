# ruff: noqa: T201
"""Inventory, copy and verify the local Compose document store and review archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.ingestion.blob_store import BlobStoreError, LocalBlobStore
from app.ingestion.contracts import BlobHead, CompletedMultipartUploadPart
from app.ingestion.r2_blob_store import R2BlobStore

STREAM_THRESHOLD = 16 * 1024 * 1024
PART_SIZE = 6 * 1024 * 1024
APP_PREFIXES = ("sources", "runs", "quarantine")
TERMINAL_UPLOADS = {"completed", "duplicate", "failed", "cancelled"}
DATABASE_BACKUP_SUFFIXES = (".dump", ".sql", ".sql.gz", ".bak", ".backup")
QUERIES = {
    "source_document": """
        SELECT id::text, storage_key, sha256, mime_type, file_size,
               storage_backend, storage_bucket FROM source_document ORDER BY id
    """,
    "ingestion_artifact": """
        SELECT id::text, storage_key, sha256, mime_type FROM ingestion_artifact ORDER BY id
    """,
    "source_upload": """
        SELECT id::text, quarantine_key, canonical_key, actual_sha256, expected_sha256,
               mime_type, expected_size, upload_backend, status, multipart_upload_id,
               lock_version FROM source_upload ORDER BY id
    """,
}


def r2_bucket_name() -> str:
    from app.core.config import settings

    bucket = (settings.R2_BUCKET_NAME or "").strip()
    if not bucket:
        raise ValueError("R2_BUCKET_NAME must be set before migrating documents")
    return bucket


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encode(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode()


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def save_new(path: Path, data: bytes) -> None:
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
    ) as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())


def safe_path(relative: str) -> PurePosixPath:
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or str(path) != relative
    ):
        raise ValueError(f"Invalid relative path: {relative}")
    return path


def database_rows(conn: Connection) -> dict[str, list[dict[str, Any]]]:
    if (
        conn.engine.url.host != "db"
        or conn.execute(text("SELECT current_database()")).scalar_one() != "app"
    ):
        raise ValueError("Expected the local Compose app database")
    return {
        table: [dict(row) for row in conn.execute(text(query)).mappings()]
        for table, query in QUERIES.items()
    }


def app_inventory(root: Path, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    references: dict[str, list[str]] = defaultdict(list)
    expected: dict[str, list[tuple[str | None, int | None]]] = defaultdict(list)
    content_types: dict[str, str] = {}
    for table in ("source_document", "ingestion_artifact"):
        for row in rows[table]:
            key = row["storage_key"]
            references[key].append(f"{table}:{row['id']}")
            expected[key].append((row["sha256"], row.get("file_size")))
            if row["mime_type"]:
                content_types[key] = row["mime_type"]

    upload_metadata = {}
    missing_history = []
    for row in rows["source_upload"]:
        ref = f"source_upload:{row['id']}"
        if key := row["canonical_key"]:
            references[key].append(f"{ref}:canonical")
            expected[key].append((row["actual_sha256"] or row["expected_sha256"], None))
        key = row["quarantine_key"]
        if (root / safe_path(key)).is_file() or row["status"] not in TERMINAL_UPLOADS:
            references[key].append(f"{ref}:quarantine")
            expected[key].append(
                (row["actual_sha256"] or row["expected_sha256"], row["expected_size"])
            )
            content_types[key] = row["mime_type"]
            upload_metadata[key] = {"source-upload-id": row["id"]}
        else:
            if row["status"] in {"completed", "duplicate"} and not row["canonical_key"]:
                raise ValueError(f"Completed upload has no canonical reference: {ref}")
            missing_history.append(ref)

    store = LocalBlobStore(root)
    entries = []
    for prefix in APP_PREFIXES:
        for path in sorted((root / prefix).rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Unexpected symlink in app blob tree: {path}")
            if not path.is_file() or path.name.endswith(".metadata.json"):
                continue
            key = path.relative_to(root).as_posix()
            head = store.head(key)
            sha = file_digest(path)
            size = path.stat().st_size
            if head.sha256 and head.sha256 != sha:
                raise ValueError(f"Local metadata checksum differs: {key}")
            for expected_sha, expected_size in expected[key]:
                if expected_sha and expected_sha != sha:
                    raise ValueError(f"Database checksum differs: {key}")
                if expected_size and expected_size != size:
                    raise ValueError(f"Database size differs: {key}")
            content_type = head.content_type
            if content_type == "application/octet-stream":
                content_type = content_types.get(key, content_type)
            entries.append(
                {
                    "path": key,
                    "key": key,
                    "sha256": sha,
                    "size": size,
                    "content_type": content_type,
                    "metadata": {
                        **head.metadata,
                        **upload_metadata.get(key, {}),
                        "sha256": sha,
                    },
                    "references": references.pop(key, []),
                }
            )
    if references:
        raise ValueError(f"Missing required app objects: {sorted(references)}")
    return {
        "kind": "app",
        "rows": rows,
        "objects": entries,
        "removed_quarantine": missing_history,
    }


def archive_inventory(root: Path, snapshot: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9-]+", snapshot):
        raise ValueError("Invalid archive snapshot ID")
    prefix = f"archive/local-compose/{snapshot}"
    entries, links, directories = [], {}, []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            target = path.resolve(strict=True)
            if not target.is_file() or not target.is_relative_to(root):
                raise ValueError(
                    f"Archive symlink must point to an internal file: {relative}"
                )
            if target.name.lower().endswith(DATABASE_BACKUP_SUFFIXES):
                continue
            links[relative] = {
                "original_target": os.readlink(path),
                "file": target.relative_to(root).as_posix(),
            }
        elif path.is_dir():
            directories.append(relative)
        elif path.is_file():
            if path.name.lower().endswith(DATABASE_BACKUP_SUFFIXES):
                continue
            sha = file_digest(path)
            entries.append(
                {
                    "path": relative,
                    "key": f"{prefix}/statute-review/{relative}",
                    "sha256": sha,
                    "size": path.stat().st_size,
                    "content_type": mimetypes.guess_type(path)[0]
                    or "application/octet-stream",
                    "metadata": {"sha256": sha},
                }
            )
        else:
            raise ValueError(f"Unsupported archive entry: {relative}")
    return {
        "kind": "archive",
        "manifest_key": f"{prefix}/manifest.json",
        "objects": entries,
        "symlinks": links,
        "directories": directories,
    }


def verify_bytes(entry: dict[str, Any], data: bytes) -> None:
    if len(data) != entry["size"] or digest(data) != entry["sha256"]:
        raise ValueError(f"Object bytes differ from inventory: {entry['key']}")


def copy_large_file(store: R2BlobStore, entry: dict[str, Any], path: Path) -> bool:
    key = entry["key"]
    upload = store.create_multipart_upload(
        key=key,
        content_type=entry["content_type"],
        part_count=(entry["size"] + PART_SIZE - 1) // PART_SIZE,
        metadata=entry["metadata"],
        expires_in_seconds=3600,
    )
    committed = False
    try:
        parts = []
        with path.open("rb") as stream, httpx.Client(timeout=90) as client:
            for part in upload.parts:
                data = stream.read(PART_SIZE)
                for attempt in range(4):
                    try:
                        response = client.put(part.upload_url, content=data)
                        if response.status_code in {429, 500, 502, 503, 504}:
                            raise httpx.TransportError("R2 part request can be retried")
                        if response.status_code != 200:
                            raise BlobStoreError(
                                f"R2 part upload failed for {key}: HTTP {response.status_code}"
                            )
                        break
                    except httpx.TransportError:
                        if attempt == 3:
                            raise
                        time.sleep(2**attempt)
                parts.append(
                    CompletedMultipartUploadPart(
                        part.part_number, response.headers["etag"]
                    )
                )
        committed = store.complete_multipart_upload_if_absent(
            key=key, upload_id=upload.upload_id, parts=parts
        )
        return committed
    finally:
        if not committed:
            try:
                store.abort_multipart_upload(key=key, upload_id=upload.upload_id)
            except FileNotFoundError:
                pass


def copy_object(
    store: R2BlobStore, entry: dict[str, Any], content: bytes | Path
) -> bool:
    key = entry["key"]
    if isinstance(content, Path):
        if (
            content.stat().st_size != entry["size"]
            or file_digest(content) != entry["sha256"]
        ):
            raise ValueError(f"Local file differs from inventory: {key}")
    else:
        verify_bytes(entry, content)
    for attempt in range(4):
        head: BlobHead | None
        try:
            try:
                head = store.head(key)
            except FileNotFoundError:
                if isinstance(content, Path):
                    created = copy_large_file(store, entry, content)
                else:
                    created = store.put_if_absent(
                        key=key,
                        content=content,
                        content_type=entry["content_type"],
                        metadata=entry["metadata"],
                    )
                head = None if created else store.head(key)
            else:
                created = False
            if isinstance(content, Path):
                checksum = hashlib.sha256()
                received = 0
                for chunk in store.iter_read(key):
                    checksum.update(chunk)
                    received += len(chunk)
                if received != entry["size"] or checksum.hexdigest() != entry["sha256"]:
                    raise ValueError(f"R2 object differs from inventory: {key}")
            else:
                verify_bytes(entry, store.read_bytes(key))
            if head is not None:
                if head.sha256 and head.sha256 != entry["sha256"]:
                    raise ValueError(f"Existing R2 checksum metadata differs: {key}")
                if head.content_type != entry["content_type"]:
                    raise ValueError(f"Existing R2 content type differs: {key}")
                if upload_id := entry["metadata"].get("source-upload-id"):
                    if head.metadata.get("source-upload-id") != upload_id:
                        raise ValueError(f"Existing R2 upload metadata differs: {key}")
            return created
        except (httpx.TransportError, BlobStoreError) as exc:
            if attempt == 3 or (
                isinstance(exc, BlobStoreError)
                and not re.search(r"HTTP (429|5\d\d)$", str(exc))
            ):
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def copy_manifest(
    store: R2BlobStore,
    manifest: dict[str, Any],
    root: Path,
    jobs: int,
    verified_objects: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    objects = manifest["objects"]
    if manifest["kind"] == "archive" and any(
        item["path"].lower().endswith(DATABASE_BACKUP_SUFFIXES) for item in objects
    ):
        raise ValueError("Database backups belong in the local backup")
    created = 0
    previously_verified = verified_objects or {}

    def transfer(entry: dict[str, Any]) -> bool:
        prior = previously_verified.get(entry["key"])
        if prior and all(
            entry[field] == prior[field]
            for field in ("sha256", "size", "content_type", "metadata")
        ):
            return False
        path = root / safe_path(entry["path"])
        if path.resolve() != path or not path.is_file():
            raise ValueError(f"Inventory file is missing or changed type: {path}")
        content = path if entry["size"] > STREAM_THRESHOLD else path.read_bytes()
        return copy_object(store, entry, content)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        pending = {executor.submit(transfer, item) for item in objects}
        try:
            for verified, result in enumerate(as_completed(pending), 1):
                created += result.result()
                if verified % 250 == 0:
                    print(f"Verified {verified}/{len(objects)} objects", flush=True)
        except BaseException:
            for future in pending:
                future.cancel()
            raise
    if manifest["kind"] == "archive":
        data = encode(manifest)
        copy_object(
            store,
            {
                "key": manifest["manifest_key"],
                "size": len(data),
                "sha256": digest(data),
                "content_type": "application/json",
                "metadata": {"sha256": digest(data)},
            },
            data,
        )
    return {
        "bucket": store.bucket_name,
        "endpoint": store.endpoint_url,
        "inventory_sha256": digest(encode(manifest)),
        "verified_objects": len(objects),
        "new_objects": created,
        "verified_bytes": sum(item["size"] for item in objects),
    }


def archive_entry(manifest: dict[str, Any], relative: str) -> dict[str, Any]:
    safe_path(relative)
    target = manifest["symlinks"].get(relative, {}).get("file", relative)
    for item in manifest["objects"]:
        if item["path"] == target:
            return cast(dict[str, Any], item)
    raise ValueError(f"Archive path not found: {relative}")


def restore_archive(
    store: R2BlobStore,
    manifest: dict[str, Any],
    destination: Path,
    relative: str | None,
    jobs: int = 8,
) -> None:
    if relative:
        entry = archive_entry(manifest, relative)
        data = store.read_bytes(entry["key"])
        verify_bytes(entry, data)
        save_new(destination, data)
        return
    destination.mkdir(mode=0o700)
    for directory in manifest["directories"]:
        (destination / safe_path(directory)).mkdir()

    def restore_entry(entry: dict[str, Any]) -> None:
        data = store.read_bytes(entry["key"])
        verify_bytes(entry, data)
        save_new(destination / safe_path(entry["path"]), data)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        for _ in executor.map(restore_entry, manifest["objects"]):
            pass
    for relative_path, link in manifest["symlinks"].items():
        path = destination / safe_path(relative_path)
        target = destination / safe_path(link["file"])
        original = Path(link["original_target"])
        if (
            not original.is_absolute()
            and (path.parent / original).resolve() == target.resolve()
        ):
            path.symlink_to(original)
        else:
            path.symlink_to(os.path.relpath(target, path.parent))


def require_receipt(
    store: R2BlobStore, manifest: dict[str, Any], receipt_path: Path
) -> None:
    receipt = read_json(receipt_path)
    if (
        receipt["bucket"] != store.bucket_name
        or receipt["endpoint"] != store.endpoint_url
        or receipt["inventory_sha256"] != digest(encode(manifest))
        or receipt["verified_objects"] != len(manifest["objects"])
    ):
        raise ValueError("Verification receipt does not match inventory or destination")


def change_database(
    conn: Connection,
    baseline: dict[str, list[dict[str, Any]]],
    *,
    rollback: bool = False,
) -> None:
    if conn.engine.url.host != "db":
        raise ValueError("Expected the Compose database host")
    bucket = r2_bucket_name()
    conn.execute(text("SET LOCAL lock_timeout = '5s'"))
    conn.execute(
        text(
            "LOCK TABLE source_document, source_upload, ingestion_artifact, ingestion_task "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    current = database_rows(conn)
    active = conn.execute(
        text(
            "SELECT count(*) FROM ingestion_task WHERE status IN ('pending', 'leased', 'running')"
        )
    ).scalar_one()
    if active:
        raise ValueError("Drain and pause ingestion tasks before changing storage")

    switched = deepcopy(baseline)
    for row in switched["source_document"]:
        if row["storage_backend"] != "local":
            raise ValueError(
                "Expected all inventoried source records to use local storage"
            )
        row["storage_backend"], row["storage_bucket"] = "r2", bucket
    for row in switched["source_upload"]:
        if row["status"] in TERMINAL_UPLOADS:
            continue
        if (
            row["status"] != "uploaded_pending_verification"
            or row["upload_backend"] != "local"
            or row["multipart_upload_id"]
        ):
            raise ValueError("Resolve active upload sessions before changing storage")
        row["upload_backend"] = "r2"

    before, after = (switched, baseline) if rollback else (baseline, switched)
    if current == after:
        return
    if current != before:
        raise ValueError(
            "Storage references changed since inventory; re-inventory before proceeding"
        )
    for row in after["source_document"]:
        conn.execute(
            text("""
            UPDATE source_document SET storage_backend = :storage_backend,
                storage_bucket = :storage_bucket WHERE id = CAST(:id AS uuid)
        """),
            row,
        )
    for row in after["source_upload"]:
        if row["status"] not in TERMINAL_UPLOADS:
            conn.execute(
                text("""
                UPDATE source_upload SET upload_backend = :upload_backend
                WHERE id = CAST(:id AS uuid)
            """),
                row,
            )
    if database_rows(conn) != after:
        raise ValueError("Storage reference update did not match the expected result")


def r2_store() -> R2BlobStore:
    from app.core.config import settings

    bucket = r2_bucket_name()
    endpoint = settings.R2_ENDPOINT_URL or ""
    url = urlsplit(endpoint)
    if url.scheme != "https" or not (url.hostname or "").endswith(
        ".r2.cloudflarestorage.com"
    ):
        raise ValueError("Expected a Cloudflare R2 HTTPS endpoint")
    return R2BlobStore(
        endpoint_url=endpoint,
        bucket_name=bucket,
        access_key_id=settings.R2_ACCESS_KEY_ID or "",
        secret_access_key=settings.R2_SECRET_ACCESS_KEY or "",
        client=httpx.Client(
            timeout=httpx.Timeout(150, connect=15),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=32),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("inventory-app")
    archive = commands.add_parser("inventory-archive")
    archive.add_argument("snapshot")
    copy = commands.add_parser("copy")
    copy.add_argument("--receipt", required=True, type=Path)
    copy.add_argument("--jobs", type=int, default=16)
    copy.add_argument("--verified-manifest", type=Path)
    copy.add_argument("--verified-receipt", type=Path)
    switch = commands.add_parser("switch")
    switch.add_argument("--receipt", required=True, type=Path)
    switch.add_argument("--archive-manifest", required=True, type=Path)
    switch.add_argument("--archive-receipt", required=True, type=Path)
    switch.add_argument("--rollback-record", required=True, type=Path)
    commands.add_parser("rollback")
    fetch = commands.add_parser("fetch-archive-manifest")
    fetch.add_argument("snapshot")
    lookup = commands.add_parser("lookup")
    lookup.add_argument("relative_path")
    restore = commands.add_parser("restore")
    restore.add_argument("destination", type=Path)
    restore.add_argument("--relative-path")
    restore.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()

    if (
        args.action in {"inventory-app", "inventory-archive", "copy", "switch"}
        and args.root is None
    ):
        parser.error("--root is required")
    root = args.root.resolve(strict=True) if args.root else None
    if args.action == "inventory-app":
        from app.core.db import engine

        assert root is not None
        with engine.connect() as conn:
            conn.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            )
            manifest = app_inventory(root, database_rows(conn))
        save_new(args.manifest, encode(manifest))
    elif args.action == "inventory-archive":
        assert root is not None
        save_new(args.manifest, encode(archive_inventory(root, args.snapshot)))
    elif args.action == "copy":
        assert root is not None
        if args.receipt.exists():
            parser.error("Receipt already exists")
        if bool(args.verified_manifest) != bool(args.verified_receipt):
            parser.error("Pass both the previous manifest and verification receipt")
        store = r2_store()
        prior = {}
        if args.verified_manifest:
            previous = read_json(args.verified_manifest)
            require_receipt(store, previous, args.verified_receipt)
            prior = {entry["key"]: entry for entry in previous["objects"]}
        receipt = copy_manifest(store, read_json(args.manifest), root, args.jobs, prior)
        save_new(args.receipt, encode(receipt))
        print(json.dumps(receipt))
    elif args.action in {"switch", "rollback"}:
        from app.core.db import engine

        manifest = read_json(args.manifest)
        if args.action == "switch":
            assert root is not None
            store = r2_store()
            require_receipt(store, manifest, args.receipt)
            require_receipt(
                store, read_json(args.archive_manifest), args.archive_receipt
            )
            with engine.connect() as conn:
                conn.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                if app_inventory(root, database_rows(conn)) != manifest:
                    raise ValueError(
                        "The local document volume or references changed since verification"
                    )
                keys = {entry["key"] for entry in manifest["objects"]}
                thumbnails = conn.execute(
                    text(
                        "SELECT DISTINCT thumbnail_key FROM source_page WHERE thumbnail_key IS NOT NULL"
                    )
                ).scalars()
                if missing := set(thumbnails) - keys:
                    raise ValueError(
                        f"Missing verified thumbnail objects: {sorted(missing)}"
                    )
            save_new(args.rollback_record, encode(manifest))
        with engine.begin() as conn:
            change_database(conn, manifest["rows"], rollback=args.action == "rollback")
        print(f"Database {args.action} complete")
    elif args.action == "fetch-archive-manifest":
        if not re.fullmatch(r"[a-z0-9-]+", args.snapshot):
            parser.error("Invalid archive snapshot ID")
        store = r2_store()
        key = f"archive/local-compose/{args.snapshot}/manifest.json"
        data = store.read_bytes(key)
        if store.head(key).sha256 != digest(data):
            raise ValueError("Remote archive manifest checksum differs")
        save_new(args.manifest, data)
    elif args.action == "lookup":
        entry = archive_entry(read_json(args.manifest), args.relative_path)
        print(f"s3://{r2_bucket_name()}/{entry['key']}")
    elif args.action == "restore":
        restore_archive(
            r2_store(),
            read_json(args.manifest),
            args.destination,
            args.relative_path,
            args.jobs,
        )


if __name__ == "__main__":
    main()
