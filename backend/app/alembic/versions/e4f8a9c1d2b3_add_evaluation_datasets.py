"""Add evaluation datasets

Revision ID: e4f8a9c1d2b3
Revises: d2a6e7f9b3c4
Create Date: 2026-09-13 18:10:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e4f8a9c1d2b3"
down_revision = "d2a6e7f9b3c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluation_dataset",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dataset_kind", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("jurisdiction", sa.String(length=255), nullable=False),
        sa.Column("instrument_slug", sa.String(length=255), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_dataset_content_sha256"),
        "evaluation_dataset",
        ["content_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_dataset_kind"),
        "evaluation_dataset",
        ["dataset_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_instrument_slug"),
        "evaluation_dataset",
        ["instrument_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_is_active"),
        "evaluation_dataset",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_jurisdiction"),
        "evaluation_dataset",
        ["jurisdiction"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_language"),
        "evaluation_dataset",
        ["language"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_source_document_id"),
        "evaluation_dataset",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_dataset_version"),
        "evaluation_dataset",
        ["version"],
        unique=True,
    )

    op.create_table(
        "evaluation_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_key", sa.String(length=255), nullable=False),
        sa.Column("item_kind", sa.String(length=32), nullable=False),
        sa.Column("canonical_path", sa.String(length=512), nullable=True),
        sa.Column("provision_kind", sa.String(length=32), nullable=True),
        sa.Column("section_number", sa.String(length=64), nullable=True),
        sa.Column("citation", sa.String(length=255), nullable=True),
        sa.Column("expected_text", sa.Text(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column(
            "expected_canonical_paths",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("source_page_start", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("source_spans", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(item_kind <> 'gold_provision') OR "
            "(canonical_path IS NOT NULL AND expected_text IS NOT NULL)",
            name="ck_evaluation_item_gold_provision_fields",
        ),
        sa.CheckConstraint(
            "(item_kind <> 'retrieval_query') OR "
            "(query_text IS NOT NULL AND expected_canonical_paths IS NOT NULL)",
            name="ck_evaluation_item_retrieval_query_fields",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["evaluation_dataset.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_id",
            "item_key",
            name="uq_evaluation_item_dataset_key",
        ),
    )
    op.create_index(
        op.f("ix_evaluation_item_canonical_path"),
        "evaluation_item",
        ["canonical_path"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_item_dataset_id"),
        "evaluation_item",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_item_item_key"),
        "evaluation_item",
        ["item_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_item_item_kind"),
        "evaluation_item",
        ["item_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_item_provision_kind"),
        "evaluation_item",
        ["provision_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_item_section_number"),
        "evaluation_item",
        ["section_number"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_evaluation_item_section_number"), table_name="evaluation_item")
    op.drop_index(op.f("ix_evaluation_item_provision_kind"), table_name="evaluation_item")
    op.drop_index(op.f("ix_evaluation_item_item_kind"), table_name="evaluation_item")
    op.drop_index(op.f("ix_evaluation_item_item_key"), table_name="evaluation_item")
    op.drop_index(op.f("ix_evaluation_item_dataset_id"), table_name="evaluation_item")
    op.drop_index(op.f("ix_evaluation_item_canonical_path"), table_name="evaluation_item")
    op.drop_table("evaluation_item")
    op.drop_index(op.f("ix_evaluation_dataset_version"), table_name="evaluation_dataset")
    op.drop_index(
        op.f("ix_evaluation_dataset_source_document_id"),
        table_name="evaluation_dataset",
    )
    op.drop_index(op.f("ix_evaluation_dataset_language"), table_name="evaluation_dataset")
    op.drop_index(
        op.f("ix_evaluation_dataset_jurisdiction"), table_name="evaluation_dataset"
    )
    op.drop_index(
        op.f("ix_evaluation_dataset_is_active"), table_name="evaluation_dataset"
    )
    op.drop_index(
        op.f("ix_evaluation_dataset_instrument_slug"),
        table_name="evaluation_dataset",
    )
    op.drop_index(
        op.f("ix_evaluation_dataset_dataset_kind"), table_name="evaluation_dataset"
    )
    op.drop_index(
        op.f("ix_evaluation_dataset_content_sha256"),
        table_name="evaluation_dataset",
    )
    op.drop_table("evaluation_dataset")
