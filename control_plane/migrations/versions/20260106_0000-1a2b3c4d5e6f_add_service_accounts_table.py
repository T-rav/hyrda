"""Add service_accounts table for external API integrations.

Revision ID: 1a2b3c4d5e6f
Revises: ae4e2812425c
Create Date: 2026-01-06 00:00:00.000000

This table enables external systems (HubSpot, Salesforce, custom apps) to
authenticate via API keys separate from internal service-to-service tokens.

Features:
- API key authentication with bcrypt hashing
- Scope-based permissions (agents:read, agents:invoke, etc.)
- Per-agent access control (allow specific agents only)
- Rate limiting (requests per hour)
- Expiration support
- Revocation with audit trail
- Usage tracking (last used, total requests, IP tracking)
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = "ae4e2812425c"
branch_labels = None
depends_on = None


def upgrade():
    """Add service_accounts table for external API integrations."""
    op.create_table(
        "service_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Identification
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Authentication
        sa.Column("api_key_hash", sa.String(length=255), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=10), nullable=False),
        # Permissions
        sa.Column(
            "scopes",
            sa.String(length=1000),
            nullable=False,
            server_default="agents:read,agents:invoke",
        ),
        sa.Column("allowed_agents", sa.Text(), nullable=True),  # JSON array
        sa.Column("rate_limit", sa.Integer(), nullable=False, server_default="100"),
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="0"),
        # Metadata
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # Audit
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        # Usage tracking
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_request_ip", sa.String(length=45), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_accounts")),
        sa.UniqueConstraint("name", name=op.f("uq_service_accounts_name")),
        sa.UniqueConstraint(
            "api_key_hash", name=op.f("uq_service_accounts_api_key_hash")
        ),
    )

    # Indexes for fast lookups
    op.create_index(
        op.f("ix_service_accounts_name"), "service_accounts", ["name"], unique=True
    )
    op.create_index(
        op.f("ix_service_accounts_api_key_hash"),
        "service_accounts",
        ["api_key_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_service_accounts_api_key_prefix"),
        "service_accounts",
        ["api_key_prefix"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_accounts_is_active"),
        "service_accounts",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_accounts_is_revoked"),
        "service_accounts",
        ["is_revoked"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_accounts_expires_at"),
        "service_accounts",
        ["expires_at"],
        unique=False,
    )


def downgrade():
    """Remove service_accounts table."""
    op.drop_index(op.f("ix_service_accounts_expires_at"), table_name="service_accounts")
    op.drop_index(op.f("ix_service_accounts_is_revoked"), table_name="service_accounts")
    op.drop_index(op.f("ix_service_accounts_is_active"), table_name="service_accounts")
    op.drop_index(
        op.f("ix_service_accounts_api_key_prefix"), table_name="service_accounts"
    )
    op.drop_index(
        op.f("ix_service_accounts_api_key_hash"), table_name="service_accounts"
    )
    op.drop_index(op.f("ix_service_accounts_name"), table_name="service_accounts")
    op.drop_table("service_accounts")
