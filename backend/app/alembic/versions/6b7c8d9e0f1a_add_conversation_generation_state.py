"""Add pinned conversations, evidence snapshots, durable runs, and spend records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "6b7c8d9e0f1a"
down_revision = "5a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("pinned_release_id", sa.Uuid(), nullable=True))
    op.add_column("conversation", sa.Column("pinned_index_build_id", sa.Uuid(), nullable=True))
    op.add_column("conversation", sa.Column("index_kind", sa.String(32), nullable=False, server_default="enacted"))
    op.create_foreign_key("fk_conversation_pinned_release", "conversation", "corpus_release", ["pinned_release_id"], ["id"])
    op.create_foreign_key("fk_conversation_pinned_index", "conversation", "retrieval_index_build", ["pinned_index_build_id"], ["id"])
    op.create_index("ix_conversation_pinned_release_id", "conversation", ["pinned_release_id"])
    op.create_index("ix_conversation_pinned_index_build_id", "conversation", ["pinned_index_build_id"])

    for name, column in (
        ("answer_content", postgresql.JSONB()),
        ("evidence_snapshot", postgresql.JSONB()),
        ("usage", postgresql.JSONB()),
        ("validation_result", postgresql.JSONB()),
    ):
        op.add_column("conversation_message", sa.Column(name, column, nullable=True))
    op.add_column("conversation_message", sa.Column("prompt_version", sa.String(64), nullable=True))
    op.add_column("message_evidence", sa.Column("release_id", sa.Uuid(), nullable=True))
    op.add_column("message_evidence", sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=True))
    op.create_foreign_key("fk_message_evidence_release", "message_evidence", "corpus_release", ["release_id"], ["id"])
    op.create_index("ix_message_evidence_release_id", "message_evidence", ["release_id"])

    op.create_table(
        "generation_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_message_id", sa.Uuid(), sa.ForeignKey("conversation_message.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(), sa.ForeignKey("conversation_message.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_generation_run_submission"),
    )
    op.create_index("ix_generation_run_conversation_id", "generation_run", ["conversation_id"])
    op.create_index("ix_generation_run_status", "generation_run", ["status"])
    op.create_index("ix_generation_run_one_active", "generation_run", ["conversation_id"], unique=True, postgresql_where=sa.text("status IN ('pending', 'running')"))
    op.create_table(
        "generation_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("generation_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_event_conversation_id", "generation_event", ["conversation_id"])
    op.create_index("ix_generation_event_run_id", "generation_event", ["run_id"])
    op.create_table(
        "generation_budget_day",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("reserved_micro_usd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("spent_micro_usd", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "generation_reservation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("generation_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), sa.ForeignKey("generation_budget_day.day"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("reserved_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("actual_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_reservation_run_id", "generation_reservation", ["run_id"])
    op.create_index("ix_generation_reservation_day", "generation_reservation", ["day"])
    op.create_table(
        "generation_capacity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO generation_capacity (id, active_count) VALUES (1, 0)")


def downgrade() -> None:
    op.drop_table("generation_capacity")
    op.drop_table("generation_reservation")
    op.drop_table("generation_budget_day")
    op.drop_table("generation_event")
    op.drop_table("generation_run")
    op.drop_index("ix_message_evidence_release_id", table_name="message_evidence")
    op.drop_constraint("fk_message_evidence_release", "message_evidence", type_="foreignkey")
    op.drop_column("message_evidence", "evidence_snapshot")
    op.drop_column("message_evidence", "release_id")
    for name in ("prompt_version", "validation_result", "usage", "evidence_snapshot", "answer_content"):
        op.drop_column("conversation_message", name)
    op.drop_index("ix_conversation_pinned_index_build_id", table_name="conversation")
    op.drop_index("ix_conversation_pinned_release_id", table_name="conversation")
    op.drop_constraint("fk_conversation_pinned_index", "conversation", type_="foreignkey")
    op.drop_constraint("fk_conversation_pinned_release", "conversation", type_="foreignkey")
    op.drop_column("conversation", "index_kind")
    op.drop_column("conversation", "pinned_index_build_id")
    op.drop_column("conversation", "pinned_release_id")
