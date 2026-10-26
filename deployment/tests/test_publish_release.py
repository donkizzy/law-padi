import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "publish_release.py"
spec = importlib.util.spec_from_file_location("publish_release", MODULE)
assert spec and spec.loader
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

LOCAL = "postgresql://postgres:x@localhost:5432/app"
NEON = f"postgresql://app_owner:x@{publish.NEON_HOST}/app?sslmode=require"


class PublishReleaseTests(unittest.TestCase):
    def test_production_neon_and_rehearsal_copies_are_the_only_targets(self):
        self.assertTrue(publish.check_identities(LOCAL, NEON))
        self.assertFalse(
            publish.check_identities(
                LOCAL, "postgresql://postgres:x@localhost/app_neon_rehearsal_20261026"
            )
        )
        for target in (
            LOCAL,
            "postgresql://postgres:x@localhost/app_test",
            f"postgresql://app_owner:x@{publish.NEON_HOST}/other",
            "postgresql://app_owner:x@ep-other.neon.tech/app",
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                publish.check_identities(LOCAL, target)

    def test_source_must_be_the_local_app_database(self):
        with self.assertRaises(ValueError):
            publish.check_identities(NEON, NEON)

    def test_neon_connections_verify_the_server_certificate(self):
        url = publish.verified_tls(NEON)
        self.assertIn("sslmode=verify-full", url)
        self.assertIn("sslrootcert=", url)
        self.assertNotIn("sslmode=require", url)

    def test_copied_rows_drop_local_references_and_stay_inactive(self):
        def rendered(table, names):
            return [
                value.as_string(None)
                for value in publish.expressions(table, names, "lawpadi")
            ]

        self.assertEqual(
            rendered("corpus_release", ["id", "status", "approved_by"]),
            ['"id"', "'building'", "NULL"],
        )
        self.assertEqual(rendered("retrieval_index_build", ["status"]), ["'ready'"])
        self.assertEqual(
            rendered("corpus_release_entry", ["ingestion_run_id"]), ["NULL"]
        )
        self.assertEqual(
            rendered(
                "source_document",
                ["storage_backend", "storage_bucket", "created_by", "sha256"],
            ),
            ["'r2'", "'lawpadi'", "NULL", '"sha256"'],
        )

    def test_commands_roll_back_unless_applied(self):
        with (
            patch.object(
                sys,
                "argv",
                ["publish_release.py", "activate", "--release-version", "v"],
            ),
            patch.object(publish, "database_url", side_effect=[LOCAL, NEON]),
            patch.object(publish, "verified_tls", side_effect=lambda url: url),
            patch.object(publish.psycopg, "connect") as connect,
            patch.object(publish, "activate_release", return_value={}),
        ):
            publish.main()
        target = connect.return_value.__enter__.return_value
        target.rollback.assert_called_once()
        target.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
