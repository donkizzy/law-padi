"""Add production ingestion workflow schema

Revision ID: 4d2f3a7c9b81
Revises: 7f4d9c2a1b6e
Create Date: 2026-09-01 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "4d2f3a7c9b81"
down_revision = "7f4d9c2a1b6e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "source_document",
        sa.Column("storage_backend", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "source_document",
        sa.Column("storage_bucket", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "source_document",
        sa.Column("original_filename", sa.String(length=512), nullable=True),
    )
    op.add_column("source_document", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("source_document", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column(
        "source_document",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_source_document_created_by_user",
        "source_document",
        "user",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_source_document_created_by"),
        "source_document",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_document_storage_backend"),
        "source_document",
        ["storage_backend"],
        unique=False,
    )

    op.add_column(
        "corpus_release",
        sa.Column(
            "validation_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "corpus_release",
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("corpus_release", "lock_version", server_default=None)
    op.create_index(
        "ix_corpus_release_single_production",
        "corpus_release",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'production'"),
    )

    op.create_table(
        "source_upload",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legal_instrument_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("instrument_slug", sa.String(length=255), nullable=False),
        sa.Column("instrument_title", sa.String(length=512), nullable=False),
        sa.Column("instrument_short_title", sa.String(length=255), nullable=True),
        sa.Column("instrument_year", sa.Integer(), nullable=False),
        sa.Column("instrument_status", sa.String(length=32), nullable=False),
        sa.Column("enacted_at", sa.Date(), nullable=True),
        sa.Column("effective_at", sa.Date(), nullable=True),
        sa.Column("ceased_at", sa.Date(), nullable=True),
        sa.Column("source_title", sa.String(length=512), nullable=False),
        sa.Column("authority", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_tier", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.Date(), nullable=False),
        sa.Column("retrieved_at", sa.Date(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("actual_sha256", sa.String(length=64), nullable=True),
        sa.Column("upload_backend", sa.String(length=64), nullable=False),
        sa.Column("quarantine_key", sa.String(length=1024), nullable=False),
        sa.Column("canonical_key", sa.String(length=1024), nullable=True),
        sa.Column("multipart_upload_id", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expected_size > 0", name="ck_source_upload_expected_size"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["legal_instrument_id"], ["legal_instrument.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quarantine_key", name="uq_source_upload_quarantine_key"),
    )
    op.create_index(
        op.f("ix_source_upload_canonical_key"),
        "source_upload",
        ["canonical_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_actual_sha256"),
        "source_upload",
        ["actual_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_authority"),
        "source_upload",
        ["authority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_created_by"),
        "source_upload",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_expected_sha256"),
        "source_upload",
        ["expected_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_idempotency_key"),
        "source_upload",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_source_upload_instrument_slug"),
        "source_upload",
        ["instrument_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_instrument_status"),
        "source_upload",
        ["instrument_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_instrument_year"),
        "source_upload",
        ["instrument_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_legal_instrument_id"),
        "source_upload",
        ["legal_instrument_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_source_document_id"),
        "source_upload",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_source_tier"),
        "source_upload",
        ["source_tier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_upload_status"), "source_upload", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_source_upload_upload_backend"),
        "source_upload",
        ["upload_backend"],
        unique=False,
    )

    op.create_table(
        "ingestion_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_upload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("pipeline_version", sa.String(length=128), nullable=False),
        sa.Column(
            "pipeline_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("expected_page_count", sa.Integer(), nullable=True),
        sa.Column("total_units", sa.Integer(), nullable=False),
        sa.Column("completed_units", sa.Integer(), nullable=False),
        sa.Column("failed_units", sa.Integer(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column(
            "error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_upload_id"], ["source_upload.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_run_created_by"),
        "ingestion_run",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_run_current_stage"),
        "ingestion_run",
        ["current_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_run_source_document_id"),
        "ingestion_run",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_run_source_upload_id"),
        "ingestion_run",
        ["source_upload_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_run_status"), "ingestion_run", ["status"], unique=False
    )

    op.create_table(
        "ingestion_step",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_units", sa.Integer(), nullable=False),
        sa.Column("completed_units", sa.Integer(), nullable=False),
        sa.Column("failed_units", sa.Integer(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dependency_step_id"], ["ingestion_step.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_ingestion_step_idempotency_key"
        ),
        sa.UniqueConstraint("run_id", "stage", name="uq_ingestion_step_run_stage"),
    )
    op.create_index(
        op.f("ix_ingestion_step_dependency_step_id"),
        "ingestion_step",
        ["dependency_step_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_step_lease_owner"),
        "ingestion_step",
        ["lease_owner"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_step_run_id"),
        "ingestion_step",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_step_stage"), "ingestion_step", ["stage"], unique=False
    )
    op.create_index(
        op.f("ix_ingestion_step_status"), "ingestion_step", ["status"], unique=False
    )

    op.create_table(
        "ingestion_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["ingestion_step.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_ingestion_event_sequence"),
    )
    op.create_index(
        op.f("ix_ingestion_event_event_type"),
        "ingestion_event",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_event_run_id"),
        "ingestion_event",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_event_sequence"),
        "ingestion_event",
        ["sequence"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_event_stage"),
        "ingestion_event",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_event_step_id"),
        "ingestion_event",
        ["step_id"],
        unique=False,
    )

    op.create_table(
        "ingestion_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["ingestion_step.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_task_idempotency_key"),
        "ingestion_task",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ingestion_task_lease_owner"),
        "ingestion_task",
        ["lease_owner"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_task_priority"),
        "ingestion_task",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_task_run_id"),
        "ingestion_task",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_task_status"),
        "ingestion_task",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_task_step_id"),
        "ingestion_task",
        ["step_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_task_task_type"),
        "ingestion_task",
        ["task_type"],
        unique=False,
    )

    op.create_table(
        "transactional_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transactional_outbox_aggregate_id"),
        "transactional_outbox",
        ["aggregate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactional_outbox_aggregate_type"),
        "transactional_outbox",
        ["aggregate_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactional_outbox_event_type"),
        "transactional_outbox",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactional_outbox_idempotency_key"),
        "transactional_outbox",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "source_page",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("inclusion_status", sa.String(length=32), nullable=False),
        sa.Column("inclusion_reason", sa.Text(), nullable=True),
        sa.Column("thumbnail_key", sa.String(length=1024), nullable=True),
        sa.Column("text_density", sa.Float(), nullable=True),
        sa.Column("orientation", sa.String(length=32), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("image_coverage", sa.Float(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("quality_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page_number > 0", name="ck_source_page_number_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "page_number", name="uq_source_page_run_number"),
    )
    op.create_index(
        op.f("ix_source_page_inclusion_status"),
        "source_page",
        ["inclusion_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_page_page_number"),
        "source_page",
        ["page_number"],
        unique=False,
    )
    op.create_index(op.f("ix_source_page_role"), "source_page", ["role"], unique=False)
    op.create_index(
        op.f("ix_source_page_run_id"), "source_page", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_page_source_document_id"),
        "source_page",
        ["source_document_id"],
        unique=False,
    )

    op.create_table(
        "ingestion_artifact",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("retention_policy", sa.String(length=128), nullable=False),
        sa.Column(
            "artifact_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_page_id"], ["source_page.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_artifact_artifact_type"),
        "ingestion_artifact",
        ["artifact_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_artifact_run_id"),
        "ingestion_artifact",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_artifact_sha256"),
        "ingestion_artifact",
        ["sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_artifact_source_page_id"),
        "ingestion_artifact",
        ["source_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_artifact_storage_key"),
        "ingestion_artifact",
        ["storage_key"],
        unique=False,
    )

    op.create_table(
        "extraction_candidate",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("materialized_provision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("materialized_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=True),
        sa.Column("heading", sa.String(length=512), nullable=True),
        sa.Column("canonical_path", sa.String(length=512), nullable=False),
        sa.Column("sort_key", sa.String(length=255), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("text_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_page_start", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("source_spans", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ancestor_headings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("parser_version", sa.String(length=128), nullable=True),
        sa.Column("extractor_version", sa.String(length=128), nullable=True),
        sa.Column("parser_confidence", sa.Float(), nullable=True),
        sa.Column("extractor_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocking_issue_count", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["materialized_provision_id"], ["provision.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["materialized_version_id"], ["provision_version.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["parent_candidate_id"], ["extraction_candidate.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "canonical_path",
            "revision_number",
            name="uq_extraction_candidate_revision_path",
        ),
    )
    op.create_index(
        op.f("ix_extraction_candidate_canonical_path"),
        "extraction_candidate",
        ["canonical_path"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_kind"),
        "extraction_candidate",
        ["kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_materialized_provision_id"),
        "extraction_candidate",
        ["materialized_provision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_materialized_version_id"),
        "extraction_candidate",
        ["materialized_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_number"),
        "extraction_candidate",
        ["number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_parent_candidate_id"),
        "extraction_candidate",
        ["parent_candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_run_id"),
        "extraction_candidate",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_sort_key"),
        "extraction_candidate",
        ["sort_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_source_document_id"),
        "extraction_candidate",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_status"),
        "extraction_candidate",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_candidate_text_sha256"),
        "extraction_candidate",
        ["text_sha256"],
        unique=False,
    )

    op.create_table(
        "candidate_revision",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("previous_text", sa.Text(), nullable=True),
        sa.Column("revised_text", sa.Text(), nullable=True),
        sa.Column("diff", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("revised_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["extraction_candidate.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["revised_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id", "revision_number", name="uq_candidate_revision_number"
        ),
    )
    op.create_index(
        op.f("ix_candidate_revision_candidate_id"),
        "candidate_revision",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_revision_revised_by"),
        "candidate_revision",
        ["revised_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_revision_revision_number"),
        "candidate_revision",
        ["revision_number"],
        unique=False,
    )

    op.create_table(
        "review_issue",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["extraction_candidate.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["resolved_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_issue_blocking"),
        "review_issue",
        ["blocking"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_issue_candidate_id"),
        "review_issue",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_issue_issue_type"),
        "review_issue",
        ["issue_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_issue_resolved_by"),
        "review_issue",
        ["resolved_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_issue_severity"),
        "review_issue",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_issue_status"),
        "review_issue",
        ["status"],
        unique=False,
    )

    op.create_table(
        "review_decision",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["extraction_candidate.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_decision_candidate_id"),
        "review_decision",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_decision_decided_by"),
        "review_decision",
        ["decided_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_decision_decision"),
        "review_decision",
        ["decision"],
        unique=False,
    )

    op.create_table(
        "corpus_release_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provision_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"], ["ingestion_run.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["provision_version_id"], ["provision_version.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["release_id"], ["corpus_release.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_document.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "provision_version_id",
            name="uq_corpus_release_entry_version",
        ),
    )
    op.create_index(
        op.f("ix_corpus_release_entry_ingestion_run_id"),
        "corpus_release_entry",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corpus_release_entry_provision_version_id"),
        "corpus_release_entry",
        ["provision_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corpus_release_entry_release_id"),
        "corpus_release_entry",
        ["release_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corpus_release_entry_source_document_id"),
        "corpus_release_entry",
        ["source_document_id"],
        unique=False,
    )

    op.create_table(
        "embedding_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_revision", sa.String(length=128), nullable=True),
        sa.Column("vector_dimensions", sa.Integer(), nullable=False),
        sa.Column("supports_sparse", sa.Boolean(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_embedding_profile_is_active"),
        "embedding_profile",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_profile_model_name"),
        "embedding_profile",
        ["model_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_profile_name"),
        "embedding_profile",
        ["name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_embedding_profile_provider"),
        "embedding_profile",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_profile_supports_sparse"),
        "embedding_profile",
        ["supports_sparse"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_profile_vector_dimensions"),
        "embedding_profile",
        ["vector_dimensions"],
        unique=False,
    )

    op.create_table(
        "embedding_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("benchmark_dataset_version", sa.String(length=128), nullable=True),
        sa.Column("recall_at_10", sa.Float(), nullable=True),
        sa.Column("ndcg_at_10", sa.Float(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("p95_latency_ms", sa.Float(), nullable=True),
        sa.Column("selected_for_release", sa.Boolean(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["embedding_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["corpus_release.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_embedding_run_profile_id"),
        "embedding_run",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_run_release_id"),
        "embedding_run",
        ["release_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_run_selected_for_release"),
        "embedding_run",
        ["selected_for_release"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_run_status"), "embedding_run", ["status"], unique=False
    )

    op.create_table(
        "vector_index",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("alias_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("point_count", sa.Integer(), nullable=False),
        sa.Column("vector_dimensions", sa.Integer(), nullable=False),
        sa.Column("payload_schema_hash", sa.String(length=64), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "validation_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["embedding_run_id"], ["embedding_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["embedding_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["corpus_release.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vector_index_alias_name"),
        "vector_index",
        ["alias_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vector_index_checksum"),
        "vector_index",
        ["checksum"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vector_index_collection_name"),
        "vector_index",
        ["collection_name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_vector_index_embedding_run_id"),
        "vector_index",
        ["embedding_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vector_index_payload_schema_hash"),
        "vector_index",
        ["payload_schema_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vector_index_profile_id"),
        "vector_index",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vector_index_release_id"),
        "vector_index",
        ["release_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vector_index_status"), "vector_index", ["status"], unique=False
    )

    op.create_table(
        "release_promotion_attempt",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector_index_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("previous_release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_collection_name", sa.String(length=255), nullable=True),
        sa.Column("target_collection_name", sa.String(length=255), nullable=True),
        sa.Column("rollback_completed", sa.Boolean(), nullable=False),
        sa.Column(
            "error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["previous_release_id"], ["corpus_release.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["release_id"], ["corpus_release.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vector_index_id"], ["vector_index.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_release_promotion_attempt_previous_release_id"),
        "release_promotion_attempt",
        ["previous_release_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_promotion_attempt_release_id"),
        "release_promotion_attempt",
        ["release_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_promotion_attempt_requested_by"),
        "release_promotion_attempt",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_promotion_attempt_rollback_completed"),
        "release_promotion_attempt",
        ["rollback_completed"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_promotion_attempt_status"),
        "release_promotion_attempt",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_promotion_attempt_vector_index_id"),
        "release_promotion_attempt",
        ["vector_index_id"],
        unique=False,
    )

    op.create_table(
        "admin_role_assignment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_role_assignment_assigned_by"),
        "admin_role_assignment",
        ["assigned_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_role_assignment_role"),
        "admin_role_assignment",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_role_assignment_user_id"),
        "admin_role_assignment",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_role_assignment_active_unique",
        "admin_role_assignment",
        ["user_id", "role"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_event_action"), "audit_event", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_event_actor_user_id"),
        "audit_event",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_event_entity_id"),
        "audit_event",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_event_entity_type"),
        "audit_event",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_event_severity"),
        "audit_event",
        ["severity"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_audit_event_severity"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_entity_type"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_entity_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_actor_user_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_action"), table_name="audit_event")
    op.drop_table("audit_event")

    op.drop_index(
        "ix_admin_role_assignment_active_unique", table_name="admin_role_assignment"
    )
    op.drop_index(
        op.f("ix_admin_role_assignment_user_id"), table_name="admin_role_assignment"
    )
    op.drop_index(
        op.f("ix_admin_role_assignment_role"), table_name="admin_role_assignment"
    )
    op.drop_index(
        op.f("ix_admin_role_assignment_assigned_by"),
        table_name="admin_role_assignment",
    )
    op.drop_table("admin_role_assignment")

    op.drop_index(
        op.f("ix_release_promotion_attempt_vector_index_id"),
        table_name="release_promotion_attempt",
    )
    op.drop_index(
        op.f("ix_release_promotion_attempt_status"),
        table_name="release_promotion_attempt",
    )
    op.drop_index(
        op.f("ix_release_promotion_attempt_rollback_completed"),
        table_name="release_promotion_attempt",
    )
    op.drop_index(
        op.f("ix_release_promotion_attempt_requested_by"),
        table_name="release_promotion_attempt",
    )
    op.drop_index(
        op.f("ix_release_promotion_attempt_release_id"),
        table_name="release_promotion_attempt",
    )
    op.drop_index(
        op.f("ix_release_promotion_attempt_previous_release_id"),
        table_name="release_promotion_attempt",
    )
    op.drop_table("release_promotion_attempt")

    op.drop_index(op.f("ix_vector_index_status"), table_name="vector_index")
    op.drop_index(op.f("ix_vector_index_release_id"), table_name="vector_index")
    op.drop_index(op.f("ix_vector_index_profile_id"), table_name="vector_index")
    op.drop_index(
        op.f("ix_vector_index_payload_schema_hash"), table_name="vector_index"
    )
    op.drop_index(op.f("ix_vector_index_embedding_run_id"), table_name="vector_index")
    op.drop_index(op.f("ix_vector_index_collection_name"), table_name="vector_index")
    op.drop_index(op.f("ix_vector_index_checksum"), table_name="vector_index")
    op.drop_index(op.f("ix_vector_index_alias_name"), table_name="vector_index")
    op.drop_table("vector_index")

    op.drop_index(op.f("ix_embedding_run_status"), table_name="embedding_run")
    op.drop_index(
        op.f("ix_embedding_run_selected_for_release"), table_name="embedding_run"
    )
    op.drop_index(op.f("ix_embedding_run_release_id"), table_name="embedding_run")
    op.drop_index(op.f("ix_embedding_run_profile_id"), table_name="embedding_run")
    op.drop_table("embedding_run")

    op.drop_index(
        op.f("ix_embedding_profile_vector_dimensions"), table_name="embedding_profile"
    )
    op.drop_index(
        op.f("ix_embedding_profile_supports_sparse"), table_name="embedding_profile"
    )
    op.drop_index(op.f("ix_embedding_profile_provider"), table_name="embedding_profile")
    op.drop_index(op.f("ix_embedding_profile_name"), table_name="embedding_profile")
    op.drop_index(
        op.f("ix_embedding_profile_model_name"), table_name="embedding_profile"
    )
    op.drop_index(
        op.f("ix_embedding_profile_is_active"), table_name="embedding_profile"
    )
    op.drop_table("embedding_profile")

    op.drop_index(
        op.f("ix_corpus_release_entry_source_document_id"),
        table_name="corpus_release_entry",
    )
    op.drop_index(
        op.f("ix_corpus_release_entry_release_id"), table_name="corpus_release_entry"
    )
    op.drop_index(
        op.f("ix_corpus_release_entry_provision_version_id"),
        table_name="corpus_release_entry",
    )
    op.drop_index(
        op.f("ix_corpus_release_entry_ingestion_run_id"),
        table_name="corpus_release_entry",
    )
    op.drop_table("corpus_release_entry")

    op.drop_index(op.f("ix_review_decision_decision"), table_name="review_decision")
    op.drop_index(op.f("ix_review_decision_decided_by"), table_name="review_decision")
    op.drop_index(op.f("ix_review_decision_candidate_id"), table_name="review_decision")
    op.drop_table("review_decision")

    op.drop_index(op.f("ix_review_issue_status"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_severity"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_resolved_by"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_issue_type"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_candidate_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_blocking"), table_name="review_issue")
    op.drop_table("review_issue")

    op.drop_index(
        op.f("ix_candidate_revision_revision_number"), table_name="candidate_revision"
    )
    op.drop_index(op.f("ix_candidate_revision_revised_by"), table_name="candidate_revision")
    op.drop_index(
        op.f("ix_candidate_revision_candidate_id"), table_name="candidate_revision"
    )
    op.drop_table("candidate_revision")

    op.drop_index(
        op.f("ix_extraction_candidate_text_sha256"),
        table_name="extraction_candidate",
    )
    op.drop_index(
        op.f("ix_extraction_candidate_status"), table_name="extraction_candidate"
    )
    op.drop_index(
        op.f("ix_extraction_candidate_source_document_id"),
        table_name="extraction_candidate",
    )
    op.drop_index(
        op.f("ix_extraction_candidate_sort_key"), table_name="extraction_candidate"
    )
    op.drop_index(
        op.f("ix_extraction_candidate_run_id"), table_name="extraction_candidate"
    )
    op.drop_index(
        op.f("ix_extraction_candidate_parent_candidate_id"),
        table_name="extraction_candidate",
    )
    op.drop_index(
        op.f("ix_extraction_candidate_number"), table_name="extraction_candidate"
    )
    op.drop_index(
        op.f("ix_extraction_candidate_materialized_version_id"),
        table_name="extraction_candidate",
    )
    op.drop_index(
        op.f("ix_extraction_candidate_materialized_provision_id"),
        table_name="extraction_candidate",
    )
    op.drop_index(
        op.f("ix_extraction_candidate_kind"), table_name="extraction_candidate"
    )
    op.drop_index(
        op.f("ix_extraction_candidate_canonical_path"),
        table_name="extraction_candidate",
    )
    op.drop_table("extraction_candidate")

    op.drop_index(
        op.f("ix_ingestion_artifact_storage_key"), table_name="ingestion_artifact"
    )
    op.drop_index(
        op.f("ix_ingestion_artifact_source_page_id"), table_name="ingestion_artifact"
    )
    op.drop_index(op.f("ix_ingestion_artifact_sha256"), table_name="ingestion_artifact")
    op.drop_index(op.f("ix_ingestion_artifact_run_id"), table_name="ingestion_artifact")
    op.drop_index(
        op.f("ix_ingestion_artifact_artifact_type"),
        table_name="ingestion_artifact",
    )
    op.drop_table("ingestion_artifact")

    op.drop_index(op.f("ix_source_page_source_document_id"), table_name="source_page")
    op.drop_index(op.f("ix_source_page_run_id"), table_name="source_page")
    op.drop_index(op.f("ix_source_page_role"), table_name="source_page")
    op.drop_index(op.f("ix_source_page_page_number"), table_name="source_page")
    op.drop_index(op.f("ix_source_page_inclusion_status"), table_name="source_page")
    op.drop_table("source_page")

    op.drop_index(
        op.f("ix_transactional_outbox_idempotency_key"),
        table_name="transactional_outbox",
    )
    op.drop_index(
        op.f("ix_transactional_outbox_event_type"),
        table_name="transactional_outbox",
    )
    op.drop_index(
        op.f("ix_transactional_outbox_aggregate_type"),
        table_name="transactional_outbox",
    )
    op.drop_index(
        op.f("ix_transactional_outbox_aggregate_id"),
        table_name="transactional_outbox",
    )
    op.drop_table("transactional_outbox")

    op.drop_index(op.f("ix_ingestion_task_task_type"), table_name="ingestion_task")
    op.drop_index(op.f("ix_ingestion_task_step_id"), table_name="ingestion_task")
    op.drop_index(op.f("ix_ingestion_task_status"), table_name="ingestion_task")
    op.drop_index(op.f("ix_ingestion_task_run_id"), table_name="ingestion_task")
    op.drop_index(op.f("ix_ingestion_task_priority"), table_name="ingestion_task")
    op.drop_index(op.f("ix_ingestion_task_lease_owner"), table_name="ingestion_task")
    op.drop_index(
        op.f("ix_ingestion_task_idempotency_key"), table_name="ingestion_task"
    )
    op.drop_table("ingestion_task")

    op.drop_index(op.f("ix_ingestion_event_step_id"), table_name="ingestion_event")
    op.drop_index(op.f("ix_ingestion_event_stage"), table_name="ingestion_event")
    op.drop_index(op.f("ix_ingestion_event_sequence"), table_name="ingestion_event")
    op.drop_index(op.f("ix_ingestion_event_run_id"), table_name="ingestion_event")
    op.drop_index(op.f("ix_ingestion_event_event_type"), table_name="ingestion_event")
    op.drop_table("ingestion_event")

    op.drop_index(op.f("ix_ingestion_step_status"), table_name="ingestion_step")
    op.drop_index(op.f("ix_ingestion_step_stage"), table_name="ingestion_step")
    op.drop_index(op.f("ix_ingestion_step_run_id"), table_name="ingestion_step")
    op.drop_index(op.f("ix_ingestion_step_lease_owner"), table_name="ingestion_step")
    op.drop_index(
        op.f("ix_ingestion_step_dependency_step_id"), table_name="ingestion_step"
    )
    op.drop_table("ingestion_step")

    op.drop_index(op.f("ix_ingestion_run_status"), table_name="ingestion_run")
    op.drop_index(
        op.f("ix_ingestion_run_source_upload_id"), table_name="ingestion_run"
    )
    op.drop_index(
        op.f("ix_ingestion_run_source_document_id"), table_name="ingestion_run"
    )
    op.drop_index(op.f("ix_ingestion_run_current_stage"), table_name="ingestion_run")
    op.drop_index(op.f("ix_ingestion_run_created_by"), table_name="ingestion_run")
    op.drop_table("ingestion_run")

    op.drop_index(op.f("ix_source_upload_upload_backend"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_status"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_source_tier"), table_name="source_upload")
    op.drop_index(
        op.f("ix_source_upload_source_document_id"), table_name="source_upload"
    )
    op.drop_index(
        op.f("ix_source_upload_legal_instrument_id"), table_name="source_upload"
    )
    op.drop_index(op.f("ix_source_upload_instrument_year"), table_name="source_upload")
    op.drop_index(
        op.f("ix_source_upload_instrument_status"), table_name="source_upload"
    )
    op.drop_index(op.f("ix_source_upload_instrument_slug"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_idempotency_key"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_expected_sha256"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_created_by"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_canonical_key"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_authority"), table_name="source_upload")
    op.drop_index(op.f("ix_source_upload_actual_sha256"), table_name="source_upload")
    op.drop_table("source_upload")

    op.drop_index("ix_corpus_release_single_production", table_name="corpus_release")
    op.drop_column("corpus_release", "lock_version")
    op.drop_column("corpus_release", "validation_report")

    op.drop_index(op.f("ix_source_document_storage_backend"), table_name="source_document")
    op.drop_index(op.f("ix_source_document_created_by"), table_name="source_document")
    op.drop_constraint(
        "fk_source_document_created_by_user", "source_document", type_="foreignkey"
    )
    op.drop_column("source_document", "created_by")
    op.drop_column("source_document", "page_count")
    op.drop_column("source_document", "file_size")
    op.drop_column("source_document", "original_filename")
    op.drop_column("source_document", "storage_bucket")
    op.drop_column("source_document", "storage_backend")
