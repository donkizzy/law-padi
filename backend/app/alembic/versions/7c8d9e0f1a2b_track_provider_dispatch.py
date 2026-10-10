"""Track provider dispatch to avoid duplicate calls after worker crashes."""

import sqlalchemy as sa
from alembic import op

revision = "7c8d9e0f1a2b"
down_revision = "6b7c8d9e0f1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_run",
        sa.Column("provider_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_run", "provider_started_at")
