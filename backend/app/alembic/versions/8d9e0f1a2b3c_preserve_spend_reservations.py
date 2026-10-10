"""Keep provider spend reservations after a conversation is deleted."""

import sqlalchemy as sa
from alembic import op

revision = "8d9e0f1a2b3c"
down_revision = "7c8d9e0f1a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "generation_reservation_run_id_fkey",
        "generation_reservation",
        type_="foreignkey",
    )
    op.alter_column("generation_reservation", "run_id", nullable=True)
    op.create_foreign_key(
        "fk_generation_reservation_run",
        "generation_reservation",
        "generation_run",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute("DELETE FROM generation_reservation WHERE run_id IS NULL")
    op.drop_constraint(
        "fk_generation_reservation_run", "generation_reservation", type_="foreignkey"
    )
    op.alter_column(
        "generation_reservation", "run_id", existing_type=sa.Uuid(), nullable=False
    )
    op.create_foreign_key(
        "generation_reservation_run_id_fkey",
        "generation_reservation",
        "generation_run",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
