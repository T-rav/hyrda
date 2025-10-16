"""SEC Filing Ingestion Job

Scheduled job for ingesting SEC filings into the vector database.
"""

import logging
from typing import Any

from config.settings import TasksSettings
from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient
from services.sec_ingestion_orchestrator import SECIngestionOrchestrator
from services.sec_symbol_service import SECSymbolService

from .base_job import BaseJob

logger = logging.getLogger(__name__)


# Job registry - will be set during import
_job_registry = None


def set_registry(registry):
    """Set the job registry for self-registration."""
    global _job_registry
    _job_registry = registry


class SECIngestionJob(BaseJob):
    """Job for ingesting SEC filings from all public companies."""

    JOB_NAME = "SEC Filing Ingestion"
    JOB_DESCRIPTION = "Automatically ingest latest 10-K annual reports for all 10,000+ public companies"
    REQUIRED_PARAMS = []  # No required params - automatically fetches all companies
    OPTIONAL_PARAMS = [
        "batch_size",  # Default: 10 (parallel processing)
        "use_parallel",  # Default: True
    ]

    def __init__(
        self,
        settings: TasksSettings,
        batch_size: int | str = 10,
        use_parallel: bool | str = True,
    ):
        """
        Initialize SEC ingestion job.

        Args:
            settings: Task settings
            batch_size: Number of filings to process in parallel (default: 10)
            use_parallel: Enable parallel processing (default: True)
        """
        super().__init__(settings)
        # Fixed configuration - ingest only annual reports (most comprehensive)
        self.filing_types = ["10-K"]  # Annual reports only (10-Q quarterly and 8-K events disabled to save costs)
        self.limit_per_type = 1  # Latest filing
        self.user_agent = "8th Light InsightMesh insightmesh@8thlight.com"

        # Configurable performance options (convert from strings if needed)
        self.batch_size = int(batch_size) if isinstance(batch_size, str) else batch_size
        self.use_parallel = (
            use_parallel.lower() in ("true", "1", "yes")
            if isinstance(use_parallel, str)
            else use_parallel
        )

    def get_job_id(self) -> str:
        """Get unique job ID."""
        return "sec_ingestion_all_filings"

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the SEC ingestion job."""
        logger.info(f"Starting SEC ingestion job for filing types: {', '.join(self.filing_types)}")
        logger.info(f"Limit per type: {self.limit_per_type}")

        # Step 1: Sync symbol table with all public companies
        logger.info("=" * 60)
        logger.info("STEP 1: Syncing SEC symbol reference table...")
        logger.info("=" * 60)

        symbol_service = SECSymbolService()

        try:
            sync_stats = symbol_service.populate_symbol_table(force_refresh=False)
            logger.info(
                f"✅ Symbol table synced: "
                f"{sync_stats['total_fetched']} companies fetched, "
                f"{sync_stats['inserted']} inserted, "
                f"{sync_stats['updated']} updated"
            )
        except Exception as e:
            logger.error(f"Failed to sync symbol table: {e}")
            return {
                "records_processed": 0,
                "records_success": 0,
                "records_failed": 1,
                "records_skipped": 0,
                "error": f"Symbol table sync failed: {str(e)}",
            }

        # Step 2: Get all companies from symbol table
        logger.info("=" * 60)
        logger.info("STEP 2: Loading company list from database...")
        logger.info("=" * 60)

        try:
            all_companies = symbol_service.get_all_symbols(active_only=True)
            logger.info(f"✅ Loaded {len(all_companies)} active companies from database")
        except Exception as e:
            logger.error(f"Failed to load companies from database: {e}")
            return {
                "records_processed": 0,
                "records_success": 0,
                "records_failed": 1,
                "records_skipped": 0,
                "error": f"Failed to load companies: {str(e)}",
            }

        if not all_companies:
            logger.error("No companies found in symbol table")
            return {
                "records_processed": 0,
                "records_success": 0,
                "records_failed": 0,
                "records_skipped": 0,
                "details": [],
            }

        # Step 3: Initialize ingestion services
        logger.info("=" * 60)
        logger.info("STEP 3: Initializing ingestion services...")
        logger.info("=" * 60)

        vector_store = QdrantClient()
        embedding_service = OpenAIEmbeddings()
        await vector_store.initialize()

        orchestrator = SECIngestionOrchestrator(user_agent=self.user_agent)
        orchestrator.set_services(vector_store, embedding_service)

        logger.info("✅ Ingestion services initialized")

        # Step 4: Ingest filings for all companies
        logger.info("=" * 60)
        logger.info("STEP 4: Ingesting SEC filings...")
        logger.info("=" * 60)
        logger.info(
            f"Processing {len(all_companies)} companies × "
            f"{len(self.filing_types)} filing types × "
            f"{self.limit_per_type} filings = "
            f"{len(all_companies) * len(self.filing_types) * self.limit_per_type} total filings"
        )

        # Convert to format expected by orchestrator
        company_list = [
            {
                "ticker": company["ticker_symbol"],
                "cik": company["cik"],
                "name": company["company_name"],
            }
            for company in all_companies
        ]

        # Ingest filings with parallel processing
        results = await orchestrator.ingest_multiple_filings(
            companies=company_list,
            filing_types=self.filing_types,
            limit_per_type=self.limit_per_type,
            batch_size=self.batch_size,
            use_parallel=self.use_parallel,
        )

        logger.info("=" * 60)
        logger.info("JOB COMPLETE")
        logger.info("=" * 60)
        logger.info(
            f"SEC ingestion complete: {results['success']} success, "
            f"{results['skipped']} skipped, {results['failed']} failed"
        )

        return {
            "records_processed": results["total"],
            "records_success": results["success"],
            "records_failed": results["failed"],
            "records_skipped": results["skipped"],
            "filing_types": ", ".join(self.filing_types),
            "total_companies": len(company_list),
            "batch_size": self.batch_size,
            "parallel_processing": self.use_parallel,
        }


# Self-register when module is imported (after class definition)
def _register():
    """Register this job type when module is imported."""
    if _job_registry is not None:
        _job_registry.register_job_type("sec_ingestion", SECIngestionJob)
