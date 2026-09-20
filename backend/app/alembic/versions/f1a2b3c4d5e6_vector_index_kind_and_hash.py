"""Add vector index kind and profile hash

Revision ID: f1a2b3c4d5e6
Revises: e4f8a9c1d2b3
Create Date: 2026-09-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e4f8a9c1d2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vector_index",
        sa.Column("index_kind", sa.String(length=32), nullable=False, server_default="enacted"),
    )
    op.add_column(
        "vector_index",
        sa.Column("profile_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_vector_index_index_kind"), "vector_index", ["index_kind"], unique=False
    )
    op.create_index(
        op.f("ix_vector_index_profile_hash"),
        "vector_index",
        ["profile_hash"],
        unique=False,
    )
    # Migrate legacy default alias to the enacted alias for existing rows.
    op.execute(
        "UPDATE vector_index SET alias_name = 'constitution_enacted' "
        "WHERE alias_name = 'law_padi_production'"
    )
    op.execute(
        "UPDATE vector_index SET index_kind = 'enacted' WHERE index_kind IS NULL"
    )


def downgrade():
    op.drop_index(op.f("ix_vector_index_profile_hash"), table_name="vector_index")
    op.drop_index(op.f("ix_vector_index_index_kind"), table_name="vector_index")
    op.drop_column("vector_index", "profile_hash")
    op.drop_column("vector_index", "index_kind")
