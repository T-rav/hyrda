#!/usr/bin/env python3
"""
Count documents by source type in Qdrant.
"""

import os
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def count_sources():
    """Count documents by source."""
    client = QdrantClient(
        host=os.getenv("VECTOR_HOST", "localhost"),
        port=int(os.getenv("VECTOR_PORT", 6333)),
        api_key=os.getenv("VECTOR_API_KEY"),
        https=True if os.getenv("VECTOR_HOST") != "localhost" else False,
    )

    collection = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")

    print("=" * 100)
    print("DOCUMENT SOURCE ANALYSIS")
    print("=" * 100)

    # Get collection info
    info = client.get_collection(collection)
    print(f"\nTotal documents: {info.points_count}")

    # Count by source
    sources = Counter()
    offset = None
    batch_size = 100

    print("\nScanning documents...")
    scanned = 0

    while True:
        points, offset = client.scroll(
            collection, limit=batch_size, offset=offset, with_payload=True
        )

        if not points:
            break

        for point in points:
            source = point.payload.get("source", "MISSING")
            sources[source] += 1
            scanned += 1

        if offset is None:
            break

        if scanned % 1000 == 0:
            print(f"  Scanned {scanned} documents...")

    print(f"\n✅ Scanned {scanned} total documents")
    print("\nDocument sources:")
    for source, count in sources.most_common():
        percentage = (count / scanned * 100) if scanned > 0 else 0
        print(f"  {source}: {count} documents ({percentage:.1f}%)")

    # Check for documents with minimal metadata (like the culprit)
    print("\n" + "=" * 100)
    print("CHECKING FOR MALFORMED DOCUMENTS")
    print("=" * 100)

    malformed = []
    offset = None

    while True:
        points, offset = client.scroll(
            collection, limit=batch_size, offset=offset, with_payload=True
        )

        if not points:
            break

        for point in points:
            keys = list(point.payload.keys())
            # Check if document has suspiciously few metadata keys
            if len(keys) <= 2:  # Only _id and _collection_name, or similar
                malformed.append(
                    {"id": point.id, "keys": keys, "payload": point.payload}
                )

        if offset is None:
            break

    if malformed:
        print(f"\n🚨 Found {len(malformed)} malformed documents with minimal metadata:")
        for doc in malformed[:10]:  # Show first 10
            print(f"  ID: {doc['id']}")
            print(f"  Keys: {doc['keys']}")
            print(f"  Payload: {doc['payload']}")
            print()
    else:
        print("\n✅ No malformed documents found")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(count_sources())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
