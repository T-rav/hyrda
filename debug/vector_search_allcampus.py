#!/usr/bin/env python3
"""
Simple vector search script to emulate internal search tool behavior for AllCampus data.

This script performs a semantic/vector search on the Qdrant vector database,
mimicking how the internal_search_tool works when searching for AllCampus.

Usage:
    python debug/vector_search_allcampus.py
    python debug/vector_search_allcampus.py --query "AllCampus relationships and partnerships"
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add root path for imports
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))

from dotenv import load_dotenv  # noqa: E402

# Load environment variables from root .env
env_file = root_path / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from: {env_file}\n")
else:
    print(f"⚠️  No .env file found at: {env_file}")
    print("Using environment variables from shell\n")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleVectorSearch:
    """Simple vector search that emulates the internal search tool."""

    def __init__(self):
        # Get config from environment
        self.host = os.getenv("VECTOR_HOST", "localhost")
        self.port = int(os.getenv("VECTOR_PORT", "6333"))
        self.api_key = os.getenv("VECTOR_API_KEY")
        self.collection_name = os.getenv(
            "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
        )
        self.openai_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        self.qdrant_client = None
        self.openai_client = None

    async def initialize(self):
        """Initialize Qdrant and OpenAI clients."""
        print("=" * 70)
        print("🔍 VECTOR SEARCH FOR ALLCAMPUS DATA")
        print("=" * 70)
        print(f"Qdrant Host:      {self.host}:{self.port}")
        print(f"Collection:       {self.collection_name}")
        print(f"Embedding Model:  {self.embedding_model}")
        print(f"API Key Set:      {bool(self.api_key)}")
        print(f"OpenAI Key Set:   {bool(self.openai_api_key)}")
        print("=" * 70)
        print()

        # Initialize Qdrant client
        try:
            from qdrant_client import QdrantClient

            if self.api_key:
                self.qdrant_client = QdrantClient(
                    url=f"http://{self.host}:{self.port}",
                    api_key=self.api_key,
                    timeout=60,
                )
            else:
                self.qdrant_client = QdrantClient(
                    host=self.host, port=self.port, timeout=60
                )

            # Verify collection exists
            collections = self.qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                raise ValueError(
                    f"Collection '{self.collection_name}' not found. "
                    f"Available: {collection_names}"
                )

            collection_info = self.qdrant_client.get_collection(self.collection_name)
            print("✅ Connected to Qdrant")
            print(f"   Collection: {self.collection_name}")
            print(f"   Total points: {collection_info.points_count}")
            print()

        except Exception as e:
            print(f"❌ Failed to connect to Qdrant: {e}")
            raise

        # Initialize OpenAI client for embeddings
        try:
            from openai import AsyncOpenAI

            if not self.openai_api_key:
                raise ValueError(
                    "OpenAI API key not found. Set LLM_API_KEY or OPENAI_API_KEY "
                    "environment variable."
                )

            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            print("✅ OpenAI client initialized")
            print()

        except Exception as e:
            print(f"❌ Failed to initialize OpenAI client: {e}")
            raise

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a query using OpenAI."""
        try:
            logger.info(f"Generating embedding for query: '{text[:100]}...'")

            response = await self.openai_client.embeddings.create(
                model=self.embedding_model, input=text
            )

            embedding = response.data[0].embedding
            logger.info(f"Generated embedding with {len(embedding)} dimensions")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Perform vector similarity search on Qdrant.

        This emulates the internal_search_tool's search behavior.
        """
        print("🔍 PERFORMING VECTOR SEARCH")
        print("-" * 70)
        print(f"Query: {query}")
        print(f"Limit: {limit}")
        print()

        try:
            # Step 1: Generate query embedding
            print("📊 Step 1: Generating query embedding...")
            query_embedding = await self.generate_embedding(query)
            print(f"✅ Generated embedding vector ({len(query_embedding)} dimensions)")
            print()

            # Step 2: Search Qdrant
            print("🔍 Step 2: Searching vector database...")
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                score_threshold=0.35,  # Match the RAG_SIMILARITY_THRESHOLD default
            )

            print(f"✅ Found {len(search_result)} results")
            print()

            # Step 3: Format results
            results = []
            for idx, point in enumerate(search_result, 1):
                result = {
                    "id": point.id,
                    "score": point.score,
                    "payload": point.payload,
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def print_results(self, results: list[dict], query: str):
        """Print search results in a readable format."""
        print("=" * 70)
        print("📋 SEARCH RESULTS")
        print("=" * 70)
        print(f"Query: {query}")
        print(f"Total results: {len(results)}")
        print("=" * 70)
        print()

        if not results:
            print("❌ No results found")
            print()
            print("💡 This could mean:")
            print("   • AllCampus data hasn't been synced to the vector database")
            print("   • The query doesn't semantically match any documents")
            print("   • The similarity threshold is too high")
            return

        for idx, result in enumerate(results, 1):
            payload = result["payload"]
            score = result["score"]

            print(f"Result #{idx} (Score: {score:.4f})")
            print("-" * 70)

            # Print common metadata fields
            if "namespace" in payload:
                print(f"Namespace:   {payload['namespace']}")
            if "data_type" in payload:
                print(f"Data Type:   {payload['data_type']}")
            if "name" in payload:
                print(f"Name:        {payload['name']}")
            if "client_id" in payload:
                print(f"Client ID:   {payload['client_id']}")
            if "source" in payload:
                print(f"Source:      {payload['source']}")
            if "created_at" in payload:
                print(f"Created:     {payload['created_at']}")

            # Print document content/text
            text = payload.get("text", "") or payload.get("content", "")
            if text:
                # Truncate long content
                max_len = 200
                if len(text) > max_len:
                    text = text[:max_len] + "..."
                print(f"Content:     {text}")

            # Print any other metadata
            other_keys = set(payload.keys()) - {
                "namespace",
                "data_type",
                "name",
                "client_id",
                "source",
                "created_at",
                "text",
                "content",
            }
            if other_keys:
                print("\nOther metadata:")
                for key in sorted(other_keys):
                    value = payload[key]
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    print(f"  {key}: {value}")

            print()

        print("=" * 70)
        print("✅ Search complete!")
        print()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Vector search for AllCampus data (emulates internal_search_tool)"
    )
    parser.add_argument(
        "--query",
        default="AllCampus relationships and partnerships",
        help="Search query (default: 'AllCampus relationships and partnerships')",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of results (default: 10)"
    )

    args = parser.parse_args()

    # Create and run search
    searcher = SimpleVectorSearch()
    await searcher.initialize()

    results = await searcher.search(query=args.query, limit=args.limit)

    searcher.print_results(results, args.query)


if __name__ == "__main__":
    asyncio.run(main())
