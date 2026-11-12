"""Count guest-tier generation admissions per client IP digest."""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_admission",
        sa.Column("client_digest", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_generation_admission_client_time",
        "generation_admission",
        ["client_digest", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_admission_client_time", table_name="generation_admission"
    )
    op.drop_column("generation_admission", "client_digest")
