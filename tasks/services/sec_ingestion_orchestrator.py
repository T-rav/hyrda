"""
SEC Ingestion Orchestrator

Main service that coordinates the SEC filing ingestion process by:
- Managing SEC Edgar client and document builder
- Fetching narrative text + financial metrics
- Orchestrating filing download and processing
- Coordinating with vector database and embedding services
- Managing the overall ingestion workflow
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from .sec_document_builder import SECDocumentBuilder
from .sec_document_tracking_service import SECDocumentTrackingService
from .sec_edgar_client import SECEdgarClient
from .sec_symbol_service import SECSymbolService

logger = logging.getLogger(__name__)


class SECIngestionOrchestrator:
    """Main orchestrator for the SEC document ingestion process."""

    def __init__(self, user_agent: str = "8th Light InsightMesh insightmesh@8thlight.com"):
        """
        Initialize the SEC ingestion orchestrator.

        Args:
            user_agent: User-Agent header for SEC API requests
        """
        self.sec_client = SECEdgarClient(user_agent)
        self.document_tracker = SECDocumentTrackingService()
        self.symbol_service = SECSymbolService()
        self.document_builder = SECDocumentBuilder()
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
                sentence_endings = [". ", "! ", "? ", "\n\n"]

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
        ticker_symbol: str,
        cik: str,
        company_name: str,
        filing_type: str = "10-K",
        index: int = 0,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        """
        Ingest a specific filing for a company with narrative + financial data.

        Args:
            ticker_symbol: Stock ticker (e.g., "AAPL")
            cik: Central Index Key (SEC company identifier)
            company_name: Company name
            filing_type: Type of filing (10-K, 10-Q, 8-K, DEF 14A)
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
            # Fetch recent filings
            logger.info(f"Fetching {filing_type} for {ticker_symbol} (CIK {cik})...")
            filings = await self.sec_client.get_recent_filings(cik, filing_type, limit=index + 1)

            if len(filings) <= index:
                return False, f"No {filing_type} filing found at index {index} for {ticker_symbol}"

            filing = filings[index]
            accession_number = filing["accession_number"]
            filing_date = filing["filing_date"]

            logger.info(
                f"Processing: {company_name} ({ticker_symbol}) - {filing_type} filed on {filing_date}"
            )

            # Download the HTML content
            html_content = await self.sec_client.download_filing(
                cik, accession_number, filing["primary_document"]
            )

            # Fetch company facts (financial metrics) - only for 10-K/10-Q
            company_facts = None
            if filing_type in ["10-K", "10-Q"]:
                logger.info(f"Fetching company facts (financial metrics) for {ticker_symbol}...")
                company_facts = await self.sec_client.get_company_facts(cik)

            # Build comprehensive document using edgartools + financial data
            logger.info(f"Building comprehensive {filing_type} document...")
            if filing_type == "10-K":
                document_text = self.document_builder.build_10k_document(
                    ticker_symbol=ticker_symbol,
                    company_name=company_name,
                    cik=cik,
                    filing_date=filing_date,
                    html_content=html_content,
                    company_facts=company_facts,
                )
            elif filing_type == "10-Q":
                document_text = self.document_builder.build_10q_document(
                    ticker_symbol=ticker_symbol,
                    company_name=company_name,
                    cik=cik,
                    filing_date=filing_date,
                    html_content=html_content,
                    company_facts=company_facts,
                )
            elif filing_type == "8-K":
                document_text = self.document_builder.build_8k_document(
                    ticker_symbol=ticker_symbol,
                    company_name=company_name,
                    cik=cik,
                    filing_date=filing_date,
                    html_content=html_content,
                )
            else:
                # Fallback for other filing types
                document_text = self.document_builder._build_document_fallback(
                    ticker_symbol=ticker_symbol,
                    company_name=company_name,
                    cik=cik,
                    filing_date=filing_date,
                    html_content=html_content,
                    filing_type=filing_type,
                    company_facts=company_facts,
                )

            # Check if document needs reindexing (idempotent ingestion)
            needs_reindex, existing_uuid = (
                self.document_tracker.check_document_needs_reindex(
                    accession_number, document_text
                )
            )

            if not needs_reindex:
                logger.info(
                    f"⏭️  Skipping (unchanged): {company_name} ({ticker_symbol}) - {filing_type}"
                )
                return True, "Document already indexed with same content"

            if existing_uuid:
                logger.info(
                    f"🔄 Content changed, reindexing: {company_name} ({ticker_symbol}) - {filing_type}"
                )

            # Generate or reuse UUID for this document
            base_uuid = existing_uuid or self.document_tracker.generate_base_uuid(
                accession_number
            )

            # Prepare comprehensive document metadata
            doc_metadata = {
                "source": "sec_edgar",
                "ticker_symbol": ticker_symbol,
                "cik": cik,
                "company_name": company_name,
                "filing_type": filing_type,
                "filing_date": filing_date,
                "accession_number": accession_number,
                "document_name": filing["primary_document"],
                "document_url": filing["url"],
                "ingested_at": datetime.utcnow().isoformat(),
            }

            # Add any additional metadata provided
            if metadata:
                doc_metadata.update(metadata)

            # Chunk the content
            logger.info(f"Chunking content ({len(document_text)} chars)...")
            chunks = self._chunk_text(document_text, chunk_size=1500, overlap=200)
            logger.info(f"Created {len(chunks)} chunks")

            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            embeddings = self.embedding_service.embed_batch(chunks)

            # Prepare metadata for each chunk
            chunk_metadata = []
            chunk_ids = []
            for i in range(len(chunks)):
                chunk_meta = doc_metadata.copy()
                chunk_meta["chunk_id"] = f"{accession_number}_chunk_{i}"
                chunk_meta["chunk_index"] = i
                chunk_meta["total_chunks"] = len(chunks)
                chunk_meta["base_uuid"] = base_uuid  # Store base UUID in metadata
                chunk_metadata.append(chunk_meta)

                # Generate proper UUID for each chunk using UUID5 (deterministic)
                chunk_uuid = str(uuid.uuid5(uuid.UUID(base_uuid), f"chunk_{i}"))
                chunk_ids.append(chunk_uuid)

            # Upsert to vector store
            logger.info(f"Upserting {len(chunks)} chunks to vector store...")
            await self.vector_service.upsert_with_namespace(
                texts=chunks,
                embeddings=embeddings,
                metadata=chunk_metadata,
                namespace="sec_filings",
            )

            # Record successful ingestion in tracking table
            try:
                self.document_tracker.record_document_ingestion(
                    ticker_symbol=ticker_symbol,  # New field
                    cik=cik,
                    accession_number=accession_number,
                    company_name=company_name,
                    filing_type=filing_type,
                    filing_date=filing_date,
                    document_name=filing["primary_document"],
                    document_url=filing["url"],
                    content=document_text,
                    vector_uuid=base_uuid,
                    chunk_count=len(chunks),
                    content_length=len(document_text),
                    metadata=doc_metadata,  # Fixed: pass doc_metadata instead of metadata
                    status="success",
                )
                logger.info("Recorded ingestion in tracking table")
            except Exception as tracking_error:
                logger.warning(f"⚠️  Failed to record ingestion tracking: {tracking_error}")

            success_msg = f"✅ Successfully ingested: {company_name} ({ticker_symbol}) - {filing_type} ({len(chunks)} chunks)"
            logger.info(success_msg)
            return True, success_msg

        except Exception as e:
            error_msg = f"❌ Error ingesting filing for {ticker_symbol}: {e}"
            logger.error(error_msg, exc_info=True)

            # Record failed ingestion
            try:
                base_uuid = self.document_tracker.generate_base_uuid(
                    f"{cik}_{filing_type}_{index}"
                )
                self.document_tracker.record_document_ingestion(
                    ticker_symbol=ticker_symbol,
                    cik=cik,
                    accession_number=f"{cik}_{filing_type}_{index}_failed",
                    company_name=company_name,
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

    async def _ingest_filing_safe(
        self,
        ticker_symbol: str,
        cik: str,
        company_name: str,
        filing_type: str,
        index: int,
    ) -> dict[str, Any]:
        """
        Safely ingest a single filing with error handling.

        Args:
            ticker_symbol: Stock ticker
            cik: Central Index Key
            company_name: Company name for logging
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            index: Filing index

        Returns:
            Dictionary with result details
        """
        try:
            success, message = await self.ingest_company_filing(
                ticker_symbol, cik, company_name, filing_type, index
            )
            return {
                "ticker_symbol": ticker_symbol,
                "cik": cik,
                "company_name": company_name,
                "filing_type": filing_type,
                "index": index,
                "success": success,
                "message": message,
            }
        except Exception as e:
            logger.error(f"Error processing {company_name} ({ticker_symbol}) {filing_type} index {index}: {e}")
            return {
                "ticker_symbol": ticker_symbol,
                "cik": cik,
                "company_name": company_name,
                "filing_type": filing_type,
                "index": index,
                "success": False,
                "message": f"Exception during ingestion: {str(e)}",
            }

    async def ingest_multiple_filings(
        self,
        companies: list[dict],
        filing_types: list[str] = ["10-K"],
        limit_per_type: int = 1,
        batch_size: int = 10,
        use_parallel: bool = True,
    ) -> dict[str, Any]:
        """
        Ingest filings for multiple companies with parallel processing.

        Args:
            companies: List of dicts with 'ticker', 'cik', and 'name'
            filing_types: List of filing types to ingest (e.g., ["10-K", "10-Q", "8-K"])
            limit_per_type: How many filings to ingest per type per company
            batch_size: Number of filings to process in parallel (default: 10)
            use_parallel: If True, use parallel processing. If False, sequential (default: True)

        Returns:
            Dictionary with success/failure counts and details
        """
        results = {
            "total": len(companies) * len(filing_types) * limit_per_type,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        # Build list of all filing tasks
        filing_tasks = []
        for company in companies:
            ticker = company.get("ticker", "")
            cik = company.get("cik")
            company_name = company.get("name", f"{ticker} (CIK {cik})")

            for filing_type in filing_types:
                for index in range(limit_per_type):
                    filing_tasks.append((ticker, cik, company_name, filing_type, index))

        total_tasks = len(filing_tasks)
        logger.info(
            f"Starting ingestion: {total_tasks} total filings "
            f"({len(companies)} companies × {len(filing_types)} types × {limit_per_type} filings)"
        )

        if use_parallel:
            # Process in batches with parallel execution
            for i in range(0, len(filing_tasks), batch_size):
                batch = filing_tasks[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(filing_tasks) + batch_size - 1) // batch_size

                logger.info(
                    f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} filings)"
                )

                # Create tasks for this batch
                batch_coros = [
                    self._ingest_filing_safe(ticker, cik, name, filing_type, idx)
                    for ticker, cik, name, filing_type, idx in batch
                ]

                # Execute batch in parallel
                batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)

                # Process results
                for result in batch_results:
                    if isinstance(result, Exception):
                        results["failed"] += 1
                        results["details"].append(
                            {"success": False, "message": f"Exception: {str(result)}"}
                        )
                    else:
                        if result["success"]:
                            if "already indexed" in result["message"]:
                                results["skipped"] += 1
                            else:
                                results["success"] += 1
                        else:
                            results["failed"] += 1
                        results["details"].append(result)

                logger.info(
                    f"Batch {batch_num} complete. Success: {results['success']}, "
                    f"Skipped: {results['skipped']}, Failed: {results['failed']}"
                )

        else:
            # Sequential processing
            for i, (ticker, cik, name, filing_type, idx) in enumerate(filing_tasks, 1):
                logger.info(f"Processing {i}/{total_tasks}: {name} ({ticker}) - {filing_type}")

                result = await self._ingest_filing_safe(ticker, cik, name, filing_type, idx)

                if result["success"]:
                    if "already indexed" in result["message"]:
                        results["skipped"] += 1
                    else:
                        results["success"] += 1
                else:
                    results["failed"] += 1

                results["details"].append(result)

                if i % 10 == 0:
                    logger.info(
                        f"Progress: {i}/{total_tasks}. Success: {results['success']}, "
                        f"Skipped: {results['skipped']}, Failed: {results['failed']}"
                    )

        logger.info(
            f"\n{'='*60}\n"
            f"✅ Ingestion complete!\n"
            f"Total: {results['total']}\n"
            f"Success: {results['success']}\n"
            f"Skipped: {results['skipped']}\n"
            f"Failed: {results['failed']}\n"
            f"{'='*60}"
        )

        return results
