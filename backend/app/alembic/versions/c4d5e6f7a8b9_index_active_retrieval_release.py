"""Index active retrieval targets by release."""

from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "a3c3553158d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_active_retrieval_target_release_id ON active_retrieval_target (release_id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_active_retrieval_target_release_id"
        )
