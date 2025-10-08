"""Rename metric_id to employee_id in portal_records table

Revision ID: 009
Revises: 008
Create Date: 2025-10-08

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    """Rename metric_id column to employee_id in portal_records."""
    # Drop the old index
    op.drop_index("idx_portal_metric_id", table_name="portal_records")

    # Rename the column
    op.alter_column(
        "portal_records",
        "metric_id",
        new_column_name="employee_id",
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # Update the column comment
    with op.batch_alter_table("portal_records") as batch_op:
        batch_op.alter_column(
            "employee_id",
            comment="Employee ID from Portal",
        )

    # Create new index with updated name
    op.create_index("idx_portal_employee_id", "portal_records", ["employee_id"])


def downgrade():
    """Revert employee_id back to metric_id."""
    # Drop the new index
    op.drop_index("idx_portal_employee_id", table_name="portal_records")

    # Rename the column back
    op.alter_column(
        "portal_records",
        "employee_id",
        new_column_name="metric_id",
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # Restore old column comment
    with op.batch_alter_table("portal_records") as batch_op:
        batch_op.alter_column(
            "metric_id",
            comment="Employee Metric.ai ID",
        )

    # Recreate old index
    op.create_index("idx_portal_metric_id", "portal_records", ["metric_id"])
