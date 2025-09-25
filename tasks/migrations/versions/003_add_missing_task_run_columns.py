"""Add missing triggered_by_user and environment_info columns

Revision ID: 003_add_missing_task_run_columns
Revises: 002_remove_scheduled_tasks
Create Date: 2025-09-24 04:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003_add_missing_task_run_columns"
down_revision = "002_remove_scheduled_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the missing triggered_by_user column to task_runs table if it doesn't exist
    # Using IF NOT EXISTS equivalent for MySQL
    op.execute("""
        ALTER TABLE task_runs
        ADD COLUMN IF NOT EXISTS triggered_by_user VARCHAR(255) NULL
        COMMENT 'Slack user ID if manually triggered'
    """)

    # Add the missing environment_info column to task_runs table if it doesn't exist
    op.execute("""
        ALTER TABLE task_runs
        ADD COLUMN IF NOT EXISTS environment_info JSON NULL
        COMMENT 'System info, versions, etc.'
    """)


def downgrade() -> None:
    # Remove the columns if rolling back
    op.drop_column("task_runs", "triggered_by_user")
    op.drop_column("task_runs", "environment_info")
