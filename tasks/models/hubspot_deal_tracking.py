"""
HubSpot Deal Tracking Model

Tracks synced HubSpot deals to enable idempotent ingestion.
Stores content hashes and vector UUIDs to detect changes and avoid duplicates.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class HubSpotDealTracking(Base):
    """Model for tracking synced HubSpot deals."""

    __tablename__ = "hubspot_deals_data"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # HubSpot deal identifier (unique)
    hubspot_deal_id: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )

    # Deal info
    deal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Full document content (stored for retrieval without vector DB)
    document_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content tracking for change detection
    deal_data_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of deal data

    # Vector database tracking
    vector_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )

    # HubSpot metadata
    hubspot_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # From HubSpot updatedAt field

    # Ingestion metadata
    first_ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_ingested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    ingestion_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="success"
    )  # success, failed, removed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional metadata (JSON)
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, name="metadata"
    )
