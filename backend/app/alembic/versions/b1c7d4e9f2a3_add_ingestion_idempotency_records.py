"""Add ingestion idempotency records

Revision ID: b1c7d4e9f2a3
Revises: a6f4c2d9e8b1
Create Date: 2026-09-12 00:15:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b1c7d4e9f2a3"
down_revision = "a6f4c2d9e8b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result_type", sa.String(length=128), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "result_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope",
            "idempotency_key",
            name="uq_idempotency_record_scope_key",
        ),
    )
    op.create_index(
        op.f("ix_idempotency_record_created_by"),
        "idempotency_record",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_record_idempotency_key"),
        "idempotency_record",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_record_request_hash"),
        "idempotency_record",
        ["request_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_record_result_id"),
        "idempotency_record",
        ["result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_record_result_type"),
        "idempotency_record",
        ["result_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_record_scope"),
        "idempotency_record",
        ["scope"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_idempotency_record_scope"), table_name="idempotency_record")
    op.drop_index(
        op.f("ix_idempotency_record_result_type"),
        table_name="idempotency_record",
    )
    op.drop_index(
        op.f("ix_idempotency_record_result_id"),
        table_name="idempotency_record",
    )
    op.drop_index(
        op.f("ix_idempotency_record_request_hash"),
        table_name="idempotency_record",
    )
    op.drop_index(
        op.f("ix_idempotency_record_idempotency_key"),
        table_name="idempotency_record",
    )
    op.drop_index(
        op.f("ix_idempotency_record_created_by"),
        table_name="idempotency_record",
    )
    op.drop_table("idempotency_record")
