#!/usr/bin/env python3
"""
Test configurable entity boost settings
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

async def test_boost_settings():
    """Test different boost settings"""

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

    print("🎯 Testing Configurable Entity Boost Settings")
    print("=" * 55)

    # Test different boost configurations
    boost_configs = [
        {"content": 0.05, "title": 0.1, "name": "Default (5%/10%)"},
        {"content": 0.1, "title": 0.2, "name": "Higher (10%/20%)"},
        {"content": 0.02, "title": 0.05, "name": "Lower (2%/5%)"},
        {"content": 0.15, "title": 0.3, "name": "Aggressive (15%/30%)"},
    ]

    query = "has 8th light worked with apple?"

    for config in boost_configs:
        print(f"🔧 Testing: {config['name']}")
        print("-" * 40)

        # Override environment settings
        os.environ["RAG_ENTITY_CONTENT_BOOST"] = str(config["content"])
        os.environ["RAG_ENTITY_TITLE_BOOST"] = str(config["title"])

        # Create fresh settings object
        settings = Settings()
        settings.rag.enable_hybrid_search = True

        print(f"   Content boost: {settings.rag.entity_content_boost}")
        print(f"   Title boost: {settings.rag.entity_title_boost}")

        # Initialize services
        vector_store = create_vector_store(settings.vector)
        await vector_store.initialize()

        embedding_service = create_embedding_provider(settings.embedding, settings.llm)
        retrieval_service = RetrievalService(settings)

        # Get results
        results = await retrieval_service.retrieve_context(
            query, vector_store, embedding_service
        )

        # Show Apple documents with boost details
        apple_results = []
        for result in results:
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            if "apple" in file_name.lower():
                similarity = result.get("similarity", 0)
                original_sim = result.get("_original_similarity", similarity)
                entity_boost = result.get("_entity_boost", 0)
                matching_entities = result.get("_matching_entities", 0)

                apple_results.append({
                    'name': file_name,
                    'final_sim': similarity,
                    'original_sim': original_sim,
                    'boost': entity_boost,
                    'entities': matching_entities
                })

        print(f"   🍎 Apple documents found: {len(apple_results)}")
        for apple in apple_results:
            print(f"      - {apple['name'][:50]}...")
            print(f"        Final: {apple['final_sim']:.3f} | Original: {apple['original_sim']:.3f} | Boost: +{apple['boost']:.3f}")

        print()

if __name__ == "__main__":
    asyncio.run(test_boost_settings())
