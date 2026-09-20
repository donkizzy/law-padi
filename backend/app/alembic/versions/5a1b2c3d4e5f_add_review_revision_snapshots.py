"""Persist structured review revision snapshots and issue resolution evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "5a1b2c3d4e5f"
down_revision = "4e9a0b1c2d3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_revision",
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "candidate_revision",
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "candidate_revision",
        sa.Column("changed_fields", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "review_issue",
        sa.Column("resolution_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "review_issue",
        sa.Column("resolution_evidence", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_issue", "resolution_evidence")
    op.drop_column("review_issue", "resolution_reason")
    op.drop_column("candidate_revision", "changed_fields")
    op.drop_column("candidate_revision", "after_snapshot")
    op.drop_column("candidate_revision", "before_snapshot")
