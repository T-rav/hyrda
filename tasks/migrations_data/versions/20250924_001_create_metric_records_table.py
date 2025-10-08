"""Create metric_records table

Revision ID: 001
Revises:
Create Date: 2025-09-24 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create metric_records table for tracking Metric.ai data synced to Pinecone."""
    op.create_table(
        "metric_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "metric_id", sa.String(length=255), nullable=False, comment="ID from Metric.ai"
        ),
        sa.Column(
            "data_type",
            sa.String(length=50),
            nullable=False,
            comment="Type: employee, project, client, allocation",
        ),
        sa.Column(
            "pinecone_id",
            sa.String(length=255),
            nullable=False,
            comment="Vector ID in Pinecone",
        ),
        sa.Column(
            "pinecone_namespace",
            sa.String(length=255),
            nullable=True,
            comment="Pinecone namespace",
        ),
        sa.Column(
            "content_snapshot",
            sa.JSON(),
            nullable=True,
            comment="Snapshot of data at sync time",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="When record was first created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="When record was last updated",
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(),
            nullable=True,
            comment="When last synced to Pinecone",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_records")),
    )

    # Create unique index on metric_id and data_type combination
    op.create_index(
        op.f("ix_metric_records_metric_id_data_type"),
        "metric_records",
        ["metric_id", "data_type"],
        unique=True,
    )

    # Create index on pinecone_id for lookups
    op.create_index(
        op.f("ix_metric_records_pinecone_id"),
        "metric_records",
        ["pinecone_id"],
        unique=False,
    )

    # Create index on data_type for filtering
    op.create_index(
        op.f("ix_metric_records_data_type"),
        "metric_records",
        ["data_type"],
        unique=False,
    )

    # Create index on synced_at for finding stale records
    op.create_index(
        op.f("ix_metric_records_synced_at"),
        "metric_records",
        ["synced_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop metric_records table and all indexes."""
    op.drop_index(op.f("ix_metric_records_synced_at"), table_name="metric_records")
    op.drop_index(op.f("ix_metric_records_data_type"), table_name="metric_records")
    op.drop_index(op.f("ix_metric_records_pinecone_id"), table_name="metric_records")
    op.drop_index(
        op.f("ix_metric_records_metric_id_data_type"), table_name="metric_records"
    )
    op.drop_table("metric_records")
