"""Remove non-Slack fields from slack_users table

Revision ID: 006
Revises: 005
Create Date: 2025-10-07

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    """Remove name, title, department, email fields from slack_users."""
    # Drop indexes first
    op.drop_index("ix_slack_users_name", table_name="slack_users")
    op.drop_index("ix_slack_users_email", table_name="slack_users")

    # Drop columns
    op.drop_column("slack_users", "name")
    op.drop_column("slack_users", "title")
    op.drop_column("slack_users", "department")
    op.drop_column("slack_users", "email")


def downgrade():
    """Restore name, title, department, email fields."""
    import sqlalchemy as sa

    # Add columns back
    op.add_column("slack_users", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("slack_users", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("slack_users", sa.Column("department", sa.String(255), nullable=True))
    op.add_column("slack_users", sa.Column("email", sa.String(255), nullable=True))

    # Restore indexes
    op.create_index("ix_slack_users_email", "slack_users", ["email"])
    op.create_index("ix_slack_users_name", "slack_users", ["name"])
