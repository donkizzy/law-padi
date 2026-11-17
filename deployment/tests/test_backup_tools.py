import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "backup/backup_tools.py"
HOST = "example.proxy.rlwy.net"
URL = f"postgresql://postgres:secret-value@{HOST}:41234/app?sslmode=verify-full"


def pg_env(**variables: str) -> tuple[int, str, str]:
    """Run `backup_tools.py pg-env`; return its status, stderr and output file."""
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "postgres.env"
        environment = {"PATH": os.environ.get("PATH", ""), **variables}
        result = subprocess.run(
            [sys.executable, "-I", str(TOOLS), "pg-env", str(output)],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        written = output.read_text() if output.exists() else ""
    return result.returncode, result.stderr, written


class PgEnvTests(unittest.TestCase):
    def test_railway_proxy_url_is_verified_against_the_pinned_certificate(self):
        status, _, written = pg_env(
            BACKUP_DATABASE_URL=URL, EXPECTED_DATABASE_HOST=HOST
        )
        self.assertEqual(status, 0)
        values = dict(line.split("=", 1) for line in written.splitlines())
        self.assertEqual(values["PGHOST"], HOST)
        self.assertEqual(values["PGPORT"], "41234")
        self.assertEqual(values["PGDATABASE"], "app")
        self.assertEqual(values["PGSSLMODE"], "verify-full")
        self.assertEqual(values["PGSSLROOTCERT"], "/run/database-ca.crt")
        self.assertIn("default_transaction_read_only=on", values["PGOPTIONS"])

    def test_names_used_before_the_move_still_work(self):
        status, _, written = pg_env(
            NEON_BACKUP_DATABASE_URL=URL, EXPECTED_NEON_HOST=HOST
        )
        self.assertEqual(status, 0)
        self.assertIn(f"PGHOST={HOST}", written)

    def test_other_hosts_and_databases_are_refused_without_echoing_them(self):
        for url in (
            URL.replace(HOST, "other.proxy.rlwy.net"),
            URL.replace("/app?", "/other?"),
            URL.replace("postgres:secret-value@", ""),
        ):
            with self.subTest(url=url):
                status, stderr, written = pg_env(
                    BACKUP_DATABASE_URL=url, EXPECTED_DATABASE_HOST=HOST
                )
                self.assertEqual(status, 1)
                self.assertEqual(written, "")
                self.assertNotIn("secret-value", stderr)


if __name__ == "__main__":
    unittest.main()
