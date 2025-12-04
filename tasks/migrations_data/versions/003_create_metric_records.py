"""Create metric_records table for tracking Metric.ai data

Revision ID: 003
Revises: 002
Create Date: 2025-10-06

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create metric_records staging table."""
    op.create_table(
        "metric_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "metric_id",
            sa.String(255),
            nullable=False,
            comment="Metric.ai record ID (e.g., emp_123)",
        ),
        sa.Column(
            "data_type",
            sa.String(50),
            nullable=False,
            comment="Type: employee, project, client, allocation",
        ),
        sa.Column(
            "pinecone_id",
            sa.String(255),
            nullable=False,
            comment="Pinecone vector ID (metric_{metric_id})",
        ),
        sa.Column(
            "pinecone_namespace",
            sa.String(100),
            nullable=False,
            server_default="metric",
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
            comment="Last sync timestamp",
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last Metric.ai sync",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_id"),
        comment="Staging table to track what has been synced from Metric.ai to Pinecone",
    )

    # Create indexes
    op.create_index("idx_metric_id", "metric_records", ["metric_id"])
    op.create_index("idx_data_type", "metric_records", ["data_type"])
    op.create_index("idx_pinecone_id", "metric_records", ["pinecone_id"])


def downgrade() -> None:
    """Drop metric_records table."""
    op.drop_index("idx_pinecone_id", table_name="metric_records")
    op.drop_index("idx_data_type", table_name="metric_records")
    op.drop_index("idx_metric_id", table_name="metric_records")
    op.drop_table("metric_records")
