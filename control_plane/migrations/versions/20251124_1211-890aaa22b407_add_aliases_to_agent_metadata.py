"""add_aliases_to_agent_metadata

Revision ID: 890aaa22b407
Revises: f9817dda5e4e
Create Date: 2025-11-24 12:11:12.076757

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '890aaa22b407'
down_revision = 'f9817dda5e4e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add aliases column to agent_metadata table
    op.add_column('agent_metadata', sa.Column('aliases', sa.Text(), nullable=True))

    # Seed with existing agents
    op.execute("""
        INSERT INTO agent_metadata (agent_name, display_name, description, aliases, is_public, requires_admin, is_system)
        VALUES
            ('profile', 'Company Profile', 'Generate comprehensive company profiles through deep research', '[""-profile""]', TRUE, FALSE, FALSE),
            ('meddic', 'MEDDIC Coach', 'MEDDPICC sales qualification and coaching', '["medic", "meddpicc"]', TRUE, FALSE, FALSE),
            ('help', 'Help Agent', 'List available bot agents and their aliases', '["agents"]', TRUE, FALSE, TRUE)
        ON DUPLICATE KEY UPDATE
            display_name = VALUES(display_name),
            description = VALUES(description),
            aliases = VALUES(aliases),
            is_system = VALUES(is_system)
    """)


def downgrade() -> None:
    # Remove aliases column
    op.drop_column('agent_metadata', 'aliases')
