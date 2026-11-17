"""Exercise migrations in disposable databases, independent of the suite database."""

import subprocess
from collections.abc import Iterator
from pathlib import Path
from pprint import pformat
from uuid import uuid4

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import URL, make_url
from sqlalchemy.schema import CreateIndex

from app.core.config import settings
from app.models import SQLModel

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def migration_database() -> Iterator[URL]:
    base = make_url(str(settings.DATABASE_URL))
    name = f"app_w2_migrations_{uuid4().hex}_test"
    assert name.endswith("_test")
    admin = (
        base.set(database="postgres")
        .render_as_string(hide_password=False)
        .replace("postgresql+psycopg://", "postgresql://", 1)
    )
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            yield base.set(database=name)
        finally:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


def _migrate(url: URL, revision: str, *, direction: str = "upgrade") -> None:
    import os
    import sys

    env = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False))
    subprocess.run(
        [sys.executable, "-m", "alembic", direction, revision],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _schema_differences(url: URL) -> list:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"compare_type": True}
            )
            return compare_metadata(context, SQLModel.metadata)
    finally:
        engine.dispose()


def _drift_signature(differences: list) -> list[tuple]:
    signatures = []
    for difference in differences:
        operation, *details = difference
        if operation in {"add_index", "remove_index"}:
            signatures.append(
                (
                    operation,
                    str(CreateIndex(details[0]).compile(dialect=postgresql.dialect())),
                )
            )
        elif operation in {"add_fk", "remove_fk"}:
            constraint = details[0]
            signatures.append(
                (
                    operation,
                    constraint.table.fullname,
                    tuple(c.name for c in constraint.columns),
                    tuple(element.target_fullname for element in constraint.elements),
                    constraint.ondelete,
                    constraint.onupdate,
                    constraint.deferrable,
                    constraint.initially,
                    constraint.match,
                )
            )
        else:
            # Unknown operations must fail, including new columns and type changes.
            signatures.append((operation, repr(details)))
    return sorted(signatures, key=repr)


# PostgreSQL-specific indexes and FK actions currently differ from metadata.
# Pin every difference; new drift must fail rather than being silently ignored.
KNOWN_DRIFT = [
    (
        "add_fk",
        "active_retrieval_target",
        ("embedding_run_id",),
        ("embedding_run.id",),
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "add_fk",
        "active_retrieval_target",
        ("profile_id",),
        ("embedding_profile.id",),
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "add_fk",
        "active_retrieval_target",
        ("release_id",),
        ("corpus_release.id",),
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "add_fk",
        "active_retrieval_target",
        ("retrieval_index_build_id",),
        ("retrieval_index_build.id",),
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "add_index",
        "CREATE INDEX ix_active_retrieval_target_activated_by ON active_retrieval_target (activated_by)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_active_retrieval_target_embedding_run_id ON active_retrieval_target "
        "(embedding_run_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_active_retrieval_target_profile_id ON active_retrieval_target (profile_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_active_retrieval_target_release_id ON active_retrieval_target (release_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_active_retrieval_target_retrieval_index_build_id ON active_retrieval_target "
        "(retrieval_index_build_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_release_promotion_attempt_index_kind ON release_promotion_attempt (index_kind)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_release_promotion_attempt_retrieval_index_build_id ON release_promotion_attempt "
        "(retrieval_index_build_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_embedding_profile_id ON retrieval_embedding (profile_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_embedding_release_id ON retrieval_embedding (release_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_segment_index_kind ON retrieval_segment (index_kind)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_segment_provision_id ON retrieval_segment (provision_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_segment_provision_version_id ON retrieval_segment "
        "(provision_version_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_segment_release_entry_id ON retrieval_segment (release_entry_id)",
    ),
    (
        "add_index",
        "CREATE INDEX ix_retrieval_segment_source_document_id ON retrieval_segment (source_document_id)",
    ),
    (
        "remove_fk",
        "active_retrieval_target",
        ("embedding_run_id",),
        ("embedding_run.id",),
        "RESTRICT",
        None,
        None,
        None,
        None,
    ),
    (
        "remove_fk",
        "active_retrieval_target",
        ("profile_id",),
        ("embedding_profile.id",),
        "RESTRICT",
        None,
        None,
        None,
        None,
    ),
    (
        "remove_fk",
        "active_retrieval_target",
        ("release_id",),
        ("corpus_release.id",),
        "RESTRICT",
        None,
        None,
        None,
        None,
    ),
    (
        "remove_fk",
        "active_retrieval_target",
        ("retrieval_index_build_id",),
        ("retrieval_index_build.id",),
        "RESTRICT",
        None,
        None,
        None,
        None,
    ),
    (
        "remove_index",
        "CREATE INDEX ix_release_promotion_index_kind ON release_promotion_attempt (index_kind)",
    ),
    (
        "remove_index",
        "CREATE INDEX ix_release_promotion_retrieval_index_build_id ON release_promotion_attempt "
        "(retrieval_index_build_id)",
    ),
    (
        "remove_index",
        "CREATE INDEX ix_retrieval_embedding_release_profile ON retrieval_embedding (release_id, "
        "profile_id)",
    ),
    (
        "remove_index",
        "CREATE INDEX ix_retrieval_segment_search_vector ON retrieval_segment USING gin (search_vector)",
    ),
]


def test_empty_database_upgrades_without_unexpected_model_drift(
    migration_database: URL,
) -> None:
    _migrate(migration_database, "head")
    differences = _schema_differences(migration_database)
    assert _drift_signature(differences) == KNOWN_DRIFT, pformat(
        _drift_signature(differences), width=120
    )


def test_latest_revision_downgrades_and_upgrades(migration_database: URL) -> None:
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    head = scripts.get_current_head()
    assert head is not None
    revision = scripts.get_revision(head)
    assert revision is not None
    _migrate(migration_database, "head")
    _migrate(migration_database, "-1", direction="downgrade")
    engine = create_engine(migration_database)
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == revision.down_revision
            )
        _migrate(migration_database, "head")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == head
            )
        assert _drift_signature(_schema_differences(migration_database)) == KNOWN_DRIFT
    finally:
        engine.dispose()


def test_email_uniqueness_migration_aborts_without_deleting_duplicates(
    migration_database: URL,
) -> None:
    _migrate(migration_database, "b9c0d1e2f3a4")
    engine = create_engine(migration_database)
    try:
        with engine.begin() as connection:
            for email in ("Duplicate@example.test", "duplicate@example.test"):
                connection.execute(
                    text(
                        'INSERT INTO "user" (id, email, hashed_password, is_active, is_superuser) '
                        "VALUES (:id, :email, :password, true, false)"
                    ),
                    {"id": uuid4(), "email": email, "password": "unused"},
                )
        with pytest.raises(subprocess.CalledProcessError) as failure:
            _migrate(migration_database, "head")
        assert "1 address(es) belong to more than one account" in failure.value.stderr
        assert "duplicate@example.test" not in failure.value.stderr.lower()
        assert "no data was deleted" in failure.value.stderr
        with engine.connect() as connection:
            assert (
                connection.execute(text('SELECT count(*) FROM "user"')).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "b9c0d1e2f3a4"
            )
            assert connection.execute(
                text("SELECT to_regclass('ix_user_email_lower')")
            ).scalar_one()
            assert (
                connection.execute(
                    text("SELECT to_regclass('ux_user_email_lower')")
                ).scalar_one()
                is None
            )
        # An operator resolves the duplicate explicitly; retrying then succeeds.
        with engine.begin() as connection:
            connection.execute(
                text('UPDATE "user" SET email = :replacement WHERE email = :email'),
                {
                    "replacement": "resolved@example.test",
                    "email": "Duplicate@example.test",
                },
            )
        _migrate(migration_database, "head")
        with engine.begin() as connection:
            assert (
                connection.execute(text('SELECT count(*) FROM "user"')).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text("SELECT to_regclass('ix_user_email_lower')")
                ).scalar_one()
                is None
            )
            assert (
                connection.execute(
                    text("SELECT to_regclass('ix_user_email')")
                ).scalar_one()
                is None
            )
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text('UPDATE "user" SET email = :email WHERE email = :old'),
                {"email": "DUPLICATE@example.test", "old": "resolved@example.test"},
            )
    finally:
        engine.dispose()
