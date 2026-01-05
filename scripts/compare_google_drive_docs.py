#!/usr/bin/env python3
"""
Analyze google_drive documents to understand the difference between environments.
"""
import os
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def analyze_google_drive_docs():
    """Analyze google_drive documents."""
    client = QdrantClient(
        host=os.getenv('VECTOR_HOST', 'localhost'),
        port=int(os.getenv('VECTOR_PORT', 6333)),
        api_key=os.getenv('VECTOR_API_KEY'),
        https=True if os.getenv('VECTOR_HOST') != 'localhost' else False
    )

    collection = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')

    print("=" * 100)
    print("GOOGLE DRIVE DOCUMENT ANALYSIS")
    print("=" * 100)

    offset = None
    batch_size = 100
    scanned = 0

    file_names = []
    unique_files = set()
    chunk_counts = Counter()
    missing_file_name = 0

    print("\nScanning google_drive documents...")

    while True:
        points, offset = client.scroll(
            collection,
            limit=batch_size,
            offset=offset,
            with_payload=True
        )

        if not points:
            break

        for point in points:
            source = point.payload.get('source', 'MISSING')

            if source == 'google_drive':
                file_name = point.payload.get('file_name')

                if not file_name:
                    missing_file_name += 1
                    if missing_file_name <= 5:
                        print(f"  ⚠️  google_drive doc without file_name: {point.id}")
                        print(f"      Keys: {list(point.payload.keys())}")
                else:
                    file_names.append(file_name)
                    unique_files.add(file_name)
                    chunk_counts[file_name] += 1

                scanned += 1

        if offset is None:
            break

        if scanned % 1000 == 0:
            print(f"  Scanned {scanned} google_drive documents...")

    print(f"\n✅ Scanned {scanned} google_drive documents")
    print(f"\nUnique files: {len(unique_files)}")
    print(f"Total chunks: {len(file_names)}")
    print(f"Documents without file_name: {missing_file_name}")

    # Show top files by chunk count
    print("\nTop 20 files by chunk count:")
    for file_name, count in chunk_counts.most_common(20):
        print(f"  {count:4d} chunks: {file_name}")

    # Show files with only 1-2 chunks (might be malformed or incomplete)
    small_files = [(name, count) for name, count in chunk_counts.items() if count <= 2]
    if small_files:
        print(f"\nFiles with 1-2 chunks only ({len(small_files)} files):")
        for file_name, count in sorted(small_files, key=lambda x: x[1])[:20]:
            print(f"  {count} chunks: {file_name}")

    return 0


if __name__ == '__main__':
    try:
        sys.exit(analyze_google_drive_docs())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
