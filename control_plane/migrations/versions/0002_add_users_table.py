"""Add users table for Google Workspace sync.

Revision ID: 0002
Revises: 0001
Create Date: 2025-11-17

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    """Add users table synced from Google Workspace."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Slack identity
        sa.Column("slack_user_id", sa.String(length=255), nullable=False),
        # Google Workspace identity (source of truth)
        sa.Column("google_id", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        # User profile
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("given_name", sa.String(length=100), nullable=True),
        sa.Column("family_name", sa.String(length=100), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        # Sync tracking
        sa.Column(
            "last_synced_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slack_user_id"),
        sa.UniqueConstraint("google_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_slack_user_id", "users", ["slack_user_id"])
    op.create_index("ix_users_google_id", "users", ["google_id"])
    op.create_index("ix_users_email", "users", ["email"])


def downgrade():
    """Remove users table."""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_index("ix_users_slack_user_id", table_name="users")
    op.drop_table("users")
