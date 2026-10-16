"""Store owner-submitted answer usefulness independently of validation."""

import sqlalchemy as sa
from alembic import op

revision = "a0f1b2c3d4e5"
down_revision = "9e0f1a2b3c4d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["conversation_message.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_message_feedback_updated_at", "message_feedback", ["updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_message_feedback_updated_at", table_name="message_feedback")
    op.drop_table("message_feedback")
