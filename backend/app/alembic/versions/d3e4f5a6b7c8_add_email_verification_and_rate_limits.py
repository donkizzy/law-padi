"""Add email verification and Postgres-backed rate limits."""

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Accounts created before verification existed keep working: treat their
    # addresses as confirmed rather than locking them out of syncing.
    op.execute('UPDATE "user" SET email_verified_at = now()')
    op.create_table(
        "rate_limit_counter",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", "window_start"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_counter")
    op.drop_column("user", "email_verified_at")
