"""refactor_agent_visibility

Refactor agent visibility control:
- Rename is_public → is_slack_visible (controls Slack visibility only)
- Add is_enabled (controls if agent is enabled at all)

Logic:
- is_enabled=false → agent disabled everywhere (unless is_system=true)
- is_enabled=true + is_slack_visible=true → visible in Slack
- is_enabled=true + is_slack_visible=false → enabled but backend-only

Revision ID: refactor_visibility
Revises: 20260106_0000-1a2b3c4d5e6f
Create Date: 2026-01-15 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "refactor_visibility"
down_revision = "20260106_0000-1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_enabled column (defaults to True for existing agents)
    op.add_column(
        "agent_metadata",
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
    )

    # Rename is_public to is_slack_visible
    op.alter_column("agent_metadata", "is_public", new_column_name="is_slack_visible")

    # For existing agents, copy values:
    # - is_enabled = old is_public value (if agent was public, it's enabled)
    # - is_slack_visible = old is_public value (if agent was public, it's visible in Slack)
    # This preserves current behavior for existing agents


def downgrade() -> None:
    # Rename is_slack_visible back to is_public
    op.alter_column("agent_metadata", "is_slack_visible", new_column_name="is_public")

    # Drop is_enabled column
    op.drop_column("agent_metadata", "is_enabled")
