"""Add permission groups tables.

Revision ID: 008
Revises: 007
Create Date: 2025-11-17

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    """Add permission_groups, user_groups, and agent_group_permissions tables."""
    # Create permission_groups table
    op.create_table(
        "permission_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_name", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
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
        sa.UniqueConstraint("group_name"),
    )
    op.create_index(
        "ix_permission_groups_group_name", "permission_groups", ["group_name"]
    )

    # Create user_groups table (many-to-many: users <-> groups)
    op.create_table(
        "user_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slack_user_id", sa.String(length=255), nullable=False),
        sa.Column("group_name", sa.String(length=50), nullable=False),
        sa.Column("added_by", sa.String(length=255), nullable=True),
        sa.Column(
            "added_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
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
        sa.ForeignKeyConstraint(
            ["group_name"],
            ["permission_groups.group_name"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_groups_slack_user_id", "user_groups", ["slack_user_id"])
    op.create_index("ix_user_groups_group_name", "user_groups", ["group_name"])

    # Create agent_group_permissions table
    op.create_table(
        "agent_group_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("group_name", sa.String(length=50), nullable=False),
        sa.Column(
            "permission_type",
            sa.String(length=10),
            nullable=False,
            server_default="allow",
        ),
        sa.Column("granted_by", sa.String(length=255), nullable=True),
        sa.Column(
            "granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
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
        sa.ForeignKeyConstraint(
            ["group_name"],
            ["permission_groups.group_name"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_group_permissions_agent_name",
        "agent_group_permissions",
        ["agent_name"],
    )
    op.create_index(
        "ix_agent_group_permissions_group_name",
        "agent_group_permissions",
        ["group_name"],
    )


def downgrade():
    """Remove permission groups tables."""
    op.drop_index(
        "ix_agent_group_permissions_group_name", table_name="agent_group_permissions"
    )
    op.drop_index(
        "ix_agent_group_permissions_agent_name", table_name="agent_group_permissions"
    )
    op.drop_table("agent_group_permissions")

    op.drop_index("ix_user_groups_group_name", table_name="user_groups")
    op.drop_index("ix_user_groups_slack_user_id", table_name="user_groups")
    op.drop_table("user_groups")

    op.drop_index("ix_permission_groups_group_name", table_name="permission_groups")
    op.drop_table("permission_groups")
