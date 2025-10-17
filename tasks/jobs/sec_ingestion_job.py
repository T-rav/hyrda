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
    JOB_DESCRIPTION = "Automatically ingest 10-K annual reports and 8-K event filings for all 10,000+ public companies"
    REQUIRED_PARAMS = []  # No required params - automatically fetches all companies
    OPTIONAL_PARAMS = [
        "batch_size",  # Default: 10 (parallel processing)
        "use_parallel",  # Default: True
        "limit_10k",  # Default: 1 (latest annual report)
        "limit_8k",  # Default: 100 (recent event filings)
    ]

    def __init__(
        self,
        settings: TasksSettings,
        batch_size: int | str = 10,
        use_parallel: bool | str = True,
        limit_10k: int | str = 1,
        limit_8k: int | str = 0,
    ):
        """
        Initialize SEC ingestion job.

        Args:
            settings: Task settings
            batch_size: Number of filings to process in parallel (default: 10)
            use_parallel: Enable parallel processing (default: True)
            limit_10k: Number of 10-K filings to fetch per company (default: 1)
            limit_8k: Number of 8-K filings to fetch per company (default: 100)
        """
        super().__init__(settings)
        # Fixed configuration - ingest annual reports and event filings
        self.filing_types = ["10-K", "8-K"]  # Annual reports and event filings
        self.user_agent = "8th Light InsightMesh insightmesh@8thlight.com"

        # Configurable performance options (convert from strings if needed)
        self.batch_size = int(batch_size) if isinstance(batch_size, str) else batch_size
        self.use_parallel = (
            use_parallel.lower() in ("true", "1", "yes")
            if isinstance(use_parallel, str)
            else use_parallel
        )

        # Per-filing-type limits
        self.limits_by_type = {
            "10-K": int(limit_10k) if isinstance(limit_10k, str) else limit_10k,
            "8-K": int(limit_8k) if isinstance(limit_8k, str) else limit_8k,
        }

    def get_job_id(self) -> str:
        """Get unique job ID."""
        return "sec_ingestion_all_filings"

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the SEC ingestion job."""
        logger.info(f"Starting SEC ingestion job for filing types: {', '.join(self.filing_types)}")
        for filing_type, limit in self.limits_by_type.items():
            logger.info(f"  - {filing_type}: {limit} filings per company")

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

        # Convert to format expected by orchestrator
        company_list = [
            {
                "ticker": company["ticker_symbol"],
                "cik": company["cik"],
                "name": company["company_name"],
            }
            for company in all_companies
        ]

        # Step 4: Ingest filings for all companies (process each filing type with its own limit)
        logger.info("=" * 60)
        logger.info("STEP 4: Ingesting SEC filings...")
        logger.info("=" * 60)

        # Calculate total expected filings
        total_expected = sum(
            len(company_list) * limit
            for limit in self.limits_by_type.values()
        )
        logger.info(f"Total expected filings: {total_expected:,}")

        # Aggregate results across all filing types
        aggregate_results = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
        }

        # Process each filing type with its specific limit
        for filing_type in self.filing_types:
            limit = self.limits_by_type[filing_type]
            logger.info("=" * 60)
            logger.info(f"Processing {filing_type} filings (limit: {limit} per company)")
            logger.info("=" * 60)

            results = await orchestrator.ingest_multiple_filings(
                companies=company_list,
                filing_types=[filing_type],
                limit_per_type=limit,
                batch_size=self.batch_size,
                use_parallel=self.use_parallel,
            )

            logger.info(
                f"✅ {filing_type} complete: {results['success']} success, "
                f"{results['skipped']} skipped, {results['failed']} failed"
            )

            # Aggregate results
            aggregate_results["total"] += results["total"]
            aggregate_results["success"] += results["success"]
            aggregate_results["skipped"] += results["skipped"]
            aggregate_results["failed"] += results["failed"]

        logger.info("=" * 60)
        logger.info("JOB COMPLETE")
        logger.info("=" * 60)
        logger.info(
            f"SEC ingestion complete: {aggregate_results['success']} success, "
            f"{aggregate_results['skipped']} skipped, {aggregate_results['failed']} failed"
        )

        return {
            "records_processed": aggregate_results["total"],
            "records_success": aggregate_results["success"],
            "records_failed": aggregate_results["failed"],
            "records_skipped": aggregate_results["skipped"],
            "filing_types": ", ".join(self.filing_types),
            "total_companies": len(company_list),
            "batch_size": self.batch_size,
            "parallel_processing": self.use_parallel,
            "limits_by_type": self.limits_by_type,
        }


# Self-register when module is imported (after class definition)
def _register():
    """Register this job type when module is imported."""
    if _job_registry is not None:
        _job_registry.register_job_type("sec_ingestion", SECIngestionJob)
