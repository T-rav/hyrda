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
    JOB_DESCRIPTION = "Automatically ingest SEC filings (10-K, 10-Q, 8-K) for all public companies"
    REQUIRED_PARAMS = []  # No required params - automatically fetches all companies
    OPTIONAL_PARAMS = [
        "filing_type",  # Default: 10-K
        "limit_per_company",  # Default: 1
        "batch_size",  # Default: 10 (parallel processing)
        "use_parallel",  # Default: True
        "user_agent",  # Default: InsightMesh Research
        "ticker_filter",  # Optional: List of specific tickers to process
        "limit_total_companies",  # Optional: Max number of companies (for testing)
    ]

    def __init__(
        self,
        settings: TasksSettings,
        filing_type: str = "10-K",
        limit_per_company: int = 1,
        batch_size: int = 10,
        use_parallel: bool = True,
        user_agent: str = "InsightMesh Research research@insightmesh.com",
        ticker_filter: list[str] | None = None,
        limit_total_companies: int | None = None,
    ):
        """
        Initialize SEC ingestion job.

        Args:
            settings: Task settings
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            limit_per_company: Number of recent filings to ingest per company
            batch_size: Number of filings to process in parallel (default: 10)
            use_parallel: Enable parallel processing (default: True)
            user_agent: User-Agent header for SEC API
            ticker_filter: Optional list of specific tickers to process (e.g., ["AAPL", "MSFT"])
            limit_total_companies: Optional max number of companies to process (for testing)
        """
        super().__init__(settings)
        self.filing_type = filing_type
        self.limit_per_company = limit_per_company
        self.batch_size = batch_size
        self.use_parallel = use_parallel
        self.user_agent = user_agent
        self.ticker_filter = ticker_filter
        self.limit_total_companies = limit_total_companies

    def get_job_id(self) -> str:
        """Get unique job ID."""
        return f"sec_ingestion_{self.filing_type.lower()}"

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

        # Apply ticker filter if specified
        if self.ticker_filter:
            logger.info(f"Filtering to {len(self.ticker_filter)} specific tickers")
            filtered_tickers = {
                ticker: cik
                for ticker, cik in all_tickers.items()
                if ticker in self.ticker_filter
            }
        else:
            filtered_tickers = all_tickers

        # Apply total company limit if specified (for testing)
        if self.limit_total_companies:
            logger.info(f"Limiting to first {self.limit_total_companies} companies")
            filtered_tickers = dict(list(filtered_tickers.items())[:self.limit_total_companies])

        logger.info(f"Processing {len(filtered_tickers)} companies")

        # Convert to format expected by orchestrator
        company_list = [
            {"cik": cik, "name": ticker}
            for ticker, cik in filtered_tickers.items()
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
            "filing_type": self.filing_type,
            "companies_processed": len(company_list),
            "details": results["details"],
        }


# Self-register when module is imported (after class definition)
def _register():
    """Register this job type when module is imported."""
    if _job_registry is not None:
        _job_registry.register_job_type("sec_ingestion", SECIngestionJob)
