"""Add content column to sec_documents_data table

Revision ID: 014
Revises: 013
Create Date: 2025-01-16

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    """Add content column to store raw SEC filing text."""
    op.add_column(
        "sec_documents_data",
        sa.Column("content", mysql.LONGTEXT(), nullable=True),
    )


def downgrade():
    """Remove content column from sec_documents_data table."""
    op.drop_column("sec_documents_data", "content")
