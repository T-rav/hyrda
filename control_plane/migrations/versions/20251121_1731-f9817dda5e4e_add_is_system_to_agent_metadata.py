"""add_is_system_to_agent_metadata

Revision ID: f9817dda5e4e
Revises: 0003
Create Date: 2025-11-21 17:31:10.644217

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9817dda5e4e'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_system column to agent_metadata table
    op.add_column(
        'agent_metadata',
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='0')
    )

    # Mark 'help' agent as system agent and ensure it's enabled
    op.execute("""
        UPDATE agent_metadata
        SET is_system = 1, is_public = 1
        WHERE agent_name = 'help'
    """)


def downgrade() -> None:
    # Remove is_system column from agent_metadata table
    op.drop_column('agent_metadata', 'is_system')
