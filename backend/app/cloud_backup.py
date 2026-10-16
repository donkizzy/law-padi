"""Bounded database exports to a private, same-region Cloud Storage bucket."""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Timer
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.engine import make_url

from app.core.config import settings

_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)


class BackupError(RuntimeError):
    pass


def _existing_backup_result(response: httpx.Response, key: str) -> dict[str, str | int]:
    if not response.is_success:
        raise BackupError("Could not verify the existing backup")
    try:
        size = int(response.json()["size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BackupError("Existing backup size was not verified") from exc
    if size <= 0:
        raise BackupError("Existing backup was empty")
    return {"status": "already_exists", "object": key, "bytes": size}


def _export_database(path: Path) -> int:
    url = make_url(str(settings.DATABASE_URL))
    if not url.host or not url.database or not url.username:
        raise BackupError("Database backup connection is incomplete")
    environment = dict(os.environ)
    environment.update(
        PGHOST=url.host,
        PGPORT=str(url.port or 5432),
        PGUSER=url.username,
        PGPASSWORD=url.password or "",
        PGDATABASE=url.database,
        PGSSLMODE=str(url.query.get("sslmode", "require")),
        PGCONNECT_TIMEOUT="15",
    )
    if ssl_root_cert := url.query.get("sslrootcert"):
        environment["PGSSLROOTCERT"] = str(ssl_root_cert)
    # Credentials stay in the child environment, never the command line or logs.
    with path.open("wb") as destination:
        process = subprocess.Popen(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        timeout = Timer(settings.BACKUP_TIMEOUT_SECONDS, process.kill)
        timeout.daemon = True
        timeout.start()
        size = 0
        try:
            if process.stdout is None:
                raise BackupError("Database export did not provide a stream")
            while chunk := process.stdout.read(64 * 1024):
                size += len(chunk)
                if size > settings.BACKUP_MAX_BYTES:
                    raise BackupError(
                        "Database export exceeded the configured size limit"
                    )
                destination.write(chunk)
            if process.wait(timeout=5) != 0:
                raise BackupError("Database export failed")
        finally:
            timeout.cancel()
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()
    if not size:
        raise BackupError("Database export was empty")
    return size


def run_backup() -> dict[str, str | int]:
    """Create at most one immutable daily export; bucket lifecycle handles retention."""
    if not settings.GCS_BACKUP_BUCKET:
        raise BackupError("GCS_BACKUP_BUCKET is not configured")
    day = datetime.now(ZoneInfo("Africa/Lagos")).date().isoformat()
    key = f"{settings.GCS_BACKUP_PREFIX.strip('/')}/{day}.dump"
    bucket = quote(settings.GCS_BACKUP_BUCKET, safe="")
    object_url = (
        f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(key, safe='')}"
    )
    with httpx.Client(timeout=60, trust_env=False) as client:
        token_response = client.get(
            _TOKEN_URL, headers={"Metadata-Flavor": "Google"}, timeout=10
        )
        token_response.raise_for_status()
        access_token = str(token_response.json()["access_token"])
        headers = {"Authorization": f"Bearer {access_token}"}
        existing = client.get(object_url, headers=headers, timeout=10)
        if existing.is_success:
            return _existing_backup_result(existing, key)
        if existing.status_code != 404:
            raise BackupError("Could not check the backup destination")
        with TemporaryDirectory(prefix="law-padi-backup-") as directory:
            path = Path(directory) / "database.dump"
            size = _export_database(path)
            with path.open("rb") as stream:
                upload = client.post(
                    f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o",
                    params={
                        "uploadType": "media",
                        "name": key,
                        "ifGenerationMatch": "0",
                    },
                    headers={
                        **headers,
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(size),
                    },
                    content=stream,
                )
            if upload.status_code == 412:
                # A simultaneous scheduler retry already created today's export.
                existing = client.get(object_url, headers=headers, timeout=10)
                return _existing_backup_result(existing, key)
            if not upload.is_success:
                raise BackupError("Database backup upload failed")
            if int(upload.json().get("size", -1)) != size:
                raise BackupError("Backup upload size was not verified")
            return {"status": "created", "object": key, "bytes": size}
