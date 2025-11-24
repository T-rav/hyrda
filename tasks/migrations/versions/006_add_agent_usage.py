"""create agent_usage table for persistent metrics

Revision ID: 006_add_agent_usage
Revises: 005_add_oauth_credentials
Create Date: 2025-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_agent_usage'
down_revision: Union[str, None] = '005_add_oauth_credentials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_usage table for persistent metrics."""
    op.create_table(
        'agent_usage',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('total_invocations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_invocations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_invocations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_invocation', sa.DateTime(), nullable=True),
        sa.Column('last_invocation', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_name'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4'
    )

    # Create index for faster lookups
    op.create_index('ix_agent_usage_agent_name', 'agent_usage', ['agent_name'])
    op.create_index('ix_agent_usage_is_active', 'agent_usage', ['is_active'])


def downgrade() -> None:
    """Drop agent_usage table."""
    op.drop_index('ix_agent_usage_is_active', table_name='agent_usage')
    op.drop_index('ix_agent_usage_agent_name', table_name='agent_usage')
    op.drop_table('agent_usage')
