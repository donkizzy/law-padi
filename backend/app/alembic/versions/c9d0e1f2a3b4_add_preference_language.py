"""Save the reader's language with account preferences."""

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences", sa.Column("language", sa.String(16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "language")
