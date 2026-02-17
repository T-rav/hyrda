"""Add group_name column to task_metadata

Revision ID: 007_add_task_group
Revises: 006_rename_to_task_creds
Create Date: 2026-02-16

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_add_task_group"
down_revision = "006_rename_to_task_creds"
branch_labels = None
depends_on = None


def upgrade():
    """Add group_name column to task_metadata table."""
    op.add_column(
        "task_metadata",
        sa.Column("group_name", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_task_metadata_group_name",
        "task_metadata",
        ["group_name"],
    )


def downgrade():
    """Remove group_name column from task_metadata table."""
    op.drop_index("ix_task_metadata_group_name", table_name="task_metadata")
    op.drop_column("task_metadata", "group_name")
