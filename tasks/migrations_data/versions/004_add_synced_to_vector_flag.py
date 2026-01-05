"""Add synced_to_vector flag to metric_records

Revision ID: 004
Revises: 003
Create Date: 2025-10-07

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    """Add synced_to_vector column to metric_records."""
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


def downgrade():
    """Remove synced_to_vector column."""
    op.drop_column("metric_records", "synced_to_vector")
