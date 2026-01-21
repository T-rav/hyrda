"""
Web Page Tracking Service

Handles tracking of scraped web pages for idempotent ingestion.
Uses the scraped_web_pages table to store content hashes and prevent duplicate indexing.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, get_db_session


class ScrapedWebPage(Base):
    """Model for tracking scraped web pages."""

    __tablename__ = "scraped_web_pages"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # URL identifier (unique)
    url: Mapped[str] = mapped_column(
        String(2048), nullable=False, unique=True, index=True
    )
    url_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA-256 of URL

    # Page info
    page_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Content tracking
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of content
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # HTTP metadata
    last_modified: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # HTTP Last-Modified header
    etag: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # HTTP ETag header

    # Vector database tracking
    vector_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    vector_namespace: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="website_scrape"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Ingestion metadata
    first_scraped_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_scraped_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    scrape_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="success"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional metadata (JSON)
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, name="metadata"
    )


class WebPageTrackingService:
    """Service for tracking web page scraping and ingestion."""

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """
        Compute SHA-256 hash of page content.

        Args:
            content: Page text content

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_url_hash(url: str) -> str:
        """
        Compute SHA-256 hash of URL for indexing.

        Args:
            url: Page URL

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_base_uuid(url: str) -> str:
        """
        Generate a deterministic base UUID from URL.

        This UUID serves as the base for chunk UUIDs:
        - Chunk 0: base_uuid with suffix _0
        - Chunk 1: base_uuid with suffix _1
        - etc.

        Args:
            url: Page URL

        Returns:
            UUID string
        """
        # Use namespace UUID for consistent UUID generation
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
        return str(uuid.uuid5(namespace, url))

    @staticmethod
    def extract_domain(url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain name (e.g., 'example.com')
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc

    def check_page_needs_rescrape(
        self, url: str, content: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if a page needs to be rescraped based on content hash.

        Args:
            url: Page URL
            content: Current page content (if available, for hash comparison)

        Returns:
            Tuple of (needs_rescrape, existing_vector_uuid)
            - needs_rescrape: True if page is new or content changed
            - existing_vector_uuid: Existing UUID if page was previously scraped, None otherwise
        """
        url_hash = self.compute_url_hash(url)

        with get_db_session() as session:
            existing_page = (
                session.query(ScrapedWebPage).filter_by(url_hash=url_hash).first()
            )

            if not existing_page:
                # Page never scraped before
                return True, None

            # If content provided, check if it changed
            if content:
                new_hash = self.compute_content_hash(content)
                if existing_page.content_hash != new_hash:
                    # Content changed, needs rescrape
                    return True, existing_page.vector_uuid

            # Content unchanged or not provided, skip rescrape
            return False, existing_page.vector_uuid

    def record_page_scrape(
        self,
        url: str,
        page_title: str | None,
        content: str,
        vector_uuid: str,
        chunk_count: int,
        last_modified: str | None = None,
        etag: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ):
        """
        Record or update page scrape in the tracking table.

        Args:
            url: Page URL
            page_title: Page title
            content: Page content (for hash computation)
            vector_uuid: Base UUID used for Qdrant point IDs
            chunk_count: Number of chunks created
            last_modified: HTTP Last-Modified header value
            etag: HTTP ETag header value
            metadata: Additional metadata
            status: Scrape status (success, failed, pending)
            error_message: Error message if scrape failed
        """
        content_hash = self.compute_content_hash(content)
        url_hash = self.compute_url_hash(url)
        domain = self.extract_domain(url)

        with get_db_session() as session:
            existing_page = (
                session.query(ScrapedWebPage).filter_by(url_hash=url_hash).first()
            )

            if existing_page:
                # Update existing record
                existing_page.url = url  # Update in case URL changed slightly
                existing_page.page_title = page_title
                existing_page.content_hash = content_hash
                existing_page.content_length = len(content)
                existing_page.last_modified = last_modified
                existing_page.etag = etag
                existing_page.vector_uuid = vector_uuid
                existing_page.chunk_count = chunk_count
                existing_page.last_scraped_at = datetime.utcnow()
                existing_page.scrape_status = status
                existing_page.error_message = error_message
                existing_page.extra_metadata = metadata
            else:
                # Create new record
                new_page = ScrapedWebPage(
                    url=url,
                    url_hash=url_hash,
                    page_title=page_title,
                    website_domain=domain,
                    content_hash=content_hash,
                    content_length=len(content),
                    last_modified=last_modified,
                    etag=etag,
                    vector_uuid=vector_uuid,
                    chunk_count=chunk_count,
                    scrape_status=status,
                    error_message=error_message,
                    extra_metadata=metadata,
                )
                session.add(new_page)

            session.commit()

    def get_page_info(self, url: str) -> dict[str, Any] | None:
        """
        Get page scrape information.

        Args:
            url: Page URL

        Returns:
            Dictionary with page info or None if not found
        """
        url_hash = self.compute_url_hash(url)

        with get_db_session() as session:
            page = session.query(ScrapedWebPage).filter_by(url_hash=url_hash).first()

            if not page:
                return None

            return {
                "url": page.url,
                "url_hash": page.url_hash,
                "page_title": page.page_title,
                "website_domain": page.website_domain,
                "content_hash": page.content_hash,
                "content_length": page.content_length,
                "last_modified": page.last_modified,
                "etag": page.etag,
                "vector_uuid": page.vector_uuid,
                "vector_namespace": page.vector_namespace,
                "chunk_count": page.chunk_count,
                "first_scraped_at": page.first_scraped_at.isoformat()
                if page.first_scraped_at
                else None,
                "last_scraped_at": page.last_scraped_at.isoformat()
                if page.last_scraped_at
                else None,
                "scrape_status": page.scrape_status,
                "error_message": page.error_message,
                "metadata": page.extra_metadata,
            }

    def get_pages_by_domain(self, domain: str) -> list[dict[str, Any]]:
        """
        Get all scraped pages for a domain.

        Args:
            domain: Website domain

        Returns:
            List of page info dictionaries
        """
        with get_db_session() as session:
            pages = (
                session.query(ScrapedWebPage)
                .filter_by(website_domain=domain)
                .order_by(ScrapedWebPage.last_scraped_at.desc())
                .all()
            )

            return [
                {
                    "url": page.url,
                    "page_title": page.page_title,
                    "content_hash": page.content_hash[:16],  # Shortened for display
                    "last_scraped_at": page.last_scraped_at.isoformat()
                    if page.last_scraped_at
                    else None,
                    "scrape_status": page.scrape_status,
                }
                for page in pages
            ]
