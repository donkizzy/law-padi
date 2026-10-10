"""Pin a user-selected provision identity to a generation run."""

import sqlalchemy as sa
from alembic import op

revision = "9e0f1a2b3c4d"
down_revision = "8d9e0f1a2b3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_run",
        sa.Column("selected_provision_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_generation_run_selected_version",
        "generation_run",
        "provision_version",
        ["selected_provision_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_generation_run_selected_provision_version_id",
        "generation_run",
        ["selected_provision_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_run_selected_provision_version_id", table_name="generation_run"
    )
    op.drop_constraint(
        "fk_generation_run_selected_version", "generation_run", type_="foreignkey"
    )
    op.drop_column("generation_run", "selected_provision_version_id")
