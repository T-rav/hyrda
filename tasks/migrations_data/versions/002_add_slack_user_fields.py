"""Add missing fields to slack_users table

Revision ID: 002
Revises: 001
Create Date: 2025-10-06

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add name, title, department, is_admin, is_bot fields to slack_users."""
    # Add missing columns
    op.add_column("slack_users", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("slack_users", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("slack_users", sa.Column("department", sa.String(255), nullable=True))
    op.add_column(
        "slack_users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "slack_users",
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column("slack_users", sa.Column("email", sa.String(255), nullable=True))

    # Add indexes for frequently queried fields
    op.create_index("ix_slack_users_email", "slack_users", ["email"])
    op.create_index("ix_slack_users_name", "slack_users", ["name"])


def downgrade() -> None:
    """Remove added fields."""
    op.drop_index("ix_slack_users_name", table_name="slack_users")
    op.drop_index("ix_slack_users_email", table_name="slack_users")

    op.drop_column("slack_users", "email")
    op.drop_column("slack_users", "is_bot")
    op.drop_column("slack_users", "is_admin")
    op.drop_column("slack_users", "department")
    op.drop_column("slack_users", "title")
    op.drop_column("slack_users", "name")
