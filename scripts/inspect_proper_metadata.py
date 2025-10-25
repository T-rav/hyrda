#!/usr/bin/env python3
"""
Check what proper document metadata looks like in Qdrant.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def inspect_proper_metadata():
    """Check metadata structure of proper documents."""
    client = QdrantClient(
        host=os.getenv('VECTOR_HOST', 'localhost'),
        port=int(os.getenv('VECTOR_PORT', 6333)),
        api_key=os.getenv('VECTOR_API_KEY'),
        https=True if os.getenv('VECTOR_HOST') != 'localhost' else False
    )

    collection = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')

    print("=" * 100)
    print("PROPER DOCUMENT METADATA STRUCTURE")
    print("=" * 100)

    # Get a few random documents
    points, _ = client.scroll(collection, limit=10, with_payload=True)

    print(f"\nChecking {len(points)} sample documents:")

    for i, point in enumerate(points, 1):
        metadata = point.payload
        print(f"\n{i}. Point ID: {point.id}")
        print(f"   Metadata keys: {list(metadata.keys())}")
        print(f"   file_name: {metadata.get('file_name', '❌ MISSING')}")
        print(f"   source: {metadata.get('source', '❌ MISSING')}")
        print(f"   page_content preview: {metadata.get('page_content', '')[:100]}...")

        # Check if this is a malformed document
        has_file_name = 'file_name' in metadata
        has_source = 'source' in metadata
        has_content = 'page_content' in metadata

        if not has_file_name or not has_source or not has_content:
            print(f"   ⚠️  MALFORMED: missing_file_name={not has_file_name}, missing_source={not has_source}, missing_content={not has_content}")

    # Now specifically check the culprit document
    print("\n" + "=" * 100)
    print("CHECKING CULPRIT DOCUMENT")
    print("=" * 100)

    culprit_id = "f74b4986-194a-53b9-8b96-827577675866"
    try:
        culprit = client.retrieve(collection, ids=[culprit_id])
        if culprit:
            doc = culprit[0]
            print(f"\nCulprit Document ID: {doc.id}")
            print(f"Full payload: {doc.payload}")
            print(f"Payload keys: {list(doc.payload.keys())}")
    except Exception as e:
        print(f"\n❌ Could not retrieve culprit document: {e}")

    return 0


if __name__ == '__main__':
    try:
        sys.exit(inspect_proper_metadata())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
