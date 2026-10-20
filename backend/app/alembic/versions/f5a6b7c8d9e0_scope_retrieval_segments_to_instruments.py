"""Scope retrieval segments to their canonical instrument without re-embedding."""

import sqlalchemy as sa
from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_segment", sa.Column("instrument_id", sa.Uuid(), nullable=True)
    )
    # ALTER TABLE holds an exclusive lock until this transaction commits. The
    # published-row guard is suspended only for this deterministic FK backfill;
    # PostgreSQL restores the trigger state as well if the migration rolls back.
    op.execute(
        "ALTER TABLE retrieval_segment DISABLE TRIGGER retrieval_segment_immutable_release"
    )
    op.execute("""
        UPDATE retrieval_segment AS segment
        SET instrument_id = provision.instrument_id
        FROM provision
        WHERE provision.id = segment.provision_id
    """)
    op.execute(
        "ALTER TABLE retrieval_segment ENABLE TRIGGER retrieval_segment_immutable_release"
    )
    op.alter_column("retrieval_segment", "instrument_id", nullable=False)
    op.create_foreign_key(
        "fk_retrieval_segment_instrument_id",
        "retrieval_segment",
        "legal_instrument",
        ["instrument_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_retrieval_segment_instrument_id", "retrieval_segment", ["instrument_id"]
    )
    op.create_index(
        "ix_retrieval_segment_release_instrument",
        "retrieval_segment",
        ["release_id", "instrument_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retrieval_segment_release_instrument", table_name="retrieval_segment"
    )
    op.drop_index("ix_retrieval_segment_instrument_id", table_name="retrieval_segment")
    op.drop_constraint(
        "fk_retrieval_segment_instrument_id", "retrieval_segment", type_="foreignkey"
    )
    op.drop_column("retrieval_segment", "instrument_id")
