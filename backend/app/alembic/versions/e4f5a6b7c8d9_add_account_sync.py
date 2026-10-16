"""Keep saved provisions and preferences in the account."""

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_provision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_path", sa.String(length=512), nullable=False),
        sa.Column("release_version", sa.String(length=128), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "canonical_path", "release_version"),
    )
    op.create_index(
        op.f("ix_saved_provision_user_id"),
        "saved_provision",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enter_to_send", sa.Boolean(), nullable=False),
        sa.Column("follow_latest", sa.Boolean(), nullable=False),
        sa.Column("open_sources", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_index(op.f("ix_saved_provision_user_id"), table_name="saved_provision")
    op.drop_table("saved_provision")
