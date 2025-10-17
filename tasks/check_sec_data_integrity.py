#!/usr/bin/env python3
"""
Check SEC Data Integrity

Verifies that SEC filing data is properly synchronized between MySQL and Qdrant.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add tasks directory to path
sys.path.insert(0, str(Path(__file__).parent))

from models.base import get_data_db_session  # noqa: E402
from services.qdrant_client import QdrantClient  # noqa: E402
from services.sec_document_tracking_service import SECDocument  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_data_integrity():
    """Check data integrity between MySQL and Qdrant."""
    logger.info("=" * 70)
    logger.info("SEC Data Integrity Check")
    logger.info("=" * 70)

    # Initialize Qdrant client (use localhost when running locally)
    import os

    if not os.getenv("QDRANT_HOST"):
        os.environ["QDRANT_HOST"] = "localhost"

    vector_store = QdrantClient()
    await vector_store.initialize()

    # 1. Check MySQL data
    logger.info("\n📊 MySQL Database (sec_documents_data table):")
    logger.info("-" * 70)

    with get_data_db_session() as session:
        total_docs = session.query(SECDocument).count()
        success_docs = (
            session.query(SECDocument).filter_by(ingestion_status="success").count()
        )
        failed_docs = (
            session.query(SECDocument).filter_by(ingestion_status="failed").count()
        )

        logger.info(f"  Total documents: {total_docs}")
        logger.info(f"  ✅ Successful ingestions: {success_docs}")
        logger.info(f"  ❌ Failed ingestions: {failed_docs}")

        # Get breakdown by filing type
        from sqlalchemy import func

        filing_type_counts = (
            session.query(
                SECDocument.filing_type, func.count(SECDocument.id).label("count")
            )
            .filter_by(ingestion_status="success")
            .group_by(SECDocument.filing_type)
            .all()
        )

        logger.info("\n  📋 Breakdown by filing type:")
        for filing_type, count in filing_type_counts:
            logger.info(f"    - {filing_type}: {count} documents")

        # Get breakdown by company
        company_counts = (
            session.query(
                SECDocument.company_name, func.count(SECDocument.id).label("count")
            )
            .filter_by(ingestion_status="success")
            .group_by(SECDocument.company_name)
            .order_by(func.count(SECDocument.id).desc())
            .limit(10)
            .all()
        )

        logger.info("\n  🏢 Top 10 companies by document count:")
        for company, count in company_counts:
            logger.info(f"    - {company}: {count} documents")

        # Get sample documents
        sample_docs = (
            session.query(SECDocument)
            .filter_by(ingestion_status="success")
            .order_by(SECDocument.filing_date.desc())
            .limit(3)
            .all()
        )

        logger.info("\n  📄 Sample recent documents:")
        for doc in sample_docs:
            logger.info(
                f"    - {doc.company_name} ({doc.ticker_symbol}) - {doc.filing_type} - {doc.filing_date}"
            )
            logger.info(f"      Accession: {doc.accession_number}")
            logger.info(f"      Chunks: {doc.chunk_count}")
            logger.info(f"      Vector UUID: {doc.vector_uuid}")
            logger.info(f"      Content length: {doc.content_length:,} chars")

    # 2. Check Qdrant data
    logger.info("\n\n🔍 Qdrant Vector Database (sec_filings namespace):")
    logger.info("-" * 70)

    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        # Count vectors in sec_filings namespace
        scroll_filter = Filter(
            must=[FieldCondition(key="namespace", match=MatchValue(value="sec_filings"))]
        )

        # Get all points (limited sample for inspection)
        result = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            scroll_filter=scroll_filter,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        points = result[0]
        logger.info(f"  Sample vectors retrieved: {len(points)}")

        if points:
            logger.info("\n  📦 Sample vector metadata:")
            for i, point in enumerate(points[:3], 1):
                payload = point.payload
                logger.info(f"\n  Vector {i}:")
                logger.info(f"    Point ID: {point.id}")
                logger.info(f"    Company: {payload.get('company_name', 'N/A')}")
                logger.info(f"    Ticker: {payload.get('ticker_symbol', 'N/A')}")
                logger.info(f"    Filing Type: {payload.get('filing_type', 'N/A')}")
                logger.info(f"    Filing Date: {payload.get('filing_date', 'N/A')}")
                logger.info(f"    Accession: {payload.get('accession_number', 'N/A')}")
                logger.info(f"    Chunk: {payload.get('chunk_index', '?')}/{payload.get('total_chunks', '?')}")
                logger.info(f"    Base UUID: {payload.get('base_uuid', 'N/A')}")
                logger.info(f"    Chunk ID: {payload.get('chunk_id', 'N/A')}")
                text_preview = payload.get("text", "")[:150]
                logger.info(f"    Text preview: {text_preview}...")

        # Try to count total vectors (this might be slow for large collections)
        logger.info("\n  Counting total sec_filings vectors...")
        count_result = vector_store.client.count(
            collection_name=vector_store.collection_name,
            count_filter=scroll_filter,
            exact=True,
        )
        total_vectors = count_result.count
        logger.info(f"  ✅ Total vectors in sec_filings namespace: {total_vectors}")

        # Calculate expected vs actual
        if success_docs > 0:
            with get_data_db_session() as session:
                total_expected_chunks = (
                    session.query(func.sum(SECDocument.chunk_count))
                    .filter_by(ingestion_status="success")
                    .scalar()
                )

            logger.info("\n  🔄 Data Consistency Check:")
            logger.info(f"    Expected chunks (from MySQL): {total_expected_chunks}")
            logger.info(f"    Actual vectors (in Qdrant): {total_vectors}")

            if total_vectors == total_expected_chunks:
                logger.info("    ✅ PERFECT MATCH - Data is consistent!")
            elif total_vectors > total_expected_chunks:
                diff = total_vectors - total_expected_chunks
                logger.info(
                    f"    ⚠️  {diff} more vectors than expected (possible orphaned chunks)"
                )
            else:
                diff = total_expected_chunks - total_vectors
                logger.info(
                    f"    ❌ {diff} missing vectors (some chunks not in Qdrant)"
                )

    except Exception as e:
        logger.error(f"  ❌ Error querying Qdrant: {e}")

    # 3. Data Quality Checks
    logger.info("\n\n🔍 Data Quality Checks:")
    logger.info("-" * 70)

    with get_data_db_session() as session:
        # Check for documents without content
        no_content = (
            session.query(SECDocument)
            .filter_by(ingestion_status="success")
            .filter(
                (SECDocument.content == None) | (SECDocument.content == "")  # noqa: E711
            )
            .count()
        )

        # Check for documents with 0 chunks
        no_chunks = (
            session.query(SECDocument)
            .filter_by(ingestion_status="success")
            .filter(SECDocument.chunk_count == 0)
            .count()
        )

        # Check for documents without vector UUID
        no_uuid = (
            session.query(SECDocument)
            .filter_by(ingestion_status="success")
            .filter((SECDocument.vector_uuid == None) | (SECDocument.vector_uuid == ""))  # noqa: E711
            .count()
        )

        logger.info(f"  Documents without content: {no_content}")
        logger.info(f"  Documents with 0 chunks: {no_chunks}")
        logger.info(f"  Documents without vector UUID: {no_uuid}")

        if no_content == 0 and no_chunks == 0 and no_uuid == 0:
            logger.info("  ✅ All quality checks passed!")
        else:
            logger.info("  ⚠️  Some data quality issues detected")

    logger.info("\n" + "=" * 70)
    logger.info("✅ Integrity check complete!")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(check_data_integrity())
