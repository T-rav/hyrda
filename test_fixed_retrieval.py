#!/usr/bin/env python3
"""
Test the fixed retrieval service with entity boosting and diversification
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

async def test_fixed_retrieval():
    """Test the fixed retrieval with current settings"""

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

    settings = Settings()

    print("🎯 Testing Fixed Retrieval Service")
    print("=" * 50)
    print(f"Current settings:")
    print(f"  - Hybrid search: {settings.rag.enable_hybrid_search}")
    print(f"  - Max results: {settings.rag.max_results}")
    print(f"  - Diversification mode: {settings.rag.diversification_mode}")
    print(f"  - Entity content boost: {settings.rag.entity_content_boost}")
    print(f"  - Entity title boost: {settings.rag.entity_title_boost}")
    print()

    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()

    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    retrieval_service = RetrievalService(settings)

    # Test the Apple query
    query = "has 8th light worked with apple?"
    print(f"🔍 Query: '{query}'")
    print()

    # Get results using the current bot configuration
    results = await retrieval_service.retrieve_context(
        query, vector_store, embedding_service
    )

    print(f"📊 Retrieved {len(results)} results:")
    print()

    # Analyze results
    unique_docs = set()
    doc_chunk_counts = {}
    apple_count = 0

    for i, result in enumerate(results):
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        similarity = result.get("similarity", 0)
        original_sim = result.get("_original_similarity", similarity)
        entity_boost = result.get("_entity_boost", 0)
        matching_entities = result.get("_matching_entities", 0)

        # Track statistics
        unique_docs.add(file_name)
        doc_chunk_counts[file_name] = doc_chunk_counts.get(file_name, 0) + 1

        if "apple" in file_name.lower():
            apple_count += 1
            status = "🍎"
        else:
            status = "📄"

        # Display result
        display_name = file_name[:55] + "..." if len(file_name) > 55 else file_name
        boost_info = f" (boost: +{entity_boost:.2f}, entities: {matching_entities})" if entity_boost > 0 else ""

        print(f"{status} {i+1}. {display_name}")
        print(f"     Final: {similarity:.3f} | Original: {original_sim:.3f}{boost_info}")

    print()
    print(f"📈 Summary:")
    print(f"   - Apple documents: {apple_count}/{len(results)}")
    print(f"   - Unique documents: {len(unique_docs)}")
    print(f"   - Document distribution:")
    for doc_name, count in doc_chunk_counts.items():
        display_name = doc_name[:60] + "..." if len(doc_name) > 60 else doc_name
        print(f"     • {display_name}: {count} chunks")

    print()
    if apple_count > 0:
        print("✅ SUCCESS: Apple documents found with entity boosting!")
        print(f"✅ SUCCESS: Using {settings.rag.diversification_mode} diversification!")
    else:
        print("❌ ISSUE: No Apple documents found")

if __name__ == "__main__":
    asyncio.run(test_fixed_retrieval())
