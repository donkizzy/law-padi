"""Enforce case insensitive user email uniqueness.

Revision ID: a3c3553158d1
Revises: b9c0d1e2f3a4
"""

import sqlalchemy as sa
from alembic import op

revision = "a3c3553158d1"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hold off account writes between the duplicate check and index creation.
    # A transactional build leaves the previous indexes intact on any failure.
    op.execute('LOCK TABLE "user" IN SHARE MODE')
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                'SELECT count(*) FROM (SELECT 1 FROM "user" '
                "GROUP BY lower(email) HAVING count(*) > 1) AS duplicate"
            )
        )
        .scalar_one()
    )
    if duplicates:
        # Report a count, not the addresses: migration output lands in deploy logs.
        raise RuntimeError(
            "Cannot enforce case-insensitive email uniqueness: "
            f"{duplicates} address(es) belong to more than one account. List them with "
            'SELECT lower(email) FROM "user" GROUP BY 1 HAVING count(*) > 1, resolve '
            "each account explicitly and rerun the migration; no data was deleted."
        )
    op.create_index(
        "ux_user_email_lower", "user", [sa.text("lower(email)")], unique=True
    )
    op.drop_index("ix_user_email_lower", table_name="user")
    op.drop_index("ix_user_email", table_name="user")


def downgrade() -> None:
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_email_lower", "user", [sa.text("lower(email)")])
    op.drop_index("ux_user_email_lower", table_name="user")
