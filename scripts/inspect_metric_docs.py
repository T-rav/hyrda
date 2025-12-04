#!/usr/bin/env python3
"""
Check metadata structure of metric documents.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


def inspect_metric_docs():
    """Check metadata structure of metric documents."""
    client = QdrantClient(
        host=os.getenv("VECTOR_HOST", "localhost"),
        port=int(os.getenv("VECTOR_PORT", 6333)),
        api_key=os.getenv("VECTOR_API_KEY"),
        https=True if os.getenv("VECTOR_HOST") != "localhost" else False,
    )

    collection = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")

    print("=" * 100)
    print("METRIC DOCUMENT METADATA STRUCTURE")
    print("=" * 100)

    # Get metric documents
    points, _ = client.scroll(
        collection,
        scroll_filter=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value="metric"))]
        ),
        limit=10,
        with_payload=True,
    )

    print(f"\nFound {len(points)} metric documents (showing first 10):")

    for i, point in enumerate(points, 1):
        metadata = point.payload
        print(f"\n{i}. Point ID: {point.id}")
        print(f"   Metadata keys: {list(metadata.keys())}")
        print(f"   source: {metadata.get('source')}")
        print(f"   file_name: {metadata.get('file_name', '❌ MISSING')}")
        print("   Full metadata:")
        for key, value in metadata.items():
            if key == "page_content" or key == "text":
                print(f"      {key}: {str(value)[:100]}...")
            else:
                print(f"      {key}: {value}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(inspect_metric_docs())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
