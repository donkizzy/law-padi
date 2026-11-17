"""Remove unused remote-vector index storage.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def _legacy_rows() -> int:
    bind = op.get_bind()
    return int(
        bind.execute(sa.text("SELECT count(*) FROM vector_index")).scalar_one()
        + bind.execute(
            sa.text(
                "SELECT count(*) FROM release_promotion_attempt "
                "WHERE vector_index_id IS NOT NULL "
                "OR previous_collection_name IS NOT NULL "
                "OR target_collection_name IS NOT NULL"
            )
        ).scalar_one()
    )


def upgrade() -> None:
    # Dropping these columns discards history; stop instead if any exists so
    # the owner can export it first.
    if _legacy_rows() and os.environ.get("ALLOW_DROP_VECTOR_HISTORY") != "1":
        raise RuntimeError(
            "Remote-vector history exists in vector_index or the "
            "release_promotion_attempt collection columns. Export it, then rerun "
            "with ALLOW_DROP_VECTOR_HISTORY=1; nothing was changed."
        )
    op.drop_constraint(
        "release_promotion_attempt_vector_index_id_fkey",
        "release_promotion_attempt",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_release_promotion_attempt_vector_index_id",
        table_name="release_promotion_attempt",
    )
    op.drop_column("release_promotion_attempt", "vector_index_id")
    op.drop_column("release_promotion_attempt", "previous_collection_name")
    op.drop_column("release_promotion_attempt", "target_collection_name")
    op.drop_table("vector_index")
    op.drop_index(
        "ix_embedding_profile_supports_sparse", table_name="embedding_profile"
    )
    op.drop_column("embedding_profile", "supports_sparse")


def downgrade() -> None:
    op.add_column(
        "embedding_profile",
        sa.Column(
            "supports_sparse", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("embedding_profile", "supports_sparse", server_default=None)
    op.create_index(
        "ix_embedding_profile_supports_sparse", "embedding_profile", ["supports_sparse"]
    )
    op.create_table(
        "vector_index",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "release_id",
            sa.UUID(),
            sa.ForeignKey("corpus_release.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "embedding_run_id",
            sa.UUID(),
            sa.ForeignKey("embedding_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.UUID(),
            sa.ForeignKey("embedding_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("collection_name", sa.String(255), nullable=False),
        sa.Column("alias_name", sa.String(255), nullable=False),
        sa.Column("index_kind", sa.String(32), nullable=False),
        sa.Column("profile_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("point_count", sa.Integer(), nullable=False),
        sa.Column("vector_dimensions", sa.Integer(), nullable=False),
        sa.Column("payload_schema_hash", sa.String(64), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("validation_report", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "alias_name",
        "checksum",
        "collection_name",
        "embedding_run_id",
        "index_kind",
        "payload_schema_hash",
        "profile_hash",
        "profile_id",
        "release_id",
        "status",
    ):
        op.create_index(
            f"ix_vector_index_{column}",
            "vector_index",
            [column],
            unique=column == "collection_name",
        )
    op.add_column(
        "release_promotion_attempt",
        sa.Column("vector_index_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "release_promotion_attempt",
        sa.Column("previous_collection_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "release_promotion_attempt",
        sa.Column("target_collection_name", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_release_promotion_attempt_vector_index_id",
        "release_promotion_attempt",
        ["vector_index_id"],
    )
    op.create_foreign_key(
        "release_promotion_attempt_vector_index_id_fkey",
        "release_promotion_attempt",
        "vector_index",
        ["vector_index_id"],
        ["id"],
        ondelete="SET NULL",
    )
