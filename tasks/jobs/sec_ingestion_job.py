"""SEC Filing Ingestion Job

Scheduled job for ingesting SEC filings into the vector database.
"""

import logging
from typing import Any

from config.settings import TasksSettings
from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient
from services.sec_edgar_client import SECEdgarClient
from services.sec_ingestion_orchestrator import SECIngestionOrchestrator

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
    JOB_DESCRIPTION = "Automatically ingest latest 10-K filings for all 10,000+ public companies"
    REQUIRED_PARAMS = []  # No required params - automatically fetches all companies
    OPTIONAL_PARAMS = [
        "batch_size",  # Default: 10 (parallel processing)
        "use_parallel",  # Default: True
    ]

    def __init__(
        self,
        settings: TasksSettings,
        batch_size: int = 10,
        use_parallel: bool = True,
    ):
        """
        Initialize SEC ingestion job.

        Args:
            settings: Task settings
            batch_size: Number of filings to process in parallel (default: 10)
            use_parallel: Enable parallel processing (default: True)
        """
        super().__init__(settings)
        # Fixed configuration
        self.filing_type = "10-K"  # Always ingest 10-K annual reports
        self.limit_per_company = 1  # Latest filing only
        self.user_agent = "8th Light InsightMesh insightmesh@8thlight.com"

        # Configurable performance options
        self.batch_size = batch_size
        self.use_parallel = use_parallel

    def get_job_id(self) -> str:
        """Get unique job ID."""
        return "sec_ingestion_10k"

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the SEC ingestion job."""
        logger.info(f"Starting SEC {self.filing_type} ingestion job")
        logger.info(f"Limit per company: {self.limit_per_company}")

        # Initialize services
        vector_store = QdrantClient()
        embedding_service = OpenAIEmbeddings()

        await vector_store.initialize()

        # Create orchestrator
        orchestrator = SECIngestionOrchestrator(user_agent=self.user_agent)
        orchestrator.set_services(vector_store, embedding_service)

        # Get SEC client
        sec_client = SECEdgarClient(self.user_agent)

        # Fetch all companies from SEC ticker list
        logger.info("Fetching all public companies from SEC Edgar...")
        all_tickers = sec_client.get_all_tickers()

        logger.info(f"Processing {len(all_tickers)} public companies")

        # Convert to format expected by orchestrator
        company_list = [
            {"cik": cik, "name": ticker}
            for ticker, cik in all_tickers.items()
        ]

        if not company_list:
            logger.error("No valid companies to process")
            return {
                "records_processed": 0,
                "records_success": 0,
                "records_failed": 0,
                "records_skipped": 0,
                "details": [],
            }

        # Ingest filings with parallel processing
        results = await orchestrator.ingest_multiple_filings(
            companies=company_list,
            filing_type=self.filing_type,
            limit_per_company=self.limit_per_company,
            batch_size=self.batch_size,
            use_parallel=self.use_parallel,
        )

        logger.info(
            f"SEC ingestion complete: {results['success']} success, "
            f"{results['skipped']} skipped, {results['failed']} failed"
        )

        return {
            "records_processed": results["total"],
            "records_success": results["success"],
            "records_failed": results["failed"],
            "records_skipped": results["skipped"],
            "filing_type": "10-K",
            "total_companies": len(company_list),
            "batch_size": self.batch_size,
            "parallel_processing": self.use_parallel,
        }


# Self-register when module is imported (after class definition)
def _register():
    """Register this job type when module is imported."""
    if _job_registry is not None:
        _job_registry.register_job_type("sec_ingestion", SECIngestionJob)
