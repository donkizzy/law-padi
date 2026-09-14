"""Tighten source document storage and revision metadata

Revision ID: a6f4c2d9e8b1
Revises: 4d2f3a7c9b81
Create Date: 2026-09-11 19:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a6f4c2d9e8b1"
down_revision = "4d2f3a7c9b81"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "source_document",
        sa.Column(
            "is_legal_revision",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "source_document",
        sa.Column("legal_revision_effective_at", sa.Date(), nullable=True),
    )
    op.create_index(
        op.f("ix_source_document_is_legal_revision"),
        "source_document",
        ["is_legal_revision"],
        unique=False,
    )

    op.execute(
        """
        UPDATE source_document
        SET source_url = 'unknown://source-document/' || id::text
        WHERE source_url IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET mime_type = 'application/pdf'
        WHERE mime_type IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET sha256 = left(replace(id::text, '-', '') || repeat('0', 64), 64)
        WHERE sha256 IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET storage_backend = 'local'
        WHERE storage_backend IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET storage_key = 'sources/legacy/' || id::text || '/original.pdf'
        WHERE storage_key IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET original_filename = 'source.pdf'
        WHERE original_filename IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET file_size = 0
        WHERE file_size IS NULL
        """
    )
    op.alter_column(
        "source_document",
        "source_url",
        existing_type=sa.String(length=2048),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "mime_type",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "sha256",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "storage_backend",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "storage_key",
        existing_type=sa.String(length=1024),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "original_filename",
        existing_type=sa.String(length=512),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "file_size",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "is_legal_revision",
        server_default=None,
    )
    op.create_check_constraint(
        "ck_source_document_legal_revision_effective_at",
        "source_document",
        "(is_legal_revision = false) OR (legal_revision_effective_at IS NOT NULL)",
    )

    op.add_column(
        "source_upload",
        sa.Column(
            "is_legal_revision",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.alter_column("source_upload", "is_legal_revision", server_default=None)
    op.add_column(
        "source_upload",
        sa.Column("legal_revision_effective_at", sa.Date(), nullable=True),
    )
    op.create_index(
        op.f("ix_source_upload_is_legal_revision"),
        "source_upload",
        ["is_legal_revision"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_source_upload_legal_revision_effective_at",
        "source_upload",
        "(is_legal_revision = false) OR (legal_revision_effective_at IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint(
        "ck_source_upload_legal_revision_effective_at",
        "source_upload",
        type_="check",
    )
    op.drop_index(op.f("ix_source_upload_is_legal_revision"), table_name="source_upload")
    op.drop_column("source_upload", "legal_revision_effective_at")
    op.drop_column("source_upload", "is_legal_revision")

    op.drop_constraint(
        "ck_source_document_legal_revision_effective_at",
        "source_document",
        type_="check",
    )
    op.alter_column(
        "source_document",
        "file_size",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "original_filename",
        existing_type=sa.String(length=512),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "storage_key",
        existing_type=sa.String(length=1024),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "storage_backend",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "sha256",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "mime_type",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "source_url",
        existing_type=sa.String(length=2048),
        nullable=True,
    )
    op.drop_index(
        op.f("ix_source_document_is_legal_revision"), table_name="source_document"
    )
    op.drop_column("source_document", "legal_revision_effective_at")
    op.drop_column("source_document", "is_legal_revision")

