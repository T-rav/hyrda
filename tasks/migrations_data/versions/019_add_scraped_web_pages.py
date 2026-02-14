"""Add scraped_web_pages table for tracking website scraping

Revision ID: 019_add_scraped_web_pages
Revises: 018_create_youtube_videos_data
Create Date: 2026-02-12

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    """Add scraped_web_pages table for tracking scraped pages with content hashes."""
    op.create_table(
        "scraped_web_pages",
        # Primary key
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        # URL identifiers
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        # Page info
        sa.Column("page_title", sa.String(512), nullable=True),
        sa.Column("website_domain", sa.String(255), nullable=False),
        # Content tracking
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_length", sa.Integer, nullable=True),
        # HTTP metadata
        sa.Column("last_modified", sa.String(100), nullable=True),
        sa.Column("etag", sa.String(255), nullable=True),
        # Vector database tracking
        sa.Column("vector_uuid", sa.String(36), nullable=False),
        sa.Column(
            "vector_namespace",
            sa.String(100),
            nullable=False,
            server_default="website_scrape",
        ),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        # Ingestion metadata
        sa.Column(
            "first_scraped_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_scraped_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "scrape_status", sa.String(50), nullable=False, server_default="success"
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        # Additional metadata
        sa.Column("metadata", sa.JSON, nullable=True),
        # Indexes for performance
        sa.Index("idx_url_hash", "url_hash"),
        sa.Index("idx_website_domain", "website_domain"),
    )


def downgrade():
    """Remove scraped_web_pages table."""
    op.drop_table("scraped_web_pages")
