"""Fit every benchmark of a composite release on its embedding run."""

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "embedding_run",
        "benchmark_dataset_version",
        existing_type=sa.String(128),
        type_=sa.String(2048),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "embedding_run",
        "benchmark_dataset_version",
        existing_type=sa.String(2048),
        type_=sa.String(128),
        existing_nullable=True,
    )
