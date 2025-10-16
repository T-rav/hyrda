"""
SEC Ingestion Orchestrator

Main service that coordinates the SEC filing ingestion process by:
- Managing SEC Edgar client
- Orchestrating filing download and processing
- Coordinating with vector database and embedding services
- Managing the overall ingestion workflow
"""

import logging
import uuid
from datetime import datetime

from .sec_document_tracking_service import SECDocumentTrackingService
from .sec_edgar_client import SECEdgarClient

logger = logging.getLogger(__name__)


class SECIngestionOrchestrator:
    """Main orchestrator for the SEC document ingestion process."""

    def __init__(self, user_agent: str = "Research Bot research@example.com"):
        """
        Initialize the SEC ingestion orchestrator.

        Args:
            user_agent: User-Agent header for SEC API requests
        """
        self.sec_client = SECEdgarClient(user_agent)
        self.document_tracker = SECDocumentTrackingService()
        self.vector_service = None
        self.embedding_service = None

    def _chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
        """
        Simple text chunking by character count with overlap.

        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at a sentence boundary
            if end < len(text):
                # Look for sentence endings within the next 200 chars
                search_end = min(end + 200, len(text))
                sentence_endings = ['. ', '! ', '? ', '\n\n']

                best_break = -1
                for ending in sentence_endings:
                    pos = text.rfind(ending, end - 100, search_end)
                    if pos > best_break:
                        best_break = pos + len(ending)

                if best_break > 0:
                    end = best_break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start forward, accounting for overlap
            start = end - overlap if end < len(text) else end

        return chunks

    def set_services(self, vector_service, embedding_service):
        """
        Set the vector database and embedding services.

        Args:
            vector_service: Vector database service instance
            embedding_service: Embedding service instance
        """
        self.vector_service = vector_service
        self.embedding_service = embedding_service

    async def ingest_company_filing(
        self,
        cik: str,
        filing_type: str = "10-K",
        index: int = 0,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        """
        Ingest a specific filing for a company.

        Args:
            cik: Central Index Key (SEC company identifier)
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            index: Which filing to get (0 = most recent, 1 = second most recent)
            metadata: Additional metadata to add to the document

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check that services are properly initialized
        if not self.vector_service or not self.embedding_service:
            raise RuntimeError(
                "Vector and embedding services must be set before calling ingest_company_filing."
            )

        try:
            # Fetch filing with content
            logger.info(f"Fetching {filing_type} (index {index}) for CIK {cik}...")
            filing = await self.sec_client.get_filing_with_content(
                cik, filing_type, index
            )

            if not filing:
                return False, f"No {filing_type} filing found for CIK {cik}"

            logger.info(
                f"Processing: {filing['company_name']} - {filing['form']} filed on {filing['filing_date']}"
            )

            # Check if document needs reindexing (idempotent ingestion)
            needs_reindex, existing_uuid = (
                self.document_tracker.check_document_needs_reindex(
                    filing["accession_number"], filing["content"]
                )
            )

            if not needs_reindex:
                logger.info(
                    f"⏭️  Skipping (unchanged): {filing['company_name']} - {filing['form']}"
                )
                return True, "Document already indexed with same content"

            if existing_uuid:
                logger.info(
                    f"🔄 Content changed, reindexing: {filing['company_name']} - {filing['form']}"
                )

            # Generate or reuse UUID for this document
            base_uuid = existing_uuid or self.document_tracker.generate_base_uuid(
                filing["accession_number"]
            )

            # Prepare comprehensive document metadata
            doc_metadata = {
                "source": "sec_edgar",
                "cik": filing["cik"],
                "company_name": filing["company_name"],
                "filing_type": filing["form"],
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "document_name": filing["primary_document"],
                "document_url": filing["url"],
                "ingested_at": datetime.utcnow().isoformat(),
            }

            # Add any additional metadata provided
            if metadata:
                doc_metadata.update(metadata)

            # Chunk the content manually (simple chunking for now)
            logger.info(f"Chunking content ({filing['content_length']} chars)...")
            chunks = self._chunk_text(filing["content"], chunk_size=1500, overlap=200)
            logger.info(f"Created {len(chunks)} chunks")

            # Inject document title into each chunk for better semantic search
            doc_header = f"[{filing['company_name']} - {filing['form']} - {filing['filing_date']}]\n\n"
            chunks_with_title = [f"{doc_header}{chunk}" for chunk in chunks]

            # Generate embeddings (with title injected)
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            embeddings = self.embedding_service.embed_batch(chunks_with_title)

            # Prepare metadata for each chunk
            chunk_metadata = []
            chunk_ids = []
            for i, chunk in enumerate(chunks):
                chunk_meta = doc_metadata.copy()
                chunk_meta["chunk_id"] = f"{filing['accession_number']}_chunk_{i}"
                chunk_meta["chunk_index"] = i
                chunk_meta["total_chunks"] = len(chunks)
                chunk_meta["base_uuid"] = base_uuid  # Store base UUID in metadata
                chunk_metadata.append(chunk_meta)

                # Generate proper UUID for each chunk using UUID5 (deterministic)
                chunk_uuid = str(uuid.uuid5(uuid.UUID(base_uuid), f"chunk_{i}"))
                chunk_ids.append(chunk_uuid)

            # Upsert to vector store (with title-injected chunks)
            logger.info(f"Upserting {len(chunks)} chunks to vector store...")
            await self.vector_service.upsert_with_namespace(
                texts=chunks_with_title,
                embeddings=embeddings,
                metadata=chunk_metadata,
                namespace="sec_filings",
            )

            # Record successful ingestion in tracking table
            try:
                self.document_tracker.record_document_ingestion(
                    cik=filing["cik"],
                    accession_number=filing["accession_number"],
                    company_name=filing["company_name"],
                    filing_type=filing["form"],
                    filing_date=filing["filing_date"],
                    document_name=filing["primary_document"],
                    document_url=filing["url"],
                    content=filing["content"],
                    vector_uuid=base_uuid,
                    chunk_count=len(chunks),
                    content_length=filing["content_length"],
                    metadata=metadata,
                    status="success",
                )
                logger.info("Recorded ingestion in tracking table")
            except Exception as tracking_error:
                logger.warning(f"⚠️  Failed to record ingestion tracking: {tracking_error}")

            success_msg = f"✅ Successfully ingested: {filing['company_name']} - {filing['form']} ({len(chunks)} chunks)"
            logger.info(success_msg)
            return True, success_msg

        except Exception as e:
            error_msg = f"❌ Error ingesting filing for CIK {cik}: {e}"
            logger.error(error_msg, exc_info=True)

            # Record failed ingestion
            try:
                base_uuid = self.document_tracker.generate_base_uuid(
                    f"{cik}_{filing_type}_{index}"
                )
                self.document_tracker.record_document_ingestion(
                    cik=cik,
                    accession_number=f"{cik}_{filing_type}_{index}_failed",
                    company_name="Unknown",
                    filing_type=filing_type,
                    filing_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    document_name="",
                    document_url="",
                    content="",
                    vector_uuid=base_uuid,
                    chunk_count=0,
                    status="failed",
                    error_message=str(e),
                )
            except Exception:
                pass  # Don't fail on tracking failures

            return False, error_msg

    async def ingest_multiple_filings(
        self,
        companies: list[dict],
        filing_type: str = "10-K",
        limit_per_company: int = 1,
    ) -> dict[str, Any]:
        """
        Ingest filings for multiple companies.

        Args:
            companies: List of dicts with 'cik' and optionally 'name'
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            limit_per_company: How many filings to ingest per company

        Returns:
            Dictionary with success/failure counts and details
        """
        results = {
            "total": len(companies) * limit_per_company,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        for company in companies:
            cik = company.get("cik")
            company_name = company.get("name", f"CIK {cik}")

            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {company_name} (CIK: {cik})")
            logger.info(f"{'='*60}")

            for index in range(limit_per_company):
                success, message = await self.ingest_company_filing(
                    cik, filing_type, index
                )

                result_entry = {
                    "cik": cik,
                    "company_name": company_name,
                    "filing_type": filing_type,
                    "index": index,
                    "success": success,
                    "message": message,
                }
                results["details"].append(result_entry)

                if success:
                    if "already indexed" in message:
                        results["skipped"] += 1
                    else:
                        results["success"] += 1
                else:
                    results["failed"] += 1

        return results
