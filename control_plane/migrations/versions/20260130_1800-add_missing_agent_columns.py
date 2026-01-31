"""add_missing_agent_columns

Add missing columns to agent_metadata table:
- langgraph_assistant_id
- langgraph_url
- endpoint_url
- is_slack_visible (rename from is_public)
- is_deleted

Revision ID: add_missing_agent_columns
Revises: 20260115_1500-add_aliases_customized
Create Date: 2026-01-30 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_missing_agent_columns"
down_revision = "20260115_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("agent_metadata")]

    # Add langgraph_assistant_id column
    if "langgraph_assistant_id" not in columns:
        op.add_column(
            "agent_metadata",
            sa.Column("langgraph_assistant_id", sa.String(255), nullable=True),
        )

    # Add langgraph_url column
    if "langgraph_url" not in columns:
        op.add_column(
            "agent_metadata",
            sa.Column("langgraph_url", sa.String(512), nullable=True),
        )

    # Add endpoint_url column
    if "endpoint_url" not in columns:
        op.add_column(
            "agent_metadata",
            sa.Column("endpoint_url", sa.String(512), nullable=True),
        )

    # Add is_deleted column
    if "is_deleted" not in columns:
        op.add_column(
            "agent_metadata",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        )

    # Rename is_public to is_slack_visible if needed
    if "is_public" in columns and "is_slack_visible" not in columns:
        op.alter_column(
            "agent_metadata",
            "is_public",
            new_column_name="is_slack_visible",
            existing_type=sa.Boolean(),
            existing_server_default="1",
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("agent_metadata")]

    # Rename is_slack_visible back to is_public
    if "is_slack_visible" in columns and "is_public" not in columns:
        op.alter_column(
            "agent_metadata", "is_slack_visible", new_column_name="is_public"
        )

    # Drop columns
    for col_name in [
        "is_deleted",
        "endpoint_url",
        "langgraph_url",
        "langgraph_assistant_id",
    ]:
        if col_name in columns:
            op.drop_column("agent_metadata", col_name)
