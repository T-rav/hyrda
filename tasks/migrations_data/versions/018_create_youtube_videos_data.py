"""Create youtube_videos_data table for YouTube ingestion tracking

Revision ID: 018
Revises: 017
Create Date: 2026-01-21

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    """Create youtube_videos_data table for tracking ingested YouTube videos."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "youtube_videos_data" not in inspector.get_table_names():
        op.create_table(
            "youtube_videos_data",
            # Primary key
            sa.Column(
                "id",
                sa.Integer(),
                nullable=False,
                autoincrement=True,
                comment="Primary key",
            ),
            # YouTube identifiers
            sa.Column(
                "youtube_video_id",
                sa.String(255),
                nullable=False,
                comment="YouTube video ID (unique identifier from YouTube)",
            ),
            sa.Column(
                "video_title",
                sa.String(512),
                nullable=False,
                comment="Video title from YouTube",
            ),
            sa.Column(
                "channel_id",
                sa.String(255),
                nullable=False,
                comment="YouTube channel ID",
            ),
            sa.Column(
                "channel_name",
                sa.String(255),
                nullable=False,
                comment="YouTube channel name",
            ),
            # Video metadata
            sa.Column(
                "video_type",
                sa.String(50),
                nullable=False,
                comment="Video type: 'video', 'short', 'podcast'",
            ),
            sa.Column(
                "duration_seconds",
                sa.Integer(),
                nullable=True,
                comment="Video duration in seconds",
            ),
            sa.Column(
                "published_at",
                sa.DateTime(),
                nullable=True,
                comment="Video publish date",
            ),
            sa.Column(
                "view_count",
                sa.BigInteger(),
                nullable=True,
                comment="Video view count",
            ),
            # Content tracking
            sa.Column(
                "transcript_hash",
                sa.String(64),
                nullable=False,
                comment="SHA-256 hash of transcript for change detection",
            ),
            sa.Column(
                "transcript_language",
                sa.String(10),
                nullable=True,
                comment="Transcript language code (e.g., 'en', 'es')",
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
                server_default="youtube",
                comment="Vector database namespace",
            ),
            sa.Column(
                "chunk_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="Number of chunks created from this video",
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
            # Additional metadata (JSON)
            sa.Column(
                "metadata",
                sa.JSON(),
                nullable=True,
                comment="Additional metadata from YouTube API",
            ),
            # Constraints
            sa.PrimaryKeyConstraint("id"),
        )

        # Create indexes for efficient lookups
        op.create_index(
            "idx_youtube_video_id",
            "youtube_videos_data",
            ["youtube_video_id"],
            unique=True,
        )
        op.create_index(
            "idx_transcript_hash", "youtube_videos_data", ["transcript_hash"]
        )
        op.create_index("idx_vector_uuid", "youtube_videos_data", ["vector_uuid"])
        op.create_index("idx_video_type", "youtube_videos_data", ["video_type"])
        op.create_index("idx_channel_id", "youtube_videos_data", ["channel_id"])
        op.create_index(
            "idx_ingestion_status",
            "youtube_videos_data",
            ["ingestion_status"],
        )

        print("✅ Created youtube_videos_data table with indexes")


def downgrade():
    """Drop youtube_videos_data table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "youtube_videos_data" in inspector.get_table_names():
        op.drop_table("youtube_videos_data")
        print("✅ Dropped youtube_videos_data table")
