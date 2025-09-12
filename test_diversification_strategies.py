#!/usr/bin/env python3
"""
Test different diversification strategies
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider
from services.retrieval_service import RetrievalService

async def test_diversification_strategies():
    """Test different diversification strategies"""

    # Load environment
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.split('#')[0].strip()
                    os.environ.setdefault(key.strip(), value)

    print("🎯 Testing Diversification Strategies")
    print("=" * 50)

    query = "has 8th light worked with apple?"

    # Test different strategies
    strategies = [
        {"mode": "similarity_first", "name": "Pure Similarity Order"},
        {"mode": "balanced", "name": "Balanced (Round-Robin)"},
        {"mode": "document_first", "name": "Document-First (Your Request)"},
    ]

    for strategy in strategies:
        print(f"🔧 Strategy: {strategy['name']}")
        print("-" * 40)

        # Override environment settings
        os.environ["RAG_DIVERSIFICATION_MODE"] = strategy["mode"]
        os.environ["RAG_MAX_UNIQUE_DOCUMENTS"] = "3"  # Test with 3 unique docs max
        os.environ["RAG_MAX_RESULTS"] = "10"  # Allow more results to see the effect

        # Create fresh settings
        settings = Settings()
        settings.rag.enable_hybrid_search = True

        print(f"   Mode: {settings.rag.diversification_mode}")
        print(f"   Max unique docs: {settings.rag.max_unique_documents}")
        print(f"   Max total results: {settings.rag.max_results}")
        print()

        # Initialize services
        vector_store = create_vector_store(settings.vector)
        await vector_store.initialize()

        embedding_service = create_embedding_provider(settings.embedding, settings.llm)
        retrieval_service = RetrievalService(settings)

        # Get results
        results = await retrieval_service.retrieve_context(
            query, vector_store, embedding_service
        )

        # Analyze results
        unique_docs = set()
        doc_chunk_counts = {}

        print(f"📊 Results ({len(results)} total):")
        for i, result in enumerate(results):
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            similarity = result.get("similarity", 0)
            entity_boost = result.get("_entity_boost", 0)

            # Track unique docs and chunk counts
            unique_docs.add(file_name)
            doc_chunk_counts[file_name] = doc_chunk_counts.get(file_name, 0) + 1

            # Truncate filename for display
            display_name = file_name[:50] + "..." if len(file_name) > 50 else file_name

            is_apple = "apple" in file_name.lower()
            status = "🍎" if is_apple else "📄"

            boost_info = f" (+{entity_boost:.2f})" if entity_boost > 0 else ""

            print(f"  {status} {i+1:2}. {display_name}")
            print(f"       Similarity: {similarity:.3f}{boost_info}")

        print()
        print(f"📈 Analysis:")
        print(f"   - Unique documents: {len(unique_docs)}")
        print(f"   - Document distribution:")
        for doc_name, count in doc_chunk_counts.items():
            display_name = doc_name[:60] + "..." if len(doc_name) > 60 else doc_name
            print(f"     • {display_name}: {count} chunks")

        print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_diversification_strategies())
