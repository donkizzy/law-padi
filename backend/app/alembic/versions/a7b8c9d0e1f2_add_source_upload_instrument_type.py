"""Carry instrument type through quarantined source uploads."""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_upload",
        sa.Column(
            "instrument_type",
            sa.String(32),
            server_default="constitution",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("source_upload", "instrument_type")
