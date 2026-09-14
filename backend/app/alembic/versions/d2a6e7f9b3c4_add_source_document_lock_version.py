"""Add source document lock version

Revision ID: d2a6e7f9b3c4
Revises: c8e5d1f0a4b2
Create Date: 2026-09-13 15:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d2a6e7f9b3c4"
down_revision = "c8e5d1f0a4b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "source_document",
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("source_document", "lock_version", server_default=None)


def downgrade():
    op.drop_column("source_document", "lock_version")
