"""Remove synced_at column from metric_records

Revision ID: 005
Revises: 004
Create Date: 2025-10-07

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    """Remove synced_at column."""
    op.drop_column("metric_records", "synced_at")


def downgrade():
    """Restore synced_at column."""
    import sqlalchemy as sa

    op.add_column(
        "metric_records",
        sa.Column(
            "synced_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
