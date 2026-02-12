"""Add hubspot_deals_data table for tracking synced HubSpot deals

Revision ID: 020_add_hubspot_deal_tracking
Revises: 019_add_scraped_web_pages
Create Date: 2026-02-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    """Add hubspot_deals_data table for tracking synced deals with content hashes."""
    op.create_table(
        "hubspot_deals_data",
        # Primary key
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        # HubSpot deal identifier
        sa.Column("hubspot_deal_id", sa.String(50), nullable=False, unique=True),
        # Deal info
        sa.Column("deal_name", sa.String(500), nullable=True),
        # Content tracking
        sa.Column("deal_data_hash", sa.String(64), nullable=False),
        # Vector database tracking
        sa.Column("vector_uuid", sa.String(36), nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="1"),
        # HubSpot metadata
        sa.Column("hubspot_updated_at", sa.DateTime, nullable=True),
        # Ingestion metadata
        sa.Column(
            "first_ingested_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_ingested_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "ingestion_status", sa.String(20), nullable=False, server_default="success"
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        # Additional metadata
        sa.Column("metadata", sa.JSON, nullable=True),
        # Indexes for performance
        sa.Index("idx_hubspot_deal_id", "hubspot_deal_id"),
    )


def downgrade():
    """Remove hubspot_deals_data table."""
    op.drop_table("hubspot_deals_data")
