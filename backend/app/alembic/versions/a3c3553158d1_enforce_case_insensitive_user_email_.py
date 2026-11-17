"""Enforce case insensitive user email uniqueness.

Revision ID: a3c3553158d1
Revises: b9c0d1e2f3a4
"""

from alembic import op
import sqlalchemy as sa

revision = "a3c3553158d1"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hold off account writes between the duplicate check and index creation.
    # A transactional build leaves the previous indexes intact on any failure.
    op.execute('LOCK TABLE "user" IN SHARE MODE')
    duplicates = op.get_bind().execute(sa.text(
        'SELECT lower(email), count(*) FROM "user" '
        'GROUP BY lower(email) HAVING count(*) > 1 ORDER BY lower(email)'
    )).all()
    if duplicates:
        addresses = ", ".join(f"{email} ({count} accounts)" for email, count in duplicates)
        raise RuntimeError(
            "Cannot enforce case-insensitive email uniqueness: duplicate addresses: "
            f"{addresses}. Resolve these accounts explicitly and rerun the migration; no data was deleted."
        )
    op.create_index("ux_user_email_lower", "user", [sa.text("lower(email)")], unique=True)
    op.drop_index("ix_user_email_lower", table_name="user")
    op.drop_index("ix_user_email", table_name="user")


def downgrade() -> None:
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_email_lower", "user", [sa.text("lower(email)")])
    op.drop_index("ux_user_email_lower", table_name="user")
