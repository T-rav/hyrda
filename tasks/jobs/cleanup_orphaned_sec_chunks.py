#!/usr/bin/env python3
"""
Cleanup Orphaned SEC Chunks

Removes chunks from Qdrant that no longer have corresponding records in MySQL.
This happens when documents are reingested or manually deleted from the tracking table.

Usage:
    # Dry run (show what would be deleted)
    python cleanup_orphaned_sec_chunks.py --dry-run

    # Actually delete orphaned chunks
    python cleanup_orphaned_sec_chunks.py
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add tasks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.base import get_data_db_session  # noqa: E402
from services.qdrant_client import QdrantClient  # noqa: E402
from services.sec_document_tracking_service import SECDocument  # noqa: E402


async def cleanup_orphaned_chunks(dry_run: bool = True):
    """
    Remove orphaned chunks from Qdrant.

    Args:
        dry_run: If True, only report what would be deleted without deleting
    """
    logger.info("=" * 70)
    logger.info("SEC Orphaned Chunks Cleanup")
    logger.info("=" * 70)
    logger.info(f"Mode: {'DRY RUN (no deletions)' if dry_run else 'LIVE (will delete)'}")
    logger.info("=" * 70)

    # Set up environment for localhost if not set
    if not os.getenv("QDRANT_HOST"):
        os.environ["QDRANT_HOST"] = "localhost"

    # Initialize Qdrant client
    vector_store = QdrantClient()
    await vector_store.initialize()

    # Step 1: Get all valid chunk IDs from MySQL
    logger.info("\n📊 Step 1: Fetching valid documents from MySQL...")
    valid_base_uuids = set()
    valid_chunk_ids = set()

    with get_data_db_session() as session:
        docs = session.query(SECDocument).filter_by(ingestion_status="success").all()

        logger.info(f"Found {len(docs)} valid documents in MySQL")

        for doc in docs:
            valid_base_uuids.add(doc.vector_uuid)
            # Generate all expected chunk IDs for this document
            # Must match the ID generation in qdrant_client.py upsert_with_namespace()
            for i in range(doc.chunk_count):
                import hashlib
                import uuid

                # chunk_id format: "{accession_number}_chunk_{i}"
                chunk_id = f"{doc.accession_number}_chunk_{i}"
                # Qdrant ID: MD5 hash of "namespace_chunk_id"
                id_string = f"sec_filings_{chunk_id}"
                id_hash = hashlib.md5(id_string.encode(), usedforsecurity=False).hexdigest()
                doc_id = str(uuid.UUID(id_hash))
                valid_chunk_ids.add(doc_id)

        logger.info(f"Total expected chunks: {len(valid_chunk_ids)}")

    # Step 2: Scan Qdrant for all sec_filings vectors
    logger.info("\n🔍 Step 2: Scanning Qdrant for sec_filings vectors...")
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    scroll_filter = Filter(
        must=[FieldCondition(key="namespace", match=MatchValue(value="sec_filings"))]
    )

    all_vector_ids = set()
    offset = None
    batch_count = 0

    while True:
        result = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            scroll_filter=scroll_filter,
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )

        points, offset = result
        batch_count += 1

        if points:
            for point in points:
                all_vector_ids.add(str(point.id))
            logger.info(f"  Scanned batch {batch_count}: {len(points)} vectors (total so far: {len(all_vector_ids)})")

        if offset is None:
            break

    logger.info(f"\n✅ Total vectors in Qdrant: {len(all_vector_ids)}")

    # Step 3: Find orphaned chunks
    logger.info("\n🔍 Step 3: Identifying orphaned chunks...")
    orphaned_ids = all_vector_ids - valid_chunk_ids

    logger.info(f"Valid chunks: {len(valid_chunk_ids)}")
    logger.info(f"Qdrant vectors: {len(all_vector_ids)}")
    logger.info(f"Orphaned chunks: {len(orphaned_ids)}")

    if not orphaned_ids:
        logger.info("\n✅ No orphaned chunks found! Vector database is clean.")
        return

    # Step 4: Delete orphaned chunks (if not dry run)
    if dry_run:
        logger.info("\n📋 DRY RUN: Would delete the following:")
        logger.info(f"  {len(orphaned_ids)} orphaned chunks")

        # Sample some orphaned IDs
        sample_ids = list(orphaned_ids)[:10]
        logger.info("\n  Sample orphaned chunk IDs:")
        for chunk_id in sample_ids:
            logger.info(f"    - {chunk_id}")

        if len(orphaned_ids) > 10:
            logger.info(f"    ... and {len(orphaned_ids) - 10} more")

        logger.info("\n💡 Run without --dry-run to actually delete these chunks")
    else:
        logger.info(f"\n🗑️  Deleting {len(orphaned_ids)} orphaned chunks...")

        # Delete in batches
        from qdrant_client.models import PointIdsList

        batch_size = 1000
        orphaned_list = list(orphaned_ids)
        total_deleted = 0

        for i in range(0, len(orphaned_list), batch_size):
            batch = orphaned_list[i:i + batch_size]

            try:
                vector_store.client.delete(
                    collection_name=vector_store.collection_name,
                    points_selector=PointIdsList(points=batch),
                )
                total_deleted += len(batch)
                logger.info(f"  Deleted batch {i // batch_size + 1}: {len(batch)} chunks (total: {total_deleted}/{len(orphaned_ids)})")
            except Exception as e:
                logger.error(f"  ❌ Failed to delete batch: {e}")

        logger.info(f"\n✅ Successfully deleted {total_deleted} orphaned chunks!")

    logger.info("\n" + "=" * 70)
    logger.info("Cleanup complete!")
    logger.info("=" * 70)


async def main():
    parser = argparse.ArgumentParser(
        description="Cleanup orphaned SEC chunks from Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    await cleanup_orphaned_chunks(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
