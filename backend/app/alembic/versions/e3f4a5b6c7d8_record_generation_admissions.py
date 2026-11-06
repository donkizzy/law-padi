"""Keep short-lived generation quota records independent of chat history."""

import sqlalchemy as sa
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "c4b2a7619ef0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_admission",
        sa.Column("run_id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("guest_digest", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_generation_admission_user_time",
        "generation_admission",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_generation_admission_guest_time",
        "generation_admission",
        ["guest_digest", "created_at"],
    )
    op.create_index(
        "ix_generation_admission_created_at", "generation_admission", ["created_at"]
    )
    # Serialize the backfill with generation admission.
    op.execute("SELECT id FROM generation_capacity WHERE id = 1 FOR UPDATE")
    op.execute(
        """
        INSERT INTO generation_admission (run_id, user_id, guest_digest, created_at)
        SELECT run.id,
               conversation.user_id,
               CASE WHEN conversation.user_id IS NULL
                    THEN conversation.anonymous_session_id END,
               run.created_at
        FROM generation_run AS run
        JOIN conversation ON conversation.id = run.conversation_id
        WHERE run.created_at >= CURRENT_TIMESTAMP - INTERVAL '1 day'
          AND (conversation.user_id IS NOT NULL
               OR length(conversation.anonymous_session_id) = 64)
        """
    )


def downgrade() -> None:
    op.drop_table("generation_admission")
