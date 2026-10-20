"""Record the reader's answer language and English question text."""

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_message", sa.Column("english_text", sa.Text(), nullable=True)
    )
    op.add_column(
        "generation_run",
        sa.Column("answer_language", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_run", "answer_language")
    op.drop_column("conversation_message", "english_text")
