"""
SEC Document Tracking Service

Handles tracking of ingested SEC filings for idempotent ingestion.
Uses the sec_documents_data table to store content hashes and UUIDs.
"""

import hashlib
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


class SECDocument(Base):
    """Model for tracking ingested SEC documents."""

    __tablename__ = "sec_documents_data"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # SEC identifiers
    ticker_symbol: Mapped[str | None] = mapped_column(
        String(10), nullable=True, index=True
    )  # Stock ticker (e.g., "AAPL")
    cik: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    accession_number: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 10-K, 10-Q, 8-K

    # Document identification
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)
    filing_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    document_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Content tracking
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_length: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Raw filing text

    # Vector database tracking
    vector_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    vector_namespace: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="sec_filings"
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

    # Additional metadata (JSON)
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, name="metadata"
    )


class SECDocumentTrackingService:
    """Service for tracking SEC document ingestion."""

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
    def generate_base_uuid(accession_number: str) -> str:
        """
        Generate a deterministic base UUID from SEC accession number.

        This UUID serves as the base for chunk UUIDs:
        - Chunk 0: base_uuid with suffix _0
        - Chunk 1: base_uuid with suffix _1
        - etc.

        Args:
            accession_number: SEC accession number (e.g., "0000320193-23-000077")

        Returns:
            UUID string
        """
        # Use namespace UUID for consistent UUID generation
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
        return str(uuid.uuid5(namespace, accession_number))

    def check_document_needs_reindex(
        self, accession_number: str, content: str
    ) -> tuple[bool, str | None]:
        """
        Check if a document needs to be reindexed based on content hash.

        Args:
            accession_number: SEC accession number
            content: Current document content

        Returns:
            Tuple of (needs_reindex, existing_vector_uuid)
            - needs_reindex: True if document is new or content changed
            - existing_vector_uuid: Existing UUID if document was previously indexed, None otherwise
        """
        new_hash = self.compute_content_hash(content)

        with get_data_db_session() as session:
            existing_doc = (
                session.query(SECDocument)
                .filter_by(accession_number=accession_number)
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
        cik: str,
        accession_number: str,
        company_name: str,
        filing_type: str,
        filing_date: str,
        document_name: str,
        document_url: str,
        content: str,
        vector_uuid: str,
        chunk_count: int,
        ticker_symbol: str | None = None,
        content_length: int | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ):
        """
        Record or update document ingestion in the tracking table.

        Args:
            cik: Central Index Key (SEC company identifier)
            accession_number: SEC accession number (unique document ID)
            company_name: Company name
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            filing_date: Filing date (YYYY-MM-DD)
            document_name: Document filename
            document_url: URL to the document
            content: Document content (for hash computation)
            vector_uuid: Base UUID used for Qdrant point IDs
            chunk_count: Number of chunks created
            ticker_symbol: Stock ticker symbol (e.g., "AAPL")
            content_length: Content length in characters
            metadata: Additional metadata
            status: Ingestion status (success, failed, pending)
            error_message: Error message if ingestion failed
        """
        content_hash = self.compute_content_hash(content)

        with get_data_db_session() as session:
            existing_doc = (
                session.query(SECDocument)
                .filter_by(accession_number=accession_number)
                .first()
            )

            if existing_doc:
                # Update existing record
                existing_doc.ticker_symbol = ticker_symbol
                existing_doc.cik = cik
                existing_doc.company_name = company_name
                existing_doc.filing_type = filing_type
                existing_doc.filing_date = filing_date
                existing_doc.document_name = document_name
                existing_doc.document_url = document_url
                existing_doc.content_hash = content_hash
                existing_doc.content_length = content_length
                existing_doc.content = content  # Store raw content
                existing_doc.vector_uuid = vector_uuid
                existing_doc.chunk_count = chunk_count
                existing_doc.last_ingested_at = datetime.utcnow()
                existing_doc.ingestion_status = status
                existing_doc.error_message = error_message
                existing_doc.extra_metadata = metadata
            else:
                # Create new record
                new_doc = SECDocument(
                    ticker_symbol=ticker_symbol,
                    cik=cik,
                    accession_number=accession_number,
                    company_name=company_name,
                    filing_type=filing_type,
                    filing_date=filing_date,
                    document_name=document_name,
                    document_url=document_url,
                    content_hash=content_hash,
                    content_length=content_length,
                    content=content,  # Store raw content
                    vector_uuid=vector_uuid,
                    chunk_count=chunk_count,
                    ingestion_status=status,
                    error_message=error_message,
                    extra_metadata=metadata,
                )
                session.add(new_doc)

            session.commit()

    def get_document_info(self, accession_number: str) -> dict[str, Any] | None:
        """
        Get document ingestion information.

        Args:
            accession_number: SEC accession number

        Returns:
            Dictionary with document info or None if not found
        """
        with get_data_db_session() as session:
            doc = (
                session.query(SECDocument)
                .filter_by(accession_number=accession_number)
                .first()
            )

            if not doc:
                return None

            return {
                "ticker_symbol": doc.ticker_symbol,
                "cik": doc.cik,
                "accession_number": doc.accession_number,
                "company_name": doc.company_name,
                "filing_type": doc.filing_type,
                "filing_date": doc.filing_date,
                "document_name": doc.document_name,
                "document_url": doc.document_url,
                "content_hash": doc.content_hash,
                "content_length": doc.content_length,
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

    def get_company_filings(
        self, cik: str, filing_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all filings for a company.

        Args:
            cik: Central Index Key
            filing_type: Optional filter by filing type (10-K, 10-Q, etc.)

        Returns:
            List of filing info dictionaries
        """
        with get_data_db_session() as session:
            query = session.query(SECDocument).filter_by(cik=cik)

            if filing_type:
                query = query.filter_by(filing_type=filing_type)

            docs = query.order_by(SECDocument.filing_date.desc()).all()

            return [
                {
                    "ticker_symbol": doc.ticker_symbol,
                    "cik": doc.cik,
                    "accession_number": doc.accession_number,
                    "company_name": doc.company_name,
                    "filing_type": doc.filing_type,
                    "filing_date": doc.filing_date,
                    "document_name": doc.document_name,
                    "ingestion_status": doc.ingestion_status,
                }
                for doc in docs
            ]
