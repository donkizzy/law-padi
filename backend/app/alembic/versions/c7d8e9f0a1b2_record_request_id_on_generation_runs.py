"""Record the request that created each generation run.

Revision ID: c7d8e9f0a1b2
Revises: c4d5e6f7a8b9
"""

import sqlalchemy as sa
from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable without a default: a metadata-only change, and runs created
    # before this revision simply have no request to point to.
    op.add_column(
        "generation_run",
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_run", "request_id")
