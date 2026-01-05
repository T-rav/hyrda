"""Add missing triggered_by_user and environment_info columns

Revision ID: 003_add_missing_task_run_columns
Revises: 002_remove_scheduled_tasks
Create Date: 2025-09-24 04:30:00.000000

"""

import contextlib

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003_add_missing_task_run_columns"
down_revision = "002_remove_scheduled_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the missing triggered_by_user column to task_runs table safely
    # MySQL doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
    # So we use a try/except approach via SQLAlchemy

    with contextlib.suppress(Exception):
        op.add_column(
            "task_runs",
            sa.Column("triggered_by_user", sa.String(length=255), nullable=True),
        )

    with contextlib.suppress(Exception):
        op.add_column(
            "task_runs", sa.Column("environment_info", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    # Remove the columns if rolling back
    op.drop_column("task_runs", "triggered_by_user")
    op.drop_column("task_runs", "environment_info")
