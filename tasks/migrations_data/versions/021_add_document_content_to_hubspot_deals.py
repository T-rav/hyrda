"""Add document_content column to hubspot_deals_data

Revision ID: 021
Revises: 020
Create Date: 2026-02-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    """Add document_content column to store full text for retrieval."""
    op.add_column(
        "hubspot_deals_data",
        sa.Column("document_content", sa.Text, nullable=True),
    )


def downgrade():
    """Remove document_content column."""
    op.drop_column("hubspot_deals_data", "document_content")
