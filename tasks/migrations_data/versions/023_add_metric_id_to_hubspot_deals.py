"""Add metric_id column to hubspot_deals_data for direct Metric linking

Revision ID: 023
Revises: 022
Create Date: 2025-02-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade():
    """Add metric_id column to hubspot_deals_data table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "hubspot_deals_data" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("hubspot_deals_data")]

        if "metric_id" not in columns:
            op.add_column(
                "hubspot_deals_data",
                sa.Column(
                    "metric_id",
                    sa.String(50),
                    nullable=True,
                    comment="Metric.ai Project ID for direct linking",
                ),
            )
            # Add index for fast lookups by metric_id
            op.create_index(
                "idx_hubspot_metric_id",
                "hubspot_deals_data",
                ["metric_id"],
            )


def downgrade():
    """Remove metric_id column from hubspot_deals_data table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "hubspot_deals_data" in inspector.get_table_names():
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("hubspot_deals_data")
        ]
        if "idx_hubspot_metric_id" in existing_indexes:
            op.drop_index("idx_hubspot_metric_id", table_name="hubspot_deals_data")

        columns = [col["name"] for col in inspector.get_columns("hubspot_deals_data")]
        if "metric_id" in columns:
            op.drop_column("hubspot_deals_data", "metric_id")
