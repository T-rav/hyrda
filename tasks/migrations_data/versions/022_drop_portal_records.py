"""Drop portal_records table - no longer used

Revision ID: 022
Revises: 021
Create Date: 2025-02-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade():
    """Drop portal_records table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "portal_records" in inspector.get_table_names():
        # Drop indexes first
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("portal_records")
        ]
        for idx_name in existing_indexes:
            op.drop_index(idx_name, table_name="portal_records")

        # Drop the table
        op.drop_table("portal_records")


def downgrade():
    """Recreate portal_records table."""
    op.create_table(
        "portal_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "employee_id",
            sa.String(255),
            nullable=False,
            comment="Employee ID from Portal",
        ),
        sa.Column(
            "data_type",
            sa.String(50),
            nullable=False,
            comment="Type: employee_profile",
        ),
        sa.Column(
            "vector_id",
            sa.String(255),
            nullable=False,
            comment="Vector database ID (portal_employee_{employee_id})",
        ),
        sa.Column(
            "vector_namespace",
            sa.String(100),
            nullable=False,
            server_default="portal",
            comment="Vector database namespace",
        ),
        sa.Column(
            "content_snapshot",
            sa.Text(),
            nullable=False,
            comment="Text content synced to vector database",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="First sync timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            comment="Last update timestamp",
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last Portal sync",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id"),
        comment="Table to track what has been synced from Portal to vector database",
    )

    # Recreate indexes
    op.create_index("idx_portal_employee_id", "portal_records", ["employee_id"])
    op.create_index("idx_portal_data_type", "portal_records", ["data_type"])
    op.create_index("idx_portal_vector_id", "portal_records", ["vector_id"])
