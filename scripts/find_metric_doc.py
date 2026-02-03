#!/usr/bin/env python3
"""
Find a metric document by scanning.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def find_metric_doc():
    client = QdrantClient(
        host=os.getenv('VECTOR_HOST', 'localhost'),
        port=int(os.getenv('VECTOR_PORT', 6333)),
        api_key=os.getenv('VECTOR_API_KEY'),
        https=True if os.getenv('VECTOR_HOST') != 'localhost' else False
    )

    collection = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')

    print("=" * 100)
    print("FINDING METRIC DOCUMENTS")
    print("=" * 100)

    offset = None
    found_count = 0
    max_to_show = 5

    while found_count < max_to_show:
        points, offset = client.scroll(
            collection,
            limit=100,
            offset=offset,
            with_payload=True
        )

        if not points:
            break

        for point in points:
            source = point.payload.get('source', 'MISSING')
            if source == 'metric':
                found_count += 1
                print(f"\n{found_count}. Point ID: {point.id}")
                print(f"   Metadata keys: {list(point.payload.keys())}")
                print(f"   Full metadata:")
                for key, value in point.payload.items():
                    if key in ('page_content', 'text'):
                        print(f"      {key}: {str(value)[:150]}...")
                    else:
                        print(f"      {key}: {value}")

                if found_count >= max_to_show:
                    break

        if offset is None:
            break

    if found_count == 0:
        print("\n❌ No metric documents found")
    else:
        print(f"\n✅ Showed {found_count} metric documents")

    return 0


if __name__ == '__main__':
    try:
        sys.exit(find_metric_doc())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
