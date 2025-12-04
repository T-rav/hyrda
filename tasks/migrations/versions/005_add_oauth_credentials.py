"""Add oauth_credentials table for encrypted token storage

Revision ID: 005_add_oauth_credentials
Revises: 004_add_task_metadata
Create Date: 2025-11-13

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "005_add_oauth_credentials"
down_revision = "004_add_task_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add oauth_credentials table for secure, encrypted storage of OAuth tokens."""
    op.create_table(
        "oauth_credentials",
        sa.Column("credential_id", sa.String(191), nullable=False),
        sa.Column("credential_name", sa.String(255), nullable=False),
        sa.Column(
            "provider", sa.String(50), nullable=False, server_default="google_drive"
        ),
        sa.Column("encrypted_token", sa.Text, nullable=False),
        sa.Column("token_metadata", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("credential_id"),
        sa.Index("idx_oauth_provider", "provider"),
    )


def downgrade() -> None:
    """Remove oauth_credentials table."""
    op.drop_table("oauth_credentials")
