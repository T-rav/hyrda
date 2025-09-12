#!/usr/bin/env python3
"""
Quick test of the new generic entity extraction approach
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from services.retrieval_service import RetrievalService
from config.settings import Settings

def test_entity_extraction():
    # Mock minimal settings
    os.environ.setdefault('SLACK_BOT_TOKEN', 'test')
    os.environ.setdefault('SLACK_APP_TOKEN', 'test')
    os.environ.setdefault('LLM_API_KEY', 'test')
    os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')

    settings = Settings()
    retrieval = RetrievalService(settings)

    test_queries = [
        "has 8th light worked with apple?",
        "Apple project details",
        "what projects did we do for Apple",
        "frontend engineering strategic design",
        "scaling experimentation automation"
    ]

    print("🔍 Testing Generic Entity Extraction")
    print("=" * 50)

    for query in test_queries:
        entities = retrieval._extract_entities_simple(query)
        print(f"Query: '{query}'")
        print(f"Entities: {sorted(entities)}")
        print()

if __name__ == "__main__":
    test_entity_extraction()
