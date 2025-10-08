"""Restore synced_at and remove synced_to_vector from metric_records

Revision ID: 007
Revises: 006
Create Date: 2025-10-07

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    """Restore synced_at column and remove synced_to_vector."""
    # Remove synced_to_vector flag
    op.drop_column("metric_records", "synced_to_vector")

    # Add synced_at back
    op.add_column(
        "metric_records",
        sa.Column(
            "synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last Pinecone sync timestamp",
        ),
    )


def downgrade():
    """Remove synced_at and restore synced_to_vector."""
    # Remove synced_at
    op.drop_column("metric_records", "synced_at")

    # Add synced_to_vector back
    op.add_column(
        "metric_records",
        sa.Column(
            "synced_to_vector",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Whether data has been synced to Pinecone",
        ),
    )
