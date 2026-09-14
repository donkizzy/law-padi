"""Require source document dates

Revision ID: c8e5d1f0a4b2
Revises: b1c7d4e9f2a3
Create Date: 2026-09-12 00:35:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8e5d1f0a4b2"
down_revision = "b1c7d4e9f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE source_document
        SET published_at = created_at::date
        WHERE published_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE source_document
        SET retrieved_at = created_at
        WHERE retrieved_at IS NULL
        """
    )
    op.alter_column(
        "source_document",
        "published_at",
        existing_type=sa.Date(),
        nullable=False,
    )
    op.alter_column(
        "source_document",
        "retrieved_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "source_document",
        "retrieved_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "source_document",
        "published_at",
        existing_type=sa.Date(),
        nullable=True,
    )
