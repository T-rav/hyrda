"""Create sec_documents_data table

Revision ID: 013
Revises: 012
Create Date: 2025-01-16

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sec_documents_data table for tracking SEC filing ingestion."""
    op.create_table(
        "sec_documents_data",
        # Primary key
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # SEC identifiers
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("accession_number", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("filing_type", sa.String(length=10), nullable=False),
        # Document identification
        sa.Column("document_name", sa.String(length=512), nullable=False),
        sa.Column("filing_date", sa.String(length=10), nullable=False),
        sa.Column("document_url", sa.String(length=1024), nullable=False),
        # Content tracking
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_length", sa.BigInteger(), nullable=True),
        # Vector database tracking
        sa.Column("vector_uuid", sa.String(length=36), nullable=False),
        sa.Column(
            "vector_namespace",
            sa.String(length=100),
            nullable=False,
            server_default="sec_filings",
        ),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        # Ingestion metadata
        sa.Column(
            "first_ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "ingestion_status",
            sa.String(length=50),
            nullable=False,
            server_default="success",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Additional metadata (JSON)
        sa.Column("metadata", mysql.JSON(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number", name="uq_accession_number"),
    )

    # Create indexes for common queries
    op.create_index("idx_cik", "sec_documents_data", ["cik"])
    op.create_index("idx_company_name", "sec_documents_data", ["company_name"])


def downgrade() -> None:
    """Drop sec_documents_data table."""
    op.drop_index("idx_company_name", table_name="sec_documents_data")
    op.drop_index("idx_cik", table_name="sec_documents_data")
    op.drop_table("sec_documents_data")
