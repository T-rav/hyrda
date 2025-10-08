"""Add content_hash to metric_records for change detection.

Revision ID: 012
Revises: 011
Create Date: 2025-10-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    """Add content_hash column to metric_records table."""
    # Add content_hash column (MD5 hash of content_snapshot)
    op.add_column(
        "metric_records",
        sa.Column("content_hash", sa.String(32), nullable=True),
    )

    # Add index for efficient lookups
    op.create_index(
        "idx_metric_content_hash",
        "metric_records",
        ["metric_id", "data_type", "content_hash"],
    )


def downgrade():
    """Remove content_hash column from metric_records table."""
    op.drop_index("idx_metric_content_hash", table_name="metric_records")
    op.drop_column("metric_records", "content_hash")
