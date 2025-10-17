"""SEC Filing Cleanup Job

Scheduled job for enforcing retention policy on SEC filings.
Removes old filings from vector database while keeping MySQL tracking records.
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from config.settings import TasksSettings
from models.base import get_db_session
from services.qdrant_client import QdrantClient
from services.sec_document_tracking_service import SECDocument

from .base_job import BaseJob

logger = logging.getLogger(__name__)


# Job registry - will be set during import
_job_registry = None


def set_registry(registry):
    """Set the job registry for self-registration."""
    global _job_registry
    _job_registry = registry


class SECCleanupJob(BaseJob):
    """Job for cleaning up old SEC filings from vector database."""

    JOB_NAME = "SEC Filing Cleanup"
    JOB_DESCRIPTION = "Remove old SEC filings from vector DB based on retention policy (keeps MySQL tracking)"
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = [
        "keep_10k",  # Default: 3
        "keep_10q",  # Default: 8
        "keep_8k_months",  # Default: 12
        "dry_run",  # Default: False
    ]

    def __init__(
        self,
        settings: TasksSettings,
        keep_10k: int = 3,
        keep_10q: int = 8,
        keep_8k_months: int = 12,
        dry_run: bool = False,
    ):
        """
        Initialize SEC cleanup job.

        Args:
            settings: Task settings
            keep_10k: Number of most recent 10-K filings to keep per company
            keep_10q: Number of most recent 10-Q filings to keep per company
            keep_8k_months: Number of months of 8-K filings to keep
            dry_run: If True, only report what would be deleted
        """
        super().__init__(settings)
        self.keep_10k = keep_10k
        self.keep_10q = keep_10q
        self.keep_8k_months = keep_8k_months
        self.dry_run = dry_run

    def get_job_id(self) -> str:
        """Get unique job ID."""
        return "sec_cleanup"

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the SEC cleanup job."""
        logger.info("Starting SEC filing cleanup job")
        logger.info("Retention Policy:")
        logger.info(f"  - 10-K: Keep {self.keep_10k} most recent per company")
        logger.info(f"  - 10-Q: Keep {self.keep_10q} most recent per company")
        logger.info(f"  - 8-K: Keep last {self.keep_8k_months} months")
        logger.info(f"  - Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")

        # Get all tracked filings
        all_filings = self._get_all_filings()
        logger.info(f"Found {len(all_filings)} total filings")

        # Group by company and filing type
        by_company = defaultdict(lambda: defaultdict(list))
        for filing in all_filings:
            cik = filing["cik"]
            filing_type = filing["filing_type"]
            by_company[cik][filing_type].append(filing)

        logger.info(f"Found {len(by_company)} unique companies")

        # Determine what to delete
        to_delete = []
        to_keep_stats = {"10-K": 0, "10-Q": 0, "8-K": 0, "other": 0}
        to_delete_stats = {"10-K": 0, "10-Q": 0, "8-K": 0, "other": 0}

        for _cik, filings_by_type in by_company.items():
            for filing_type, filings in filings_by_type.items():
                # Sort by filing date (most recent first)
                filings.sort(key=lambda x: x["filing_date"], reverse=True)

                # Determine retention
                if filing_type == "10-K":
                    keep_count = self.keep_10k
                    keep = filings[:keep_count]
                    delete = filings[keep_count:]
                elif filing_type == "10-Q":
                    keep_count = self.keep_10q
                    keep = filings[:keep_count]
                    delete = filings[keep_count:]
                elif filing_type == "8-K":
                    # For 8-K, keep by date
                    cutoff_date = (
                        datetime.now() - timedelta(days=30 * self.keep_8k_months)
                    ).strftime("%Y-%m-%d")
                    keep = [f for f in filings if f["filing_date"] >= cutoff_date]
                    delete = [f for f in filings if f["filing_date"] < cutoff_date]
                else:
                    # Unknown type, keep all
                    keep = filings
                    delete = []

                filing_key = filing_type if filing_type in to_keep_stats else "other"
                to_keep_stats[filing_key] += len(keep)
                to_delete_stats[filing_key] += len(delete)
                to_delete.extend(delete)

        total_to_delete = sum(to_delete_stats.values())

        logger.info(f"Files to DELETE: {total_to_delete}")
        for filing_type, count in to_delete_stats.items():
            if count > 0:
                logger.info(f"  {filing_type}: {count}")

        if total_to_delete == 0:
            logger.info("✅ No filings to delete")
            return {
                "records_processed": len(all_filings),
                "records_success": 0,
                "records_failed": 0,
                "records_skipped": len(all_filings),
                "deleted": 0,
                "dry_run": self.dry_run,
            }

        if self.dry_run:
            logger.info("🔍 DRY RUN - No deletions performed")
            return {
                "records_processed": len(all_filings),
                "records_success": 0,
                "records_failed": 0,
                "records_skipped": len(all_filings),
                "would_delete": total_to_delete,
                "dry_run": True,
                "retention_policy": {
                    "10-K": self.keep_10k,
                    "10-Q": self.keep_10q,
                    "8-K_months": self.keep_8k_months,
                },
            }

        # Actually delete from vector database
        logger.info(f"🗑️  Deleting {total_to_delete} filings from vector database...")

        vector_store = QdrantClient()
        await vector_store.initialize()

        deleted_count = 0
        failed_count = 0

        for filing in to_delete:
            try:
                await self._delete_filing_from_vector_db(
                    vector_store, filing["vector_uuid"], filing["chunk_count"]
                )
                deleted_count += 1

                if deleted_count % 10 == 0:
                    logger.info(f"  Deleted {deleted_count}/{total_to_delete}...")

            except Exception as e:
                logger.error(
                    f"Failed to delete {filing['accession_number']}: {e}",
                )
                failed_count += 1

        logger.info(f"✅ Deleted {deleted_count} filings from vector database")
        if failed_count > 0:
            logger.warning(f"⚠️  Failed to delete {failed_count} filings")

        return {
            "records_processed": len(all_filings),
            "records_success": deleted_count,
            "records_failed": failed_count,
            "records_skipped": len(all_filings) - total_to_delete,
            "deleted": deleted_count,
            "dry_run": False,
            "retention_policy": {
                "10-K": self.keep_10k,
                "10-Q": self.keep_10q,
                "8-K_months": self.keep_8k_months,
            },
        }

    def _get_all_filings(self) -> list[dict]:
        """Get all SEC filings from tracking database."""
        filings = []
        with get_db_session() as session:
            docs = (
                session.query(SECDocument).filter_by(ingestion_status="success").all()
            )

            for doc in docs:
                filings.append(
                    {
                        "cik": doc.cik,
                        "company_name": doc.company_name,
                        "filing_type": doc.filing_type,
                        "filing_date": doc.filing_date,
                        "accession_number": doc.accession_number,
                        "vector_uuid": doc.vector_uuid,
                        "chunk_count": doc.chunk_count,
                    }
                )

        return filings

    async def _delete_filing_from_vector_db(
        self, vector_store: QdrantClient, base_uuid: str, chunk_count: int
    ):
        """Delete a filing's chunks from vector database."""
        import asyncio

        # Generate chunk UUIDs (same logic as ingestion)
        chunk_ids = [
            str(uuid.uuid5(uuid.UUID(base_uuid), f"chunk_{i}"))
            for i in range(chunk_count)
        ]

        # Delete from Qdrant
        if hasattr(vector_store.client, "delete"):
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: vector_store.client.delete(
                    collection_name=vector_store.collection_name,
                    points_selector=chunk_ids,
                ),
            )


# Self-register when module is imported (after class definition)
def _register():
    """Register this job type when module is imported."""
    if _job_registry is not None:
        _job_registry.register_job_type("sec_cleanup", SECCleanupJob)
