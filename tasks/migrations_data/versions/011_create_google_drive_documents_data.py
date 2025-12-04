"""Create google_drive_documents_data table for ingestion tracking

Revision ID: 011
Revises: 010
Create Date: 2025-10-08

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create google_drive_documents_data table for tracking ingested documents."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "google_drive_documents_data" not in inspector.get_table_names():
        op.create_table(
            "google_drive_documents_data",
            # Primary key
            sa.Column(
                "id",
                sa.Integer(),
                nullable=False,
                autoincrement=True,
                comment="Primary key",
            ),
            # Google Drive identifiers
            sa.Column(
                "google_drive_id",
                sa.String(255),
                nullable=False,
                comment="Google Drive file ID",
            ),
            sa.Column(
                "file_path",
                sa.String(1024),
                nullable=False,
                comment="Full path in Google Drive (e.g., 'Folder/Subfolder/Document.pdf')",
            ),
            sa.Column(
                "document_name",
                sa.String(512),
                nullable=False,
                comment="Document name/title from Google Drive",
            ),
            # Content tracking
            sa.Column(
                "content_hash",
                sa.String(64),
                nullable=False,
                comment="SHA-256 hash of document content for change detection",
            ),
            sa.Column(
                "mime_type",
                sa.String(255),
                nullable=True,
                comment="Google Drive MIME type",
            ),
            sa.Column(
                "file_size",
                sa.BigInteger(),
                nullable=True,
                comment="File size in bytes",
            ),
            # Vector database tracking
            sa.Column(
                "vector_uuid",
                sa.String(36),
                nullable=False,
                comment="Base UUID used for Qdrant point IDs (chunks get uuid_0, uuid_1, etc.)",
            ),
            sa.Column(
                "vector_namespace",
                sa.String(100),
                nullable=False,
                server_default="google_drive",
                comment="Vector database namespace",
            ),
            sa.Column(
                "chunk_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="Number of chunks created from this document",
            ),
            # Ingestion metadata
            sa.Column(
                "first_ingested_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                comment="First ingestion timestamp",
            ),
            sa.Column(
                "last_ingested_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                comment="Last ingestion timestamp (updates on re-index)",
            ),
            sa.Column(
                "ingestion_status",
                sa.String(50),
                nullable=False,
                server_default="success",
                comment="Ingestion status: success, failed, pending",
            ),
            sa.Column(
                "error_message",
                sa.Text(),
                nullable=True,
                comment="Error message if ingestion failed",
            ),
            # Additional metadata
            sa.Column(
                "metadata",
                sa.JSON(),
                nullable=True,
                comment="Additional metadata (permissions, owners, etc.)",
            ),
            # Constraints
            sa.PrimaryKeyConstraint("id"),
        )

        # Create indexes for efficient lookups
        op.create_index(
            "idx_google_drive_id",
            "google_drive_documents_data",
            ["google_drive_id"],
            unique=True,
        )
        op.create_index(
            "idx_content_hash", "google_drive_documents_data", ["content_hash"]
        )
        op.create_index(
            "idx_vector_uuid", "google_drive_documents_data", ["vector_uuid"]
        )
        # Use prefix index for file_path to avoid "key too long" error in MySQL
        # MySQL with utf8mb4 has a max key length of 3072 bytes
        # String(1024) * 4 bytes per char = 4096 bytes > 3072 bytes
        # Use prefix of 255 chars: 255 * 4 = 1020 bytes < 3072 bytes
        op.execute(
            "CREATE INDEX idx_file_path ON google_drive_documents_data (file_path(255))"
        )
        op.create_index(
            "idx_ingestion_status",
            "google_drive_documents_data",
            ["ingestion_status"],
        )

        print("✅ Created google_drive_documents_data table with indexes")


def downgrade() -> None:
    """Drop google_drive_documents_data table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "google_drive_documents_data" in inspector.get_table_names():
        op.drop_table("google_drive_documents_data")
        print("✅ Dropped google_drive_documents_data table")
