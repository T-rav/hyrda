"""
Example usage of SEC filing ingestion.

This file demonstrates how to programmatically use the SEC ingestion services.
"""

import asyncio
import os

# You would normally set these via environment variables
os.environ.setdefault("OPENAI_API_KEY", "your-key-here")
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")

from services.embedding_provider import EmbeddingProvider
from services.vector_store import QdrantVectorStore

from services.sec_edgar_client import SECEdgarClient
from services.sec_ingestion_orchestrator import SECIngestionOrchestrator


async def example_single_company():
    """Example: Ingest most recent 10-K for Apple."""
    print("=" * 60)
    print("Example 1: Single Company Ingestion")
    print("=" * 60)

    # Initialize services
    vector_store = QdrantVectorStore(
        host="localhost", port=6333, collection_name="knowledge_base"
    )

    embedding_service = EmbeddingProvider(model_name="text-embedding-3-large")

    await vector_store.initialize(embedding_dimension=3072)

    # Create orchestrator
    orchestrator = SECIngestionOrchestrator(
        user_agent="MyCompany Research research@mycompany.com"
    )
    orchestrator.set_services(vector_store, embedding_service)

    # Ingest Apple's most recent 10-K
    success, message = await orchestrator.ingest_company_filing(
        cik="0000320193",  # Apple's CIK
        filing_type="10-K",
        index=0,  # Most recent
    )

    print(f"\nResult: {message}")


async def example_multiple_companies():
    """Example: Ingest 10-Ks for multiple tech companies."""
    print("\n" + "=" * 60)
    print("Example 2: Multiple Companies Batch Ingestion")
    print("=" * 60)

    # Initialize services
    vector_store = QdrantVectorStore(
        host="localhost", port=6333, collection_name="knowledge_base"
    )

    embedding_service = EmbeddingProvider(model_name="text-embedding-3-large")

    await vector_store.initialize(embedding_dimension=3072)

    # Create orchestrator
    orchestrator = SECIngestionOrchestrator(
        user_agent="MyCompany Research research@mycompany.com"
    )
    orchestrator.set_services(vector_store, embedding_service)

    # Define companies
    companies = [
        {"cik": "0000320193", "name": "Apple Inc"},
        {"cik": "0000789019", "name": "Microsoft Corp"},
        {"cik": "0001652044", "name": "Alphabet Inc"},
    ]

    # Ingest most recent 10-K for each
    results = await orchestrator.ingest_multiple_filings(
        companies=companies, filing_type="10-K", limit_per_company=1
    )

    # Print summary
    print(f"\nTotal: {results['total']}")
    print(f"Success: {results['success']}")
    print(f"Skipped: {results['skipped']}")
    print(f"Failed: {results['failed']}")


async def example_check_filings():
    """Example: Check what filings are already ingested."""
    print("\n" + "=" * 60)
    print("Example 3: Check Ingested Filings")
    print("=" * 60)

    from services.sec_document_tracking_service import SECDocumentTrackingService

    tracker = SECDocumentTrackingService()

    # Get all Apple filings
    filings = tracker.get_company_filings(cik="0000320193", filing_type="10-K")

    print(f"\nFound {len(filings)} Apple 10-K filings:\n")
    for filing in filings:
        print(
            f"  {filing['filing_date']}: {filing['filing_type']} - {filing['ingestion_status']}"
        )


async def example_explore_sec_api():
    """Example: Explore what filings are available without ingesting."""
    print("\n" + "=" * 60)
    print("Example 4: Explore Available Filings")
    print("=" * 60)

    client = SECEdgarClient(user_agent="MyCompany Research research@mycompany.com")

    # Get company info
    company_data = await client.get_company_info(cik="0000320193")
    print(f"\nCompany: {company_data.get('name')}")
    print(f"CIK: {company_data.get('cik')}")

    # Get recent 10-K filings
    filings = await client.get_recent_filings(
        cik="0000320193", filing_type="10-K", limit=5
    )

    print("\nRecent 10-K filings:")
    for i, filing in enumerate(filings):
        print(f"  {i}. {filing['filing_date']}: {filing['accession_number']}")
        print(f"     URL: {filing['url']}")


async def main():
    """Run all examples."""
    print("SEC Filing Ingestion Examples")
    print("=" * 60)
    print("NOTE: These examples require:")
    print("  - Qdrant running on localhost:6333")
    print("  - OpenAI API key in environment")
    print("  - MySQL database with migrations run")
    print("=" * 60)

    # Example 1: Single company
    # await example_single_company()

    # Example 2: Multiple companies
    # await example_multiple_companies()

    # Example 3: Check existing filings
    # await example_check_filings()

    # Example 4: Explore SEC API
    await example_explore_sec_api()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    # To run an example, uncomment it in main() above, then:
    # python example_sec_usage.py
    asyncio.run(main())
