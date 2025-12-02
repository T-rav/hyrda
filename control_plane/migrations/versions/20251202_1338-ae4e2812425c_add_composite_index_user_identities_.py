"""add_composite_index_user_identities_provider_active

Revision ID: ae4e2812425c
Revises: 890aaa22b407
Create Date: 2025-12-02 13:38:42.450831

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'ae4e2812425c'
down_revision = '890aaa22b407'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add composite index on (provider_type, is_active) for efficient user sync queries."""
    # Create composite index for active identity queries
    # Used by user_sync.py:219-225 to find all active identities for a provider
    op.create_index(
        "ix_user_identities_provider_active",
        "user_identities",
        ["provider_type", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite index on (provider_type, is_active)."""
    op.drop_index("ix_user_identities_provider_active", table_name="user_identities")
