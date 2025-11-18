"""Add multi-provider support with user_identities table

Revision ID: 0003
Revises: 0002
Create Date: 2025-11-17 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user_identities table and primary_provider field to users."""
    # Add primary_provider column to users table
    op.add_column(
        "users",
        sa.Column(
            "primary_provider",
            sa.String(50),
            nullable=False,
            server_default="slack",
        ),
    )
    op.create_index("ix_users_primary_provider", "users", ["primary_provider"])

    # Create user_identities table
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("given_name", sa.String(255), nullable=True),
        sa.Column("family_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_identities_user_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for user_identities
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.create_index("ix_user_identities_provider_type", "user_identities", ["provider_type"])
    op.create_index("ix_user_identities_provider_user_id", "user_identities", ["provider_user_id"])
    op.create_index("ix_user_identities_provider_email", "user_identities", ["provider_email"])

    # Create unique constraint on provider_type + provider_user_id
    op.create_index(
        "uq_user_identities_provider_user",
        "user_identities",
        ["provider_type", "provider_user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove multi-provider support."""
    # Drop user_identities table
    op.drop_index("uq_user_identities_provider_user", table_name="user_identities")
    op.drop_index("ix_user_identities_provider_email", table_name="user_identities")
    op.drop_index("ix_user_identities_provider_user_id", table_name="user_identities")
    op.drop_index("ix_user_identities_provider_type", table_name="user_identities")
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")

    # Remove primary_provider column from users
    op.drop_index("ix_users_primary_provider", table_name="users")
    op.drop_column("users", "primary_provider")
