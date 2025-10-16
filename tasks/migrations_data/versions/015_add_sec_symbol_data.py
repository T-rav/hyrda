"""Add sec_symbol_data table and ticker_symbol to sec_documents_data

Revision ID: 015
Revises: 014
Create Date: 2025-01-16

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    """Create sec_symbol_data reference table and add ticker_symbol to sec_documents_data."""

    # 1. Create sec_symbol_data reference table (all public companies)
    op.create_table(
        "sec_symbol_data",
        # Primary key
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Company identifiers
        sa.Column("ticker_symbol", sa.String(length=10), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=512), nullable=False),
        # Metadata
        sa.Column("exchange", sa.String(length=10), nullable=True),  # NYSE, NASDAQ, etc.
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_symbol", name="uq_ticker_symbol"),
        sa.UniqueConstraint("cik", name="uq_cik"),
    )

    # Create indexes for lookups
    op.create_index("idx_ticker_symbol", "sec_symbol_data", ["ticker_symbol"])
    op.create_index("idx_symbol_cik", "sec_symbol_data", ["cik"])
    op.create_index("idx_company_name_symbol", "sec_symbol_data", ["company_name"])

    # 2. Add ticker_symbol to sec_documents_data (for cross-referencing)
    op.add_column(
        "sec_documents_data",
        sa.Column("ticker_symbol", sa.String(length=10), nullable=True)
    )

    # Create index on ticker_symbol for joins
    op.create_index("idx_ticker_symbol_docs", "sec_documents_data", ["ticker_symbol"])


def downgrade():
    """Remove sec_symbol_data table and ticker_symbol column."""

    # Drop ticker_symbol from sec_documents_data
    op.drop_index("idx_ticker_symbol_docs", table_name="sec_documents_data")
    op.drop_column("sec_documents_data", "ticker_symbol")

    # Drop sec_symbol_data table
    op.drop_index("idx_company_name_symbol", table_name="sec_symbol_data")
    op.drop_index("idx_symbol_cik", table_name="sec_symbol_data")
    op.drop_index("idx_ticker_symbol", table_name="sec_symbol_data")
    op.drop_table("sec_symbol_data")
