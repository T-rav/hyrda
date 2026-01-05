"""add task metadata table

Revision ID: 004_add_task_metadata
Revises: 003_add_missing_task_run_columns
Create Date: 2025-11-12 22:45:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004_add_task_metadata"
down_revision = "003_add_missing_task_run_columns"
branch_labels = None
depends_on = None


def upgrade():
    """Add task_metadata table for storing custom task names."""
    op.create_table(
        "task_metadata",
        sa.Column("job_id", sa.String(191), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime, server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade():
    """Remove task_metadata table."""
    op.drop_table("task_metadata")
