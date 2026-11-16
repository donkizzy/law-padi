from pathlib import Path

import httpx
import pytest

from app.ingestion.r2_blob_store import R2BlobStore
from scripts.migrate_local_documents import (
    archive_entry,
    archive_inventory,
    copy_manifest,
    restore_archive,
)


def test_review_archive_excludes_database_dumps_and_restores_relative_links(
    tmp_path: Path,
) -> None:
    root = tmp_path / "review"
    root.mkdir()
    (root / "notes").mkdir()
    (root / "notes" / "review.txt").write_bytes(b"review evidence")
    (root / "notes" / "database.dump").write_bytes(b"private dump")
    (root / "alias.txt").symlink_to("notes/review.txt")
    (root / "dump-alias").symlink_to("notes/database.dump")
    manifest = archive_inventory(root, "test-snapshot")
    assert [entry["path"] for entry in manifest["objects"]] == ["notes/review.txt"]
    assert set(manifest["symlinks"]) == {"alias.txt"}
    entry = archive_entry(manifest, "alias.txt")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith(entry["key"])
        return httpx.Response(200, content=b"review evidence")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        store = R2BlobStore(
            endpoint_url="https://example.test",
            bucket_name="lawpadi",
            access_key_id="test",
            secret_access_key="test",
            client=client,
        )
        restored = tmp_path / "restored"
        restore_archive(store, manifest, restored, None)
        assert (restored / "alias.txt").is_symlink()
        assert (restored / "alias.txt").readlink() == Path("notes/review.txt")
        assert (restored / "alias.txt").read_bytes() == b"review evidence"

        manifest["objects"][0]["path"] = "notes/database.dump"
        with pytest.raises(ValueError, match="Database backups belong"):
            copy_manifest(store, manifest, root, jobs=1)
