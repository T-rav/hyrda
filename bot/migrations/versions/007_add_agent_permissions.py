"""Add agent permissions tables.

Revision ID: 003
Revises: 002
Create Date: 2025-11-17

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    """Add agent_metadata and agent_permissions tables."""
    # Create agent_metadata table
    op.create_table(
        "agent_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("requires_admin", sa.Boolean(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("agent_name"),
    )
    op.create_index("ix_agent_metadata_agent_name", "agent_metadata", ["agent_name"])

    # Create agent_permissions table
    op.create_table(
        "agent_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("slack_user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "permission_type",
            sa.Enum("allow", "deny", name="permission_type_enum"),
            nullable=False,
            server_default="allow",
        ),
        sa.Column("granted_by", sa.String(length=255), nullable=True),
        sa.Column(
            "granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
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
    )
    op.create_index(
        "ix_agent_permissions_agent_name", "agent_permissions", ["agent_name"]
    )
    op.create_index(
        "ix_agent_permissions_slack_user_id", "agent_permissions", ["slack_user_id"]
    )


def downgrade():
    """Remove agent permissions tables."""
    op.drop_index("ix_agent_permissions_slack_user_id", table_name="agent_permissions")
    op.drop_index("ix_agent_permissions_agent_name", table_name="agent_permissions")
    op.drop_table("agent_permissions")

    op.drop_index("ix_agent_metadata_agent_name", table_name="agent_metadata")
    op.drop_table("agent_metadata")
