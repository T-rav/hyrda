#!/usr/bin/env python3
"""
Delete all documents except google_drive and metric sources from Qdrant.

Keeps only:
- source='google_drive' (internal documents)
- source='metric' (metric data)

Deletes everything else (SEC filings, unknown sources, malformed docs, etc.)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def prune_vector_db():
    """Delete all documents except google_drive and metric sources."""
    client = QdrantClient(
        host=os.getenv("VECTOR_HOST", "localhost"),
        port=int(os.getenv("VECTOR_PORT", 6333)),
        api_key=os.getenv("VECTOR_API_KEY"),
        https=True if os.getenv("VECTOR_HOST") != "localhost" else False,
    )

    collection = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")

    print("=" * 100)
    print("PRUNE VECTOR DATABASE - KEEP ONLY GOOGLE DRIVE AND METRIC")
    print("=" * 100)

    # Get collection info
    info = client.get_collection(collection)
    print(f"\nTotal documents BEFORE pruning: {info.points_count}")

    # Find documents to delete (NOT google_drive or metric, OR malformed)
    print("\nScanning for documents to delete...")

    allowed_sources = {"google_drive", "metric"}
    to_delete = []
    to_keep_by_source = {}
    malformed_count = 0
    offset = None
    batch_size = 100
    scanned = 0

    while True:
        points, offset = client.scroll(
            collection, limit=batch_size, offset=offset, with_payload=True
        )

        if not points:
            break

        for point in points:
            source = point.payload.get("source", "MISSING")
            payload_keys = list(point.payload.keys())

            # Check if document is malformed (only has _id and _collection_name)
            # These documents have no actual content and cause false positives
            is_malformed = len(payload_keys) <= 2 and all(
                key.startswith("_") for key in payload_keys
            )

            if is_malformed:
                # Delete malformed documents
                to_delete.append(point.id)
                malformed_count += 1
                if malformed_count <= 10:
                    print(f"  🚨 Malformed document: {point.id} (keys: {payload_keys})")
            elif source in allowed_sources:
                # Keep this document
                to_keep_by_source[source] = to_keep_by_source.get(source, 0) + 1
            else:
                # Delete this document (wrong source)
                to_delete.append(point.id)

            scanned += 1

        if offset is None:
            break

        if scanned % 10000 == 0:
            print(
                f"  Scanned {scanned} documents... (found {len(to_delete)} to delete)"
            )

    print(f"\n✅ Scanned {scanned} total documents")

    print("\nDocuments to KEEP:")
    for source, count in sorted(to_keep_by_source.items()):
        print(f"  {source}: {count} documents")

    print(f"\nDocuments to DELETE: {len(to_delete)}")
    if malformed_count > 0:
        print(
            f"  - {malformed_count} malformed documents (only _id and _collection_name)"
        )
        print(f"  - {len(to_delete) - malformed_count} wrong source documents")
    print(f"  ({len(to_delete) / scanned * 100:.1f}% of total)")

    if not to_delete:
        print("\n✅ No documents to delete - database already clean!")
        return 0

    response = input(f"\nDelete {len(to_delete)} documents? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return 1

    # Delete in batches
    print(f"\nDeleting {len(to_delete)} documents...")
    batch_size = 100
    for i in range(0, len(to_delete), batch_size):
        batch = to_delete[i : i + batch_size]
        client.delete(collection_name=collection, points_selector=batch)
        print(
            f"  Deleted batch {i // batch_size + 1}/{(len(to_delete) + batch_size - 1) // batch_size}"
        )

    # Get updated count
    info = client.get_collection(collection)
    print("\n✅ Pruning complete!")
    print(f"Total documents AFTER pruning: {info.points_count}")
    print(f"Deleted: {len(to_delete)} documents")
    print(f"Kept: {info.points_count} documents (google_drive + metric only)")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(prune_vector_db())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
