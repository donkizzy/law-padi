"""Add legal domain schema

Revision ID: 7f4d9c2a1b6e
Revises: fe56fa70289e
Create Date: 2026-08-30 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7f4d9c2a1b6e"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.drop_table("item")

    op.create_table(
        "legal_instrument",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("short_title", sa.String(length=255), nullable=True),
        sa.Column("instrument_type", sa.String(length=32), nullable=False),
        sa.Column("jurisdiction", sa.String(length=255), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("enacted_at", sa.Date(), nullable=True),
        sa.Column("effective_at", sa.Date(), nullable=True),
        sa.Column("ceased_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legal_instrument_instrument_type"),
        "legal_instrument",
        ["instrument_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_instrument_jurisdiction"),
        "legal_instrument",
        ["jurisdiction"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_instrument_slug"),
        "legal_instrument",
        ["slug"],
        unique=True,
    )
    op.create_index(
        op.f("ix_legal_instrument_status"),
        "legal_instrument",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_instrument_year"),
        "legal_instrument",
        ["year"],
        unique=False,
    )

    op.create_table(
        "corpus_release",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_model_version", sa.String(length=128), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_corpus_release_approved_by"),
        "corpus_release",
        ["approved_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corpus_release_source_manifest_hash"),
        "corpus_release",
        ["source_manifest_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corpus_release_status"),
        "corpus_release",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corpus_release_version"),
        "corpus_release",
        ["version"],
        unique=True,
    )

    op.create_table(
        "legal_concept",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legal_concept_slug"),
        "legal_concept",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "conversation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("anonymous_session_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("preferred_language", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "user_id IS NOT NULL OR anonymous_session_id IS NOT NULL",
            name="ck_conversation_has_owner_or_anonymous_session",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_anonymous_session_id"),
        "conversation",
        ["anonymous_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_preferred_language"),
        "conversation",
        ["preferred_language"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_user_id"),
        "conversation",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "source_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authority", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_tier", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("extraction_method", sa.String(length=32), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["legal_instrument_id"],
            ["legal_instrument.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["verified_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_document_authority"),
        "source_document",
        ["authority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_document_legal_instrument_id"),
        "source_document",
        ["legal_instrument_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_document_sha256"),
        "source_document",
        ["sha256"],
        unique=True,
    )
    op.create_index(
        op.f("ix_source_document_source_tier"),
        "source_document",
        ["source_tier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_document_verification_status"),
        "source_document",
        ["verification_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_document_verified_by"),
        "source_document",
        ["verified_by"],
        unique=False,
    )

    op.create_table(
        "provision",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=True),
        sa.Column("heading", sa.String(length=512), nullable=True),
        sa.Column("canonical_path", sa.String(length=512), nullable=False),
        sa.Column("sort_key", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["legal_instrument.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["provision.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_provision_canonical_path"),
        "provision",
        ["canonical_path"],
        unique=True,
    )
    op.create_index(
        op.f("ix_provision_instrument_id"),
        "provision",
        ["instrument_id"],
        unique=False,
    )
    op.create_index(op.f("ix_provision_kind"), "provision", ["kind"], unique=False)
    op.create_index(op.f("ix_provision_number"), "provision", ["number"], unique=False)
    op.create_index(
        op.f("ix_provision_parent_id"),
        "provision",
        ["parent_id"],
        unique=False,
    )
    op.create_index(op.f("ix_provision_sort_key"), "provision", ["sort_key"], unique=False)

    op.create_table(
        "amendment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("act_number", sa.String(length=128), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("passed_at", sa.Date(), nullable=True),
        sa.Column("effective_at", sa.Date(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["legal_instrument.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_document.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_amendment_act_number"),
        "amendment",
        ["act_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_instrument_id"),
        "amendment",
        ["instrument_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_source_document_id"),
        "amendment",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(op.f("ix_amendment_status"), "amendment", ["status"], unique=False)
    op.create_index(op.f("ix_amendment_year"), "amendment", ["year"], unique=False)

    op.create_table(
        "constitutional_bill",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_number", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("introduced_at", sa.Date(), nullable=True),
        sa.Column("originating_chamber", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=128), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["legal_instrument.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_constitutional_bill_bill_number"),
        "constitutional_bill",
        ["bill_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_constitutional_bill_current_stage"),
        "constitutional_bill",
        ["current_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_constitutional_bill_instrument_id"),
        "constitutional_bill",
        ["instrument_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_constitutional_bill_originating_chamber"),
        "constitutional_bill",
        ["originating_chamber"],
        unique=False,
    )
    op.create_index(
        op.f("ix_constitutional_bill_status"),
        "constitutional_bill",
        ["status"],
        unique=False,
    )

    op.create_table(
        "legal_concept_alias",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("phrase", sa.String(length=512), nullable=False),
        sa.Column("normalized_phrase", sa.String(length=512), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["legal_concept.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legal_concept_alias_concept_id"),
        "legal_concept_alias",
        ["concept_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_concept_alias_language"),
        "legal_concept_alias",
        ["language"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_concept_alias_normalized_phrase"),
        "legal_concept_alias",
        ["normalized_phrase"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_concept_alias_reviewed"),
        "legal_concept_alias",
        ["reviewed"],
        unique=False,
    )

    op.create_table(
        "conversation_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=16), nullable=True),
        sa.Column("answer_status", sa.String(length=32), nullable=True),
        sa.Column("model_provider", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("retrieval_trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_message_answer_status"),
        "conversation_message",
        ["answer_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_message_conversation_id"),
        "conversation_message",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_message_detected_language"),
        "conversation_message",
        ["detected_language"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_message_retrieval_trace_id"),
        "conversation_message",
        ["retrieval_trace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_message_role"),
        "conversation_message",
        ["role"],
        unique=False,
    )

    op.create_table(
        "legislative_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("chamber", sa.String(length=32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["constitutional_bill.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_document.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legislative_event_bill_id"),
        "legislative_event",
        ["bill_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legislative_event_chamber"),
        "legislative_event",
        ["chamber"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legislative_event_event_date"),
        "legislative_event",
        ["event_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legislative_event_event_type"),
        "legislative_event",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legislative_event_source_document_id"),
        "legislative_event",
        ["source_document_id"],
        unique=False,
    )

    op.create_table(
        "provision_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("legal_status", sa.String(length=32), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_page_start", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_by_amendment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_provision_version_valid_period",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_amendment_id"],
            ["amendment.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["provision_id"],
            ["provision.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_document.id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["provision_version.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provision_id",
            "revision_number",
            name="uq_provision_version_revision",
        ),
    )
    op.create_index(
        op.f("ix_provision_version_created_by_amendment_id"),
        "provision_version",
        ["created_by_amendment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_legal_status"),
        "provision_version",
        ["legal_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_provision_id"),
        "provision_version",
        ["provision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_source_document_id"),
        "provision_version",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_supersedes_id"),
        "provision_version",
        ["supersedes_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_text_sha256"),
        "provision_version",
        ["text_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_valid_from"),
        "provision_version",
        ["valid_from"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provision_version_valid_until"),
        "provision_version",
        ["valid_until"],
        unique=False,
    )
    op.execute(
        """
        ALTER TABLE provision_version
        ADD CONSTRAINT provision_version_no_overlap
        EXCLUDE USING gist (
            provision_id WITH =,
            daterange(valid_from, COALESCE(valid_until, 'infinity'::date), '[)') WITH &&
        )
        """
    )

    op.create_table(
        "amendment_operation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amendment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_provision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("selector", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("old_text", sa.Text(), nullable=True),
        sa.Column("new_text", sa.Text(), nullable=True),
        sa.Column("old_text_hash", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["amendment_id"],
            ["amendment.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["target_provision_id"],
            ["provision.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_version_id"],
            ["provision_version.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_amendment_operation_amendment_id"),
        "amendment_operation",
        ["amendment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_old_text_hash"),
        "amendment_operation",
        ["old_text_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_operation_type"),
        "amendment_operation",
        ["operation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_review_status"),
        "amendment_operation",
        ["review_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_reviewed_by"),
        "amendment_operation",
        ["reviewed_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_sort_order"),
        "amendment_operation",
        ["sort_order"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_target_provision_id"),
        "amendment_operation",
        ["target_provision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amendment_operation_target_version_id"),
        "amendment_operation",
        ["target_version_id"],
        unique=False,
    )

    op.create_table(
        "message_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provision_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_role", sa.String(length=32), nullable=False),
        sa.Column("retrieval_rank", sa.Integer(), nullable=True),
        sa.Column("retrieval_score", sa.Float(), nullable=True),
        sa.Column("citation_label", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["conversation_message.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provision_version_id"],
            ["provision_version.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_message_evidence_evidence_role"),
        "message_evidence",
        ["evidence_role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_evidence_message_id"),
        "message_evidence",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_evidence_provision_version_id"),
        "message_evidence",
        ["provision_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_evidence_retrieval_rank"),
        "message_evidence",
        ["retrieval_rank"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_message_evidence_retrieval_rank"), table_name="message_evidence")
    op.drop_index(op.f("ix_message_evidence_provision_version_id"), table_name="message_evidence")
    op.drop_index(op.f("ix_message_evidence_message_id"), table_name="message_evidence")
    op.drop_index(op.f("ix_message_evidence_evidence_role"), table_name="message_evidence")
    op.drop_table("message_evidence")

    op.drop_index(op.f("ix_amendment_operation_target_version_id"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_target_provision_id"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_sort_order"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_reviewed_by"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_review_status"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_operation_type"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_old_text_hash"), table_name="amendment_operation")
    op.drop_index(op.f("ix_amendment_operation_amendment_id"), table_name="amendment_operation")
    op.drop_table("amendment_operation")

    op.execute("ALTER TABLE provision_version DROP CONSTRAINT provision_version_no_overlap")
    op.drop_index(op.f("ix_provision_version_valid_until"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_valid_from"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_text_sha256"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_supersedes_id"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_source_document_id"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_provision_id"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_legal_status"), table_name="provision_version")
    op.drop_index(op.f("ix_provision_version_created_by_amendment_id"), table_name="provision_version")
    op.drop_table("provision_version")

    op.drop_index(op.f("ix_legislative_event_source_document_id"), table_name="legislative_event")
    op.drop_index(op.f("ix_legislative_event_event_type"), table_name="legislative_event")
    op.drop_index(op.f("ix_legislative_event_event_date"), table_name="legislative_event")
    op.drop_index(op.f("ix_legislative_event_chamber"), table_name="legislative_event")
    op.drop_index(op.f("ix_legislative_event_bill_id"), table_name="legislative_event")
    op.drop_table("legislative_event")

    op.drop_index(op.f("ix_conversation_message_role"), table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_retrieval_trace_id"), table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_detected_language"), table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_conversation_id"), table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_answer_status"), table_name="conversation_message")
    op.drop_table("conversation_message")

    op.drop_index(op.f("ix_legal_concept_alias_reviewed"), table_name="legal_concept_alias")
    op.drop_index(op.f("ix_legal_concept_alias_normalized_phrase"), table_name="legal_concept_alias")
    op.drop_index(op.f("ix_legal_concept_alias_language"), table_name="legal_concept_alias")
    op.drop_index(op.f("ix_legal_concept_alias_concept_id"), table_name="legal_concept_alias")
    op.drop_table("legal_concept_alias")

    op.drop_index(op.f("ix_constitutional_bill_status"), table_name="constitutional_bill")
    op.drop_index(op.f("ix_constitutional_bill_originating_chamber"), table_name="constitutional_bill")
    op.drop_index(op.f("ix_constitutional_bill_instrument_id"), table_name="constitutional_bill")
    op.drop_index(op.f("ix_constitutional_bill_current_stage"), table_name="constitutional_bill")
    op.drop_index(op.f("ix_constitutional_bill_bill_number"), table_name="constitutional_bill")
    op.drop_table("constitutional_bill")

    op.drop_index(op.f("ix_amendment_year"), table_name="amendment")
    op.drop_index(op.f("ix_amendment_status"), table_name="amendment")
    op.drop_index(op.f("ix_amendment_source_document_id"), table_name="amendment")
    op.drop_index(op.f("ix_amendment_instrument_id"), table_name="amendment")
    op.drop_index(op.f("ix_amendment_act_number"), table_name="amendment")
    op.drop_table("amendment")

    op.drop_index(op.f("ix_provision_sort_key"), table_name="provision")
    op.drop_index(op.f("ix_provision_parent_id"), table_name="provision")
    op.drop_index(op.f("ix_provision_number"), table_name="provision")
    op.drop_index(op.f("ix_provision_kind"), table_name="provision")
    op.drop_index(op.f("ix_provision_instrument_id"), table_name="provision")
    op.drop_index(op.f("ix_provision_canonical_path"), table_name="provision")
    op.drop_table("provision")

    op.drop_index(op.f("ix_source_document_verified_by"), table_name="source_document")
    op.drop_index(op.f("ix_source_document_verification_status"), table_name="source_document")
    op.drop_index(op.f("ix_source_document_source_tier"), table_name="source_document")
    op.drop_index(op.f("ix_source_document_sha256"), table_name="source_document")
    op.drop_index(op.f("ix_source_document_legal_instrument_id"), table_name="source_document")
    op.drop_index(op.f("ix_source_document_authority"), table_name="source_document")
    op.drop_table("source_document")

    op.drop_index(op.f("ix_conversation_user_id"), table_name="conversation")
    op.drop_index(op.f("ix_conversation_preferred_language"), table_name="conversation")
    op.drop_index(op.f("ix_conversation_anonymous_session_id"), table_name="conversation")
    op.drop_table("conversation")

    op.drop_index(op.f("ix_legal_concept_slug"), table_name="legal_concept")
    op.drop_table("legal_concept")

    op.drop_index(op.f("ix_corpus_release_version"), table_name="corpus_release")
    op.drop_index(op.f("ix_corpus_release_status"), table_name="corpus_release")
    op.drop_index(op.f("ix_corpus_release_source_manifest_hash"), table_name="corpus_release")
    op.drop_index(op.f("ix_corpus_release_approved_by"), table_name="corpus_release")
    op.drop_table("corpus_release")

    op.drop_index(op.f("ix_legal_instrument_year"), table_name="legal_instrument")
    op.drop_index(op.f("ix_legal_instrument_status"), table_name="legal_instrument")
    op.drop_index(op.f("ix_legal_instrument_slug"), table_name="legal_instrument")
    op.drop_index(op.f("ix_legal_instrument_jurisdiction"), table_name="legal_instrument")
    op.drop_index(op.f("ix_legal_instrument_instrument_type"), table_name="legal_instrument")
    op.drop_table("legal_instrument")

    op.create_table(
        "item",
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user.id"],
            name="item_owner_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
