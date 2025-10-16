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
    """Job for ingesting SEC filings."""

    JOB_NAME = "SEC Filing Ingestion"
    JOB_DESCRIPTION = "Ingest SEC filings (10-K, 10-Q, 8-K) into vector database for sales intelligence"
    REQUIRED_PARAMS = ["companies"]  # List of CIKs or tickers
    OPTIONAL_PARAMS = [
        "filing_type",  # Default: 10-K
        "limit_per_company",  # Default: 1
        "batch_size",  # Default: 10 (parallel processing)
        "use_parallel",  # Default: True
        "user_agent",  # Default: InsightMesh Research
    ]

    def __init__(
        self,
        settings: TasksSettings,
        companies: list[str] | None = None,
        filing_type: str = "10-K",
        limit_per_company: int = 1,
        batch_size: int = 10,
        use_parallel: bool = True,
        user_agent: str = "InsightMesh Research research@insightmesh.com",
    ):
        """
        Initialize SEC ingestion job.

        Args:
            settings: Task settings
            companies: List of CIKs or ticker symbols (e.g., ["AAPL", "MSFT", "0000320193"])
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            limit_per_company: Number of recent filings to ingest per company
            batch_size: Number of filings to process in parallel (default: 10)
            use_parallel: Enable parallel processing (default: True)
            user_agent: User-Agent header for SEC API
        """
        super().__init__(settings)
        self.companies = companies or []
        self.filing_type = filing_type
        self.limit_per_company = limit_per_company
        self.batch_size = batch_size
        self.use_parallel = use_parallel
        self.user_agent = user_agent

    def get_job_id(self) -> str:
        """Get unique job ID."""
        return f"sec_ingestion_{self.filing_type.lower()}"

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the SEC ingestion job."""
        logger.info(f"Starting SEC {self.filing_type} ingestion job")
        logger.info(f"Companies: {len(self.companies)}")
        logger.info(f"Limit per company: {self.limit_per_company}")

        # Initialize services
        vector_store = QdrantClient()
        embedding_service = OpenAIEmbeddings()

        await vector_store.initialize()

        # Create orchestrator
        orchestrator = SECIngestionOrchestrator(user_agent=self.user_agent)
        orchestrator.set_services(vector_store, embedding_service)

        # Convert companies list to format expected by orchestrator
        # Handle both CIKs and ticker symbols
        sec_client = SECEdgarClient(self.user_agent)
        company_list = []

        for company_id in self.companies:
            # Check if it's a ticker or CIK
            if company_id.isalpha() and len(company_id) <= 5:
                # Likely a ticker
                cik = sec_client.lookup_cik(company_id.upper())
                if cik:
                    company_list.append({"cik": cik, "name": company_id.upper()})
                else:
                    logger.warning(f"Could not find CIK for ticker {company_id}")
            else:
                # Assume it's a CIK
                company_list.append({"cik": company_id})

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
            "filing_type": self.filing_type,
            "companies_processed": len(company_list),
            "details": results["details"],
        }


# Self-register when module is imported (after class definition)
def _register():
    """Register this job type when module is imported."""
    if _job_registry is not None:
        _job_registry.register_job_type("sec_ingestion", SECIngestionJob)
