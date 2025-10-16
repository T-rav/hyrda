#!/usr/bin/env python3
"""
SEC Filing Ingestion CLI

Command-line tool for ingesting SEC filings (10-K, 10-Q, 8-K) into the vector database.

Usage:
    # Ingest most recent 10-K for a company (by CIK)
    python ingest_sec.py --cik 0000320193

    # Ingest by ticker symbol (Apple)
    python ingest_sec.py --ticker AAPL

    # Ingest multiple recent filings
    python ingest_sec.py --cik 0000320193 --limit 3

    # Ingest 10-Q instead of 10-K
    python ingest_sec.py --cik 0000320193 --filing-type 10-Q

    # Ingest multiple companies from a file
    python ingest_sec.py --companies-file companies.txt

    # companies.txt format (one per line):
    # 0000320193  # Apple
    # 0000789019  # Microsoft
    # GOOGL       # Can use ticker symbols too
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add tasks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tasks.services.openai_embeddings import OpenAIEmbeddingService
from tasks.services.qdrant_client import QdrantClient
from tasks.services.sec_edgar_client import SECEdgarClient
from tasks.services.sec_ingestion_orchestrator import SECIngestionOrchestrator


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest SEC filings into vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Company identification
    company_group = parser.add_mutually_exclusive_group(required=True)
    company_group.add_argument("--cik", help="SEC Central Index Key (CIK)")
    company_group.add_argument("--ticker", help="Stock ticker symbol (e.g., AAPL)")
    company_group.add_argument(
        "--companies-file", help="File with list of CIKs/tickers (one per line)"
    )

    # Filing options
    parser.add_argument(
        "--filing-type",
        default="10-K",
        choices=["10-K", "10-Q", "8-K"],
        help="Type of SEC filing (default: 10-K)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of recent filings to ingest per company (default: 1)",
    )

    # Infrastructure options
    parser.add_argument(
        "--qdrant-host", default="localhost", help="Qdrant host (default: localhost)"
    )
    parser.add_argument(
        "--qdrant-port", type=int, default=6333, help="Qdrant port (default: 6333)"
    )
    parser.add_argument(
        "--collection",
        default="knowledge_base",
        help="Qdrant collection name (default: knowledge_base)",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-large",
        help="OpenAI embedding model (default: text-embedding-3-large)",
    )
    parser.add_argument(
        "--user-agent",
        default="8thLight Research research@8thlight.com",
        help="User-Agent for SEC API (required by SEC)",
    )

    args = parser.parse_args()

    # Initialize services
    logger.info("Initializing services...")

    # Vector store
    vector_store = QdrantClient(
        host=args.qdrant_host,
        port=args.qdrant_port,
        collection_name=args.collection,
    )

    # Embedding service
    embedding_service = OpenAIEmbeddingService(model_name=args.embedding_model)

    # Determine embedding dimension
    embedding_dim = 3072 if "large" in args.embedding_model else 1536

    # Initialize vector store
    await vector_store.initialize()

    # SEC ingestion orchestrator
    orchestrator = SECIngestionOrchestrator(user_agent=args.user_agent)
    orchestrator.set_services(vector_store, embedding_service)

    # Determine which companies to process
    companies = []

    if args.cik:
        companies.append({"cik": args.cik})
    elif args.ticker:
        sec_client = SECEdgarClient(args.user_agent)
        cik = sec_client.lookup_cik(args.ticker)
        if not cik:
            logger.error(f"Could not find CIK for ticker {args.ticker}")
            logger.error(
                "Try using --cik directly, or add the ticker to the lookup_cik() method"
            )
            sys.exit(1)
        companies.append({"cik": cik, "name": args.ticker})
    elif args.companies_file:
        # Read companies from file
        companies_path = Path(args.companies_file)
        if not companies_path.exists():
            logger.error(f"Companies file not found: {args.companies_file}")
            sys.exit(1)

        sec_client = SECEdgarClient(args.user_agent)
        with open(companies_path) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Check if it's a ticker or CIK
                if line.isalpha() and len(line) <= 5:
                    # Likely a ticker
                    cik = sec_client.lookup_cik(line)
                    if cik:
                        companies.append({"cik": cik, "name": line})
                    else:
                        logger.warning(f"Could not find CIK for ticker {line}")
                else:
                    # Assume it's a CIK
                    companies.append({"cik": line})

    if not companies:
        logger.error("No companies to process")
        sys.exit(1)

    logger.info(f"Processing {len(companies)} companies...")

    # Ingest filings
    results = await orchestrator.ingest_multiple_filings(
        companies=companies,
        filing_type=args.filing_type,
        limit_per_company=args.limit,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Total filings attempted: {results['total']}")
    print(f"✅ Successfully ingested: {results['success']}")
    print(f"⏭️  Skipped (unchanged):   {results['skipped']}")
    print(f"❌ Failed:                 {results['failed']}")
    print("=" * 60)

    if results["failed"] > 0:
        print("\nFailed filings:")
        for detail in results["details"]:
            if not detail["success"]:
                print(
                    f"  - {detail['company_name']} ({detail['cik']}): {detail['message']}"
                )

    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
