"""Run the test suite only against a dedicated, migrated test database."""

import os
import subprocess
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import settings


def main() -> int:
    configured = os.environ.get("TEST_DATABASE_URL")
    source_url = make_url(str(settings.DATABASE_URL))
    target_url = (
        make_url(configured)
        if configured
        else source_url.set(
            database=source_url.database
            if (source_url.database or "").endswith("_test")
            else f"{source_url.database}_test"
        )
    )
    if not target_url.database or not target_url.database.endswith("_test"):
        raise RuntimeError("The test database name must end in '_test'")
    if target_url == source_url and not (source_url.database or "").endswith("_test"):
        raise RuntimeError("Refusing to test against the application database")

    admin_url = target_url.set(database="postgres")
    dsn = admin_url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (target_url.database,)
        ).fetchone()
        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(target_url.database)
                )
            )

    env = dict(os.environ)
    env["DATABASE_URL"] = target_url.render_as_string(hide_password=False)
    env["FASTAPI_ENV"] = "development"
    for command in (
        ["alembic", "upgrade", "head"],
        ["coverage", "run", "-m", "pytest", *(sys.argv[1:] or ["tests/"])],
        ["coverage", "report"],
        ["coverage", "html", "--title", "coverage"],
    ):
        result = subprocess.run(command, env=env, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
