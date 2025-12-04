"""Rename pinecone columns to vector in metric_records and portal_records

Revision ID: 010
Revises: 009
Create Date: 2025-10-08

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename pinecone_* columns to vector_* in metric_records and portal_records."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Rename columns in metric_records table
    if "metric_records" in inspector.get_table_names():
        # Drop old indexes
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("metric_records")
        ]
        if "idx_pinecone_id" in existing_indexes:
            op.drop_index("idx_pinecone_id", table_name="metric_records")

        # Rename columns
        op.alter_column(
            "metric_records",
            "pinecone_id",
            new_column_name="vector_id",
            existing_type=sa.String(255),
            existing_nullable=False,
            comment="Vector database ID (metric_{metric_id})",
        )
        op.alter_column(
            "metric_records",
            "pinecone_namespace",
            new_column_name="vector_namespace",
            existing_type=sa.String(100),
            existing_nullable=False,
            existing_server_default="metric",
            comment="Vector database namespace",
        )

        # Create new index
        op.create_index("idx_vector_id", "metric_records", ["vector_id"])

    # Rename columns in portal_records table
    if "portal_records" in inspector.get_table_names():
        # Drop old indexes
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("portal_records")
        ]
        if "idx_portal_pinecone_id" in existing_indexes:
            op.drop_index("idx_portal_pinecone_id", table_name="portal_records")

        # Rename columns
        op.alter_column(
            "portal_records",
            "pinecone_id",
            new_column_name="vector_id",
            existing_type=sa.String(255),
            existing_nullable=False,
            comment="Vector database ID (portal_employee_{metric_id})",
        )
        op.alter_column(
            "portal_records",
            "pinecone_namespace",
            new_column_name="vector_namespace",
            existing_type=sa.String(100),
            existing_nullable=False,
            existing_server_default="portal",
            comment="Vector database namespace",
        )

        # Create new index
        op.create_index("idx_portal_vector_id", "portal_records", ["vector_id"])


def downgrade() -> None:
    """Rename vector_* columns back to pinecone_* in metric_records and portal_records."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Rename columns in metric_records table
    if "metric_records" in inspector.get_table_names():
        # Drop new indexes
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("metric_records")
        ]
        if "idx_vector_id" in existing_indexes:
            op.drop_index("idx_vector_id", table_name="metric_records")

        # Rename columns back
        op.alter_column(
            "metric_records",
            "vector_id",
            new_column_name="pinecone_id",
            existing_type=sa.String(255),
            existing_nullable=False,
            comment="Pinecone vector ID (metric_{metric_id})",
        )
        op.alter_column(
            "metric_records",
            "vector_namespace",
            new_column_name="pinecone_namespace",
            existing_type=sa.String(100),
            existing_nullable=False,
            existing_server_default="metric",
            comment="Pinecone namespace",
        )

        # Create old index
        op.create_index("idx_pinecone_id", "metric_records", ["pinecone_id"])

    # Rename columns in portal_records table
    if "portal_records" in inspector.get_table_names():
        # Drop new indexes
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("portal_records")
        ]
        if "idx_portal_vector_id" in existing_indexes:
            op.drop_index("idx_portal_vector_id", table_name="portal_records")

        # Rename columns back
        op.alter_column(
            "portal_records",
            "vector_id",
            new_column_name="pinecone_id",
            existing_type=sa.String(255),
            existing_nullable=False,
            comment="Pinecone vector ID (portal_employee_{metric_id})",
        )
        op.alter_column(
            "portal_records",
            "vector_namespace",
            new_column_name="pinecone_namespace",
            existing_type=sa.String(100),
            existing_nullable=False,
            existing_server_default="portal",
            comment="Pinecone namespace",
        )

        # Create old index
        op.create_index("idx_portal_pinecone_id", "portal_records", ["pinecone_id"])
