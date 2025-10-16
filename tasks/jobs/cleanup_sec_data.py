#!/usr/bin/env python3
"""
Cleanup SEC Data Script

Removes all SEC filing data from:
1. MySQL sec_documents_data table
2. Qdrant vector database (sec_filings namespace)

Use this to start fresh with SEC ingestion.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add tasks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.base import get_data_db_session  # noqa: E402
from services.qdrant_client import QdrantClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_mysql_data(dry_run: bool = False) -> dict:
    """
    Clean up SEC documents data from MySQL.

    Args:
        dry_run: If True, only count records without deleting

    Returns:
        Dictionary with stats
    """
    logger.info("=" * 60)
    logger.info("CLEANING UP MySQL sec_documents_data TABLE")
    logger.info("=" * 60)

    stats = {"records_found": 0, "records_deleted": 0}

    try:
        with get_data_db_session() as session:
            # Count existing records
            count_result = session.execute(
                text("SELECT COUNT(*) FROM sec_documents_data")
            )
            count = count_result.scalar()
            stats["records_found"] = count

            logger.info(f"Found {count} SEC document records in MySQL")

            if count == 0:
                logger.info("✅ No records to delete")
                return stats

            if dry_run:
                logger.info("🔍 DRY RUN: Would delete all records")
                return stats

            # Delete all records
            logger.info("🗑️  Deleting all records...")
            delete_result = session.execute(text("DELETE FROM sec_documents_data"))
            session.commit()

            stats["records_deleted"] = delete_result.rowcount
            logger.info(f"✅ Deleted {stats['records_deleted']} records from MySQL")

    except Exception as e:
        logger.error(f"❌ Error cleaning up MySQL data: {e}")
        raise

    return stats


async def cleanup_qdrant_vectors(dry_run: bool = False) -> dict:
    """
    Clean up SEC filing vectors from Qdrant.

    Args:
        dry_run: If True, only count vectors without deleting

    Returns:
        Dictionary with stats
    """
    logger.info("=" * 60)
    logger.info("CLEANING UP Qdrant SEC VECTORS (sec_filings namespace)")
    logger.info("=" * 60)

    stats = {"vectors_found": 0, "vectors_deleted": 0}

    try:
        # Initialize Qdrant client
        vector_store = QdrantClient()
        await vector_store.initialize()

        # Count existing vectors with sec_filings namespace
        logger.info("Counting SEC filing vectors in Qdrant...")

        # Get collection info
        collection_info = vector_store.client.get_collection(
            collection_name=vector_store.collection_name
        )
        total_points = collection_info.points_count

        logger.info(f"Collection has {total_points} total vectors")

        # Count vectors with sec_filings namespace
        # We'll use scroll to count them
        namespace_filter = {
            "must": [
                {
                    "key": "namespace",
                    "match": {"value": "sec_filings"},
                }
            ]
        }

        # Scroll through to count
        offset = None
        count = 0
        batch_size = 100

        while True:
            result = vector_store.client.scroll(
                collection_name=vector_store.collection_name,
                scroll_filter=namespace_filter,
                limit=batch_size,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )

            points, next_offset = result

            if not points:
                break

            count += len(points)
            offset = next_offset

            if next_offset is None:
                break

        stats["vectors_found"] = count
        logger.info(f"Found {count} SEC filing vectors in Qdrant")

        if count == 0:
            logger.info("✅ No vectors to delete")
            return stats

        if dry_run:
            logger.info("🔍 DRY RUN: Would delete all SEC filing vectors")
            return stats

        # Delete all vectors with sec_filings namespace
        logger.info("🗑️  Deleting all SEC filing vectors...")

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        delete_filter = Filter(
            must=[
                FieldCondition(
                    key="namespace",
                    match=MatchValue(value="sec_filings"),
                )
            ]
        )

        vector_store.client.delete(
            collection_name=vector_store.collection_name,
            points_selector=delete_filter,
        )

        stats["vectors_deleted"] = count
        logger.info(f"✅ Deleted {stats['vectors_deleted']} vectors from Qdrant")

    except Exception as e:
        logger.error(f"❌ Error cleaning up Qdrant vectors: {e}")
        raise

    return stats


async def main():
    """Main cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up all SEC filing data (MySQL + Qdrant)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (see what would be deleted)
  python cleanup_sec_data.py --dry-run

  # Actually delete everything
  python cleanup_sec_data.py

  # Skip confirmation prompt (DANGEROUS!)
  python cleanup_sec_data.py --force
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)",
    )

    args = parser.parse_args()

    logger.info("")
    logger.info("=" * 60)
    logger.info("SEC DATA CLEANUP SCRIPT")
    logger.info("=" * 60)
    logger.info("")

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No data will be deleted")
    else:
        logger.info("⚠️  WARNING: This will DELETE all SEC filing data!")
        logger.info("   - MySQL: sec_documents_data table")
        logger.info("   - Qdrant: sec_filings namespace")
        logger.info("")

        if not args.force:
            confirmation = input("Are you sure you want to continue? (yes/no): ")
            if confirmation.lower() != "yes":
                logger.info("❌ Cleanup cancelled")
                return

    logger.info("")

    # Clean up MySQL
    mysql_stats = cleanup_mysql_data(dry_run=args.dry_run)

    logger.info("")

    # Clean up Qdrant
    qdrant_stats = await cleanup_qdrant_vectors(dry_run=args.dry_run)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"MySQL Records: {mysql_stats['records_found']} found, {mysql_stats['records_deleted']} deleted")
    logger.info(f"Qdrant Vectors: {qdrant_stats['vectors_found']} found, {qdrant_stats['vectors_deleted']} deleted")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("🔍 DRY RUN COMPLETE - No data was deleted")
    else:
        logger.info("✅ CLEANUP COMPLETE - All SEC data removed")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
