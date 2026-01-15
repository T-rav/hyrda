"""Add aliases_customized column to agent_metadata

Revision ID: 20260115_1500
Revises: 20260115_1300
Create Date: 2026-01-15 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "20260115_1500"
down_revision = "refactor_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add aliases_customized column to track admin edits."""
    op.add_column(
        "agent_metadata",
        sa.Column("aliases_customized", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Remove aliases_customized column."""
    op.drop_column("agent_metadata", "aliases_customized")
