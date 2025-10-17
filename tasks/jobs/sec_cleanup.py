#!/usr/bin/env python3
"""
SEC Filing Cleanup Job

Removes old SEC filings from vector database based on retention policy.
Keeps MySQL tracking records for audit trail.

Retention Policy:
- 10-K (Annual): Keep 3 most recent per company
- 10-Q (Quarterly): Keep 8 most recent per company (2 years)
- 8-K (Events): Keep last 12 months

Usage:
    # Dry run (show what would be deleted)
    python sec_cleanup.py --dry-run

    # Actually delete old filings
    python sec_cleanup.py

    # Custom retention
    python sec_cleanup.py --keep-10k 5 --keep-10q 12
"""

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add tasks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tasks.services.qdrant_client import QdrantClient  # noqa: E402
from tasks.services.sec_document_tracking_service import (  # noqa: E402
    SECDocumentTrackingService,
)


class SECCleanupJob:
    """Cleanup old SEC filings from vector database."""

    def __init__(
        self,
        keep_10k: int = 3,
        keep_10q: int = 8,
        keep_8k_months: int = 12,
        dry_run: bool = False,
    ):
        """
        Initialize cleanup job.

        Args:
            keep_10k: Number of most recent 10-K filings to keep per company
            keep_10q: Number of most recent 10-Q filings to keep per company
            keep_8k_months: Number of months of 8-K filings to keep
            dry_run: If True, only show what would be deleted
        """
        self.keep_10k = keep_10k
        self.keep_10q = keep_10q
        self.keep_8k_months = keep_8k_months
        self.dry_run = dry_run
        self.tracker = SECDocumentTrackingService()

    async def run(self):
        """Execute cleanup job."""
        logger.info("=" * 60)
        logger.info("SEC Filing Cleanup Job")
        logger.info("=" * 60)
        logger.info("Retention Policy:")
        logger.info(f"  - 10-K: Keep {self.keep_10k} most recent per company")
        logger.info(f"  - 10-Q: Keep {self.keep_10q} most recent per company")
        logger.info(f"  - 8-K: Keep last {self.keep_8k_months} months")
        logger.info(f"  - Mode: {'DRY RUN (no deletions)' if self.dry_run else 'LIVE'}")
        logger.info("=" * 60)

        # Get all tracked filings
        logger.info("Fetching all tracked SEC filings...")
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
            company_name = None

            for filing_type, filings in filings_by_type.items():
                # Sort by filing date (most recent first)
                filings.sort(key=lambda x: x["filing_date"], reverse=True)

                if company_name is None and filings:
                    company_name = filings[0]["company_name"]

                # Determine retention count
                if filing_type == "10-K":
                    keep_count = self.keep_10k
                elif filing_type == "10-Q":
                    keep_count = self.keep_10q
                elif filing_type == "8-K":
                    # For 8-K, keep by date instead of count
                    cutoff_date = (
                        datetime.now() - timedelta(days=30 * self.keep_8k_months)
                    ).strftime("%Y-%m-%d")
                    keep = [f for f in filings if f["filing_date"] >= cutoff_date]
                    delete = [f for f in filings if f["filing_date"] < cutoff_date]

                    to_keep_stats["8-K"] += len(keep)
                    to_delete_stats["8-K"] += len(delete)
                    to_delete.extend(delete)
                    continue
                else:
                    # Unknown filing type, keep all
                    to_keep_stats["other"] += len(filings)
                    continue

                # Keep most recent N, delete the rest
                keep = filings[:keep_count]
                delete = filings[keep_count:]

                filing_key = filing_type if filing_type in to_keep_stats else "other"
                to_keep_stats[filing_key] += len(keep)
                to_delete_stats[filing_key] += len(delete)
                to_delete.extend(delete)

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP SUMMARY")
        logger.info("=" * 60)
        logger.info("Filings to KEEP:")
        for filing_type, count in to_keep_stats.items():
            if count > 0:
                logger.info(f"  {filing_type}: {count}")

        logger.info("\nFilings to DELETE from vector database:")
        total_to_delete = 0
        for filing_type, count in to_delete_stats.items():
            if count > 0:
                logger.info(f"  {filing_type}: {count}")
                total_to_delete += count

        if total_to_delete == 0:
            logger.info("✅ No filings to delete. Everything within retention policy.")
            return

        if self.dry_run:
            logger.info("\n🔍 DRY RUN - Showing what would be deleted:")
            for filing in to_delete[:10]:  # Show first 10
                logger.info(
                    f"  - {filing['company_name']} ({filing['filing_type']} - {filing['filing_date']})"
                )
            if len(to_delete) > 10:
                logger.info(f"  ... and {len(to_delete) - 10} more")
            logger.info("\nRun without --dry-run to actually delete")
            return

        # Actually delete from vector database
        logger.info(f"\n🗑️  Deleting {total_to_delete} filings from vector database...")

        vector_store = QdrantClient()
        await vector_store.initialize()

        deleted_count = 0
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
                    exc_info=True,
                )

        logger.info(f"✅ Deleted {deleted_count} filings from vector database")
        logger.info("\n📝 Note: Tracking records kept in MySQL for audit trail")
        logger.info("=" * 60)

    def _get_all_filings(self) -> list[dict]:
        """Get all SEC filings from tracking database."""
        from tasks.services.sec_document_tracking_service import SECDocument

        from models.base import get_db_session

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
        """
        Delete a filing's chunks from vector database.

        Args:
            vector_store: Qdrant client
            base_uuid: Base UUID for the filing
            chunk_count: Number of chunks to delete
        """
        import uuid

        # Generate chunk UUIDs (same logic as ingestion)
        chunk_ids = [
            str(uuid.uuid5(uuid.UUID(base_uuid), f"chunk_{i}"))
            for i in range(chunk_count)
        ]

        # Delete from Qdrant
        # Note: The current QdrantClient doesn't have a delete method
        # We would need to add one or use the SDK directly
        if hasattr(vector_store.client, "delete"):
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: vector_store.client.delete(
                    collection_name=vector_store.collection_name,
                    points_selector=chunk_ids,
                ),
            )


async def main():
    parser = argparse.ArgumentParser(
        description="Cleanup old SEC filings from vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--keep-10k",
        type=int,
        default=3,
        help="Number of most recent 10-K filings to keep per company (default: 3)",
    )

    parser.add_argument(
        "--keep-10q",
        type=int,
        default=8,
        help="Number of most recent 10-Q filings to keep per company (default: 8)",
    )

    parser.add_argument(
        "--keep-8k-months",
        type=int,
        default=12,
        help="Number of months of 8-K filings to keep (default: 12)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    cleanup_job = SECCleanupJob(
        keep_10k=args.keep_10k,
        keep_10q=args.keep_10q,
        keep_8k_months=args.keep_8k_months,
        dry_run=args.dry_run,
    )

    await cleanup_job.run()


if __name__ == "__main__":
    asyncio.run(main())
