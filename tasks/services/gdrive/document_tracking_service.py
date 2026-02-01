"""
Document Tracking Service

Handles tracking of ingested Google Drive documents for idempotent ingestion.
Uses the google_drive_documents_data table to store content hashes and UUIDs.
"""

import hashlib
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Add tasks path for database access
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tasks"))

# Import from tasks/models/base.py (not bot/models/base.py)
from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, get_data_db_session  # noqa: E402

logger = logging.getLogger(__name__)


class GoogleDriveDocument(Base):
    """Model for tracking ingested Google Drive documents."""

    __tablename__ = "google_drive_documents_data"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Google Drive identifiers
    google_drive_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)

    # Content tracking
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Vector database tracking
    vector_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    vector_namespace: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="google_drive"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

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
        String(50), nullable=False, server_default="success"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional metadata (JSON) - using 'extra_metadata' to avoid SQLAlchemy reserved name
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, name="metadata"
    )


class DocumentTrackingService:
    """Service for tracking Google Drive document ingestion."""

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """
        Compute SHA-256 hash of document content.

        Args:
            content: Document text content

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_base_uuid(google_drive_id: str) -> str:
        """
        Generate a deterministic base UUID from Google Drive file ID.

        This UUID serves as the base for chunk UUIDs:
        - Chunk 0: base_uuid with suffix _0
        - Chunk 1: base_uuid with suffix _1
        - etc.

        Args:
            google_drive_id: Google Drive file ID

        Returns:
            UUID string
        """
        # Use namespace UUID for consistent UUID generation
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
        return str(uuid.uuid5(namespace, google_drive_id))

    def check_document_needs_reindex_by_metadata(
        self, google_drive_id: str, modified_time: str | None, file_size: int | None
    ) -> tuple[bool, str | None]:
        """
        Check if a document needs reindexing based on metadata (FAST - no download/transcription).

        This method checks if the file exists and if its modifiedTime or size has changed.
        Use this BEFORE downloading to avoid unnecessary transcription costs for videos/audio.

        Args:
            google_drive_id: Google Drive file ID
            modified_time: File's modifiedTime from Google Drive API (ISO format)
            file_size: File size in bytes

        Returns:
            Tuple of (needs_reindex, existing_vector_uuid)
            - needs_reindex: True if document is new or metadata changed
            - existing_vector_uuid: Existing UUID if document was previously indexed, None otherwise
        """
        with get_data_db_session() as session:
            existing_doc = (
                session.query(GoogleDriveDocument)
                .filter_by(google_drive_id=google_drive_id)
                .first()
            )

            if not existing_doc:
                # Document never indexed before
                return True, None

            # Compare modifiedTime (most reliable indicator)
            if modified_time:
                # Parse the ISO timestamp from Google Drive
                try:
                    new_modified = datetime.fromisoformat(
                        modified_time.replace("Z", "+00:00")
                    )
                    # Compare with last ingestion time
                    if (
                        existing_doc.last_ingested_at
                        and new_modified <= existing_doc.last_ingested_at
                    ):
                        # File not modified since last ingestion - SKIP!
                        return False, existing_doc.vector_uuid
                except (ValueError, AttributeError):
                    logger.debug(
                        "Failed to parse modified time, falling through to size check"
                    )

            # If modified time check inconclusive, check file size
            if (
                file_size is not None
                and existing_doc.file_size is not None
                and file_size == existing_doc.file_size
            ):
                # Same size, likely unchanged - SKIP!
                return False, existing_doc.vector_uuid

            # Metadata suggests change or inconclusive - download to be safe
            return True, existing_doc.vector_uuid

    def check_document_needs_reindex(
        self, google_drive_id: str, content: str
    ) -> tuple[bool, str | None]:
        """
        Check if a document needs to be reindexed based on content hash.

        NOTE: This method requires the full content (expensive for videos/audio).
        Use check_document_needs_reindex_by_metadata() first to avoid download costs.

        Args:
            google_drive_id: Google Drive file ID
            content: Current document content

        Returns:
            Tuple of (needs_reindex, existing_vector_uuid)
            - needs_reindex: True if document is new or content changed
            - existing_vector_uuid: Existing UUID if document was previously indexed, None otherwise
        """
        new_hash = self.compute_content_hash(content)

        with get_data_db_session() as session:
            existing_doc = (
                session.query(GoogleDriveDocument)
                .filter_by(google_drive_id=google_drive_id)
                .first()
            )

            if not existing_doc:
                # Document never indexed before
                return True, None

            if existing_doc.content_hash != new_hash:
                # Content changed, needs reindex
                return True, existing_doc.vector_uuid

            # Content unchanged, skip reindex
            return False, existing_doc.vector_uuid

    def record_document_ingestion(
        self,
        google_drive_id: str,
        file_path: str,
        document_name: str,
        content: str,
        vector_uuid: str,
        chunk_count: int,
        mime_type: str | None = None,
        file_size: int | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ):
        """
        Record or update document ingestion in the tracking table.

        Args:
            google_drive_id: Google Drive file ID
            file_path: Full path in Google Drive
            document_name: Document name/title
            content: Document content (for hash computation)
            vector_uuid: Base UUID used for Qdrant point IDs
            chunk_count: Number of chunks created
            mime_type: Google Drive MIME type
            file_size: File size in bytes
            metadata: Additional metadata
            status: Ingestion status (success, failed, pending)
            error_message: Error message if ingestion failed
        """
        content_hash = self.compute_content_hash(content)

        with get_data_db_session() as session:
            existing_doc = (
                session.query(GoogleDriveDocument)
                .filter_by(google_drive_id=google_drive_id)
                .first()
            )

            if existing_doc:
                # Update existing record
                existing_doc.file_path = file_path
                existing_doc.document_name = document_name
                existing_doc.content_hash = content_hash
                existing_doc.mime_type = mime_type
                existing_doc.file_size = file_size
                existing_doc.vector_uuid = vector_uuid
                existing_doc.chunk_count = chunk_count
                existing_doc.last_ingested_at = datetime.utcnow()
                existing_doc.ingestion_status = status
                existing_doc.error_message = error_message
                existing_doc.extra_metadata = metadata
            else:
                # Create new record
                new_doc = GoogleDriveDocument(
                    google_drive_id=google_drive_id,
                    file_path=file_path,
                    document_name=document_name,
                    content_hash=content_hash,
                    mime_type=mime_type,
                    file_size=file_size,
                    vector_uuid=vector_uuid,
                    chunk_count=chunk_count,
                    ingestion_status=status,
                    error_message=error_message,
                    extra_metadata=metadata,
                )
                session.add(new_doc)

            session.commit()

    def get_document_info(self, google_drive_id: str) -> dict[str, Any] | None:
        """
        Get document ingestion information.

        Args:
            google_drive_id: Google Drive file ID

        Returns:
            Dictionary with document info or None if not found
        """
        with get_data_db_session() as session:
            doc = (
                session.query(GoogleDriveDocument)
                .filter_by(google_drive_id=google_drive_id)
                .first()
            )

            if not doc:
                return None

            return {
                "google_drive_id": doc.google_drive_id,
                "file_path": doc.file_path,
                "document_name": doc.document_name,
                "content_hash": doc.content_hash,
                "mime_type": doc.mime_type,
                "file_size": doc.file_size,
                "vector_uuid": doc.vector_uuid,
                "vector_namespace": doc.vector_namespace,
                "chunk_count": doc.chunk_count,
                "first_ingested_at": doc.first_ingested_at.isoformat()
                if doc.first_ingested_at
                else None,
                "last_ingested_at": doc.last_ingested_at.isoformat()
                if doc.last_ingested_at
                else None,
                "ingestion_status": doc.ingestion_status,
                "error_message": doc.error_message,
                "metadata": doc.extra_metadata,
            }
