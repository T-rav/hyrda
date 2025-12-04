"""Remove scheduled_tasks table

Revision ID: 002_remove_scheduled_tasks
Revises: 001
Create Date: 2025-09-24 03:20:49.765197

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002_remove_scheduled_tasks"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade."""
    # Drop the scheduled_tasks table if it exists
    op.execute("DROP TABLE IF EXISTS scheduled_tasks")


def downgrade() -> None:
    """Downgrade."""
    # Recreate the scheduled_tasks table if needed to rollback
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=255), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_config", sa.JSON(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_tasks")),
        sa.UniqueConstraint("job_id", name=op.f("uq_scheduled_tasks_job_id")),
    )
    op.create_index(
        op.f("ix_scheduled_tasks_job_type"),
        "scheduled_tasks",
        ["job_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_tasks_is_active"),
        "scheduled_tasks",
        ["is_active"],
        unique=False,
    )
