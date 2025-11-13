"""Add oauth_credentials table for encrypted token storage

Revision ID: 005
Revises: 004
Create Date: 2025-11-13

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    """Add oauth_credentials table for secure, encrypted storage of OAuth tokens."""
    op.create_table(
        "oauth_credentials",
        sa.Column("credential_id", sa.String(191), nullable=False),
        sa.Column("credential_name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="google_drive"),
        sa.Column("encrypted_token", sa.Text, nullable=False),
        sa.Column("token_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("credential_id"),
        sa.Index("idx_oauth_provider", "provider"),
    )


def downgrade():
    """Remove oauth_credentials table."""
    op.drop_table("oauth_credentials")
