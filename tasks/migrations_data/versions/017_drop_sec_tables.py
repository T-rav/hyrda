"""Drop SEC database tables (moved to on-demand only)

Revision ID: 017
Revises: 016
Create Date: 2025-01-17

SEC ingestion is now on-demand only (no scheduled jobs, no persistence).
Dropping sec_documents_data and sec_symbol_data tables.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    """Drop SEC database tables - now using on-demand fetching only."""
    from sqlalchemy import inspect

    # Get database connection
    conn = op.get_bind()
    inspector = inspect(conn)

    # Check if sec_documents_data table exists
    if "sec_documents_data" in inspector.get_table_names():
        # Drop indexes if they exist
        indexes = [idx["name"] for idx in inspector.get_indexes("sec_documents_data")]
        if "idx_company_name" in indexes:
            op.drop_index("idx_company_name", table_name="sec_documents_data")
        if "idx_cik" in indexes:
            op.drop_index("idx_cik", table_name="sec_documents_data")

        # Drop table
        op.drop_table("sec_documents_data")
        print("✅ Dropped sec_documents_data table")
    else:
        print("⏭️  sec_documents_data table does not exist, skipping")

    # Check if sec_symbol_data table exists
    if "sec_symbol_data" in inspector.get_table_names():
        # Drop indexes if they exist
        indexes = [idx["name"] for idx in inspector.get_indexes("sec_symbol_data")]
        if "idx_ticker_lookup" in indexes:
            op.drop_index("idx_ticker_lookup", table_name="sec_symbol_data")
        if "idx_cik_lookup" in indexes:
            op.drop_index("idx_cik_lookup", table_name="sec_symbol_data")

        # Drop table
        op.drop_table("sec_symbol_data")
        print("✅ Dropped sec_symbol_data table")
    else:
        print("⏭️  sec_symbol_data table does not exist, skipping")


def downgrade():
    """Recreate SEC tables if needed (not recommended)."""
    import sqlalchemy as sa
    from sqlalchemy.dialects import mysql

    # Recreate sec_documents_data
    op.create_table(
        "sec_documents_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("accession_number", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("filing_type", sa.String(length=10), nullable=False),
        sa.Column("document_name", sa.String(length=512), nullable=False),
        sa.Column("filing_date", sa.String(length=10), nullable=False),
        sa.Column("document_url", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_length", sa.BigInteger(), nullable=True),
        sa.Column("vector_uuid", sa.String(length=36), nullable=False),
        sa.Column(
            "vector_namespace",
            sa.String(length=100),
            nullable=False,
            server_default="sec_filings",
        ),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.Column("metadata", mysql.JSON(), nullable=True),
        sa.Column(
            "content",
            sa.Text(),
            nullable=True,
            comment="Full filing content (compressed)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number", name="uq_accession_number"),
    )
    op.create_index("idx_cik", "sec_documents_data", ["cik"])
    op.create_index("idx_company_name", "sec_documents_data", ["company_name"])

    # Recreate sec_symbol_data
    op.create_table(
        "sec_symbol_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_symbol", sa.String(length=10), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=50), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_symbol", name="uq_ticker_symbol"),
        sa.UniqueConstraint("cik", name="uq_cik"),
    )
    op.create_index("idx_ticker_lookup", "sec_symbol_data", ["ticker_symbol"])
    op.create_index("idx_cik_lookup", "sec_symbol_data", ["cik"])
