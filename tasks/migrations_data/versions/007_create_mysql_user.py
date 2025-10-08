"""Create MySQL user for data database access

Revision ID: 007
Revises: 006
Create Date: 2025-10-07

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    """Create insightmesh_data MySQL user and grant privileges."""
    # Create user if not exists
    op.execute(
        """
        CREATE USER IF NOT EXISTS 'insightmesh_data'@'%'
        IDENTIFIED BY 'insightmesh_data_password'
        """
    )

    # Grant all privileges on insightmesh_data database
    op.execute(
        """
        GRANT ALL PRIVILEGES ON insightmesh_data.*
        TO 'insightmesh_data'@'%'
        """
    )

    # Flush privileges to apply changes
    op.execute("FLUSH PRIVILEGES")


def downgrade():
    """Drop insightmesh_data MySQL user."""
    # Revoke privileges first
    op.execute(
        """
        REVOKE ALL PRIVILEGES ON insightmesh_data.*
        FROM 'insightmesh_data'@'%'
        """
    )

    # Drop user
    op.execute("DROP USER IF EXISTS 'insightmesh_data'@'%'")

    # Flush privileges
    op.execute("FLUSH PRIVILEGES")
