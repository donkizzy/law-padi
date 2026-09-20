"""Add pgvector promotion evidence fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3d8f9a0b1c2e"
down_revision = "2c7e8a9b0d1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "release_promotion_attempt",
        sa.Column("retrieval_index_build_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "release_promotion_attempt",
        sa.Column("index_kind", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_release_promotion_retrieval_build",
        "release_promotion_attempt",
        "retrieval_index_build",
        ["retrieval_index_build_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_release_promotion_retrieval_index_build_id",
        "release_promotion_attempt",
        ["retrieval_index_build_id"],
    )
    op.create_index(
        "ix_release_promotion_index_kind",
        "release_promotion_attempt",
        ["index_kind"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_release_promotion_index_kind", table_name="release_promotion_attempt"
    )
    op.drop_index(
        "ix_release_promotion_retrieval_index_build_id",
        table_name="release_promotion_attempt",
    )
    op.drop_constraint(
        "fk_release_promotion_retrieval_build",
        "release_promotion_attempt",
        type_="foreignkey",
    )
    op.drop_column("release_promotion_attempt", "index_kind")
    op.drop_column("release_promotion_attempt", "retrieval_index_build_id")
