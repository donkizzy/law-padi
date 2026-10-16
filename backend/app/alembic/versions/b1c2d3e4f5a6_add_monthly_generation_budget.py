"""Add an atomic monthly spend ceiling, retaining previous provider usage."""

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a0f1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_budget_month",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("reserved_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("spent_micro_usd", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("month"),
    )
    # Daily rows already include uncertain reservations, including reservations
    # retained after conversation deletion. Do not reset that spend on upgrade.
    op.execute(
        """
        INSERT INTO generation_budget_month
            (month, reserved_micro_usd, spent_micro_usd)
        SELECT date_trunc('month', day)::date,
               SUM(reserved_micro_usd), SUM(spent_micro_usd)
        FROM generation_budget_day
        GROUP BY date_trunc('month', day)::date
        """
    )


def downgrade() -> None:
    op.drop_table("generation_budget_month")
