"""Add users table synced from Google Workspace.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-17 15:30:00.000000

This table stores user data from Google Workspace in the security database.
Users are linked to the slack_users table in the data database via slack_user_id.
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
        sa.Column("slack_user_id", sa.String(length=255), nullable=False),
        sa.Column("google_id", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("given_name", sa.String(length=255), nullable=True),
        sa.Column("family_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("slack_user_id", name=op.f("uq_users_slack_user_id")),
        sa.UniqueConstraint("google_id", name=op.f("uq_users_google_id")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_slack_user_id"), "users", ["slack_user_id"], unique=True)
    op.create_index(op.f("ix_google_id"), "users", ["google_id"], unique=True)
    op.create_index(op.f("ix_email"), "users", ["email"], unique=True)


def downgrade():
    """Remove users table."""
    op.drop_index(op.f("ix_email"), table_name="users")
    op.drop_index(op.f("ix_google_id"), table_name="users")
    op.drop_index(op.f("ix_slack_user_id"), table_name="users")
    op.drop_table("users")
