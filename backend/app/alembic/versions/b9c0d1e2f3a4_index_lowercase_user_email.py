"""Index lower-cased user emails for case-insensitive account lookup."""

from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Not unique: existing addresses that differ only by case must keep working.
    op.execute('CREATE INDEX IF NOT EXISTS ix_user_email_lower ON "user" (lower(email))')


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_email_lower")
