"""Add PostgreSQL vector retrieval storage and active targets.

This is an expand migration. The legacy vector_index/Qdrant columns remain in
place so existing releases can be migrated and observed before contract cleanup.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2c7e8a9b0d1f"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "retrieval_segment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provision_version_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("index_kind", sa.String(length=32), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("citation", sa.String(length=255), nullable=False),
        sa.Column("canonical_path", sa.String(length=512), nullable=False),
        sa.Column(
            "ancestor_headings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("ancestor_text", sa.Text(), nullable=False),
        sa.Column("heading", sa.String(length=512), nullable=True),
        sa.Column("retrieval_text", sa.Text(), nullable=False),
        sa.Column("retrieval_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("authoritative_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("lexical_profile_version", sa.String(length=128), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', coalesce(citation, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(heading, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(ancestor_text, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(retrieval_text, '')), 'D')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("segment_index >= 1", name="ck_retrieval_segment_index_positive"),
        sa.CheckConstraint(
            "segment_count >= segment_index",
            name="ck_retrieval_segment_count_covers_index",
        ),
        sa.CheckConstraint("language = 'en'", name="ck_retrieval_segment_language_en"),
        sa.CheckConstraint(
            "retrieval_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_segment_text_hash",
        ),
        sa.CheckConstraint(
            "authoritative_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_segment_authoritative_hash",
        ),
        sa.ForeignKeyConstraint(["release_id"], ["corpus_release.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["release_entry_id"], ["corpus_release_entry.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["provision_id"], ["provision.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["provision_version_id"], ["provision_version.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "provision_version_id",
            "segment_index",
            name="uq_retrieval_segment_release_version_index",
        ),
    )
    op.create_index(
        "ix_retrieval_segment_release_id", "retrieval_segment", ["release_id"]
    )
    op.create_index(
        "ix_retrieval_segment_release_kind",
        "retrieval_segment",
        ["release_id", "index_kind"],
    )
    op.create_index(
        "ix_retrieval_segment_provision_version",
        "retrieval_segment",
        ["provision_version_id"],
    )
    op.create_index(
        "ix_retrieval_segment_canonical_path",
        "retrieval_segment",
        ["canonical_path"],
    )
    op.create_index(
        "ix_retrieval_segment_search_vector",
        "retrieval_segment",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "retrieval_embedding",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("embedding_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "vector_dimensions = 1024", name="ck_retrieval_embedding_dimensions"
        ),
        sa.CheckConstraint(
            "embedding_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_retrieval_embedding_hash",
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"], ["retrieval_segment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["corpus_release.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["embedding_run_id"], ["embedding_run.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["embedding_profile.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "embedding_run_id", "segment_id", name="uq_retrieval_embedding_run_segment"
        ),
    )
    # Altering the placeholder text column to vector keeps the migration
    # portable through Alembic's SQL renderer while still creating VECTOR(1024).
    op.execute(
        "ALTER TABLE retrieval_embedding ALTER COLUMN embedding TYPE vector(1024) "
        "USING embedding::vector"
    )
    op.create_index(
        "ix_retrieval_embedding_segment_id", "retrieval_embedding", ["segment_id"]
    )
    op.create_index(
        "ix_retrieval_embedding_release_profile",
        "retrieval_embedding",
        ["release_id", "profile_id"],
    )
    op.create_index(
        "ix_retrieval_embedding_embedding_run_id",
        "retrieval_embedding",
        ["embedding_run_id"],
    )
    op.create_check_constraint(
        "ck_retrieval_embedding_vector_dims",
        "retrieval_embedding",
        "vector_dims(embedding) = vector_dimensions",
    )

    op.create_table(
        "retrieval_index_build",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=False),
        sa.Column("index_kind", sa.String(length=32), nullable=False),
        sa.Column("relation_name", sa.String(length=128), nullable=False),
        sa.Column("physical_index_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_segment_count", sa.Integer(), nullable=False),
        sa.Column("stored_segment_count", sa.Integer(), nullable=False),
        sa.Column("stored_embedding_count", sa.Integer(), nullable=False),
        sa.Column("vector_dimensions", sa.Integer(), nullable=False),
        sa.Column("profile_hash", sa.String(length=64), nullable=True),
        sa.Column("payload_schema_hash", sa.String(length=64), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("backend = 'pgvector'", name="ck_retrieval_index_backend"),
        sa.CheckConstraint(
            "vector_dimensions = 1024", name="ck_retrieval_index_dimensions"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["corpus_release.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["embedding_run_id"], ["embedding_run.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["embedding_profile.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "embedding_run_id",
            "index_kind",
            name="uq_retrieval_index_build_release_run_kind",
        ),
    )
    op.create_index(
        "ix_retrieval_index_build_release_id", "retrieval_index_build", ["release_id"]
    )
    op.create_index(
        "ix_retrieval_index_build_embedding_run_id",
        "retrieval_index_build",
        ["embedding_run_id"],
    )
    op.create_index(
        "ix_retrieval_index_build_profile_id", "retrieval_index_build", ["profile_id"]
    )
    op.create_index(
        "ix_retrieval_index_build_index_kind", "retrieval_index_build", ["index_kind"]
    )
    op.create_index(
        "ix_retrieval_index_build_status", "retrieval_index_build", ["status"]
    )

    op.create_table(
        "active_retrieval_target",
        sa.Column("index_kind", sa.String(length=32), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "retrieval_index_build_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"], ["corpus_release.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["embedding_run_id"], ["embedding_run.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["retrieval_index_build_id"],
            ["retrieval_index_build.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["embedding_profile.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"], ["user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("index_kind"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_retrieval_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE release_status text;
        DECLARE release_id uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                release_id := OLD.release_id;
            ELSE
                release_id := NEW.release_id;
            END IF;
            SELECT status INTO release_status
            FROM corpus_release
            WHERE id = release_id;
            IF release_status IN ('approved', 'production') THEN
                RAISE EXCEPTION 'retrieval data for release % is immutable',
                    release_id;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    for table in ("retrieval_segment", "retrieval_embedding"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable_release "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_retrieval_mutation()"
        )


def downgrade() -> None:
    for table in ("retrieval_segment", "retrieval_embedding"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable_release ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_retrieval_mutation()")
    op.drop_table("active_retrieval_target")
    op.drop_index("ix_retrieval_index_build_status", table_name="retrieval_index_build")
    op.drop_index("ix_retrieval_index_build_index_kind", table_name="retrieval_index_build")
    op.drop_index("ix_retrieval_index_build_profile_id", table_name="retrieval_index_build")
    op.drop_index(
        "ix_retrieval_index_build_embedding_run_id", table_name="retrieval_index_build"
    )
    op.drop_index("ix_retrieval_index_build_release_id", table_name="retrieval_index_build")
    op.drop_table("retrieval_index_build")
    op.drop_index("ix_retrieval_embedding_embedding_run_id", table_name="retrieval_embedding")
    op.drop_index("ix_retrieval_embedding_release_profile", table_name="retrieval_embedding")
    op.drop_index("ix_retrieval_embedding_segment_id", table_name="retrieval_embedding")
    op.drop_table("retrieval_embedding")
    op.drop_index("ix_retrieval_segment_search_vector", table_name="retrieval_segment")
    op.drop_index("ix_retrieval_segment_canonical_path", table_name="retrieval_segment")
    op.drop_index("ix_retrieval_segment_provision_version", table_name="retrieval_segment")
    op.drop_index("ix_retrieval_segment_release_kind", table_name="retrieval_segment")
    op.drop_index("ix_retrieval_segment_release_id", table_name="retrieval_segment")
    op.drop_table("retrieval_segment")
    op.execute("DROP EXTENSION IF EXISTS vector")
