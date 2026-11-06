"""Version account credentials and refresh tokens."""

import sqlalchemy as sa
from alembic import op

revision = "c4b2a7619ef0"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("user", "refresh_token"):
        op.add_column(
            table,
            sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for table in ("refresh_token", "user"):
        op.drop_column(table, "auth_version")
