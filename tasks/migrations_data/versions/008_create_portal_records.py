"""Create portal_records table for tracking Portal employee data

Revision ID: 008
Revises: 007
Create Date: 2025-10-08

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create portal_records table."""
    op.create_table(
        "portal_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "metric_id",
            sa.String(255),
            nullable=False,
            comment="Employee Metric.ai ID",
        ),
        sa.Column(
            "data_type",
            sa.String(50),
            nullable=False,
            comment="Type: employee_profile",
        ),
        sa.Column(
            "pinecone_id",
            sa.String(255),
            nullable=False,
            comment="Pinecone vector ID (portal_employee_{metric_id})",
        ),
        sa.Column(
            "pinecone_namespace",
            sa.String(100),
            nullable=False,
            server_default="portal",
            comment="Pinecone namespace",
        ),
        sa.Column(
            "content_snapshot",
            sa.Text(),
            nullable=False,
            comment="Text content synced to Pinecone",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="First sync timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            comment="Last update timestamp",
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last Portal sync",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_id"),
        comment="Table to track what has been synced from Portal to Pinecone",
    )

    # Create indexes
    op.create_index("idx_portal_metric_id", "portal_records", ["metric_id"])
    op.create_index("idx_portal_data_type", "portal_records", ["data_type"])
    op.create_index("idx_portal_pinecone_id", "portal_records", ["pinecone_id"])


def downgrade() -> None:
    """Drop portal_records table."""
    op.drop_index("idx_portal_pinecone_id", table_name="portal_records")
    op.drop_index("idx_portal_data_type", table_name="portal_records")
    op.drop_index("idx_portal_metric_id", table_name="portal_records")
    op.drop_table("portal_records")
