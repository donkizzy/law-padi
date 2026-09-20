"""Enforce the V1 embedding dimension contract."""

from alembic import op


revision = "4e9a0b1c2d3f"
down_revision = "3d8f9a0b1c2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy profiles remain readable for migration evidence but cannot be
    # selected for new runs after this expand migration.
    op.execute(
        "UPDATE embedding_profile SET is_active = false "
        "WHERE vector_dimensions <> 1024"
    )
    op.create_check_constraint(
        "ck_embedding_profile_vector_dimensions",
        "embedding_profile",
        "vector_dimensions = 1024",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_embedding_profile_vector_dimensions", "embedding_profile", type_="check"
    )
