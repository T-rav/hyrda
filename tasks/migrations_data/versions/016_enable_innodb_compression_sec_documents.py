"""Enable InnoDB compression on sec_documents_data table

Revision ID: 016
Revises: 015
Create Date: 2025-10-16

Enables ROW_FORMAT=COMPRESSED with KEY_BLOCK_SIZE=8 to reduce storage
and improve write performance for large SEC documents (~300 pages each).
Typical compression ratio: 60-80% size reduction.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable InnoDB compression on sec_documents_data table."""
    # Enable compression with 8KB block size (good balance for text data)
    op.execute(
        """
        ALTER TABLE sec_documents_data
        ROW_FORMAT=COMPRESSED
        KEY_BLOCK_SIZE=8
        """
    )


def downgrade() -> None:
    """Disable InnoDB compression on sec_documents_data table."""
    # Revert to dynamic row format (InnoDB default)
    op.execute(
        """
        ALTER TABLE sec_documents_data
        ROW_FORMAT=DYNAMIC
        """
    )
