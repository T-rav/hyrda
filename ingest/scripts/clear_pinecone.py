#!/usr/bin/env python3
"""
Clear Pinecone Vector Database

Simple script to delete all vectors from your Pinecone index.
Useful for clean re-ingestion or testing.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv
load_dotenv()


def clear_pinecone():
    """Clear all vectors from Pinecone index"""
    try:
        from pinecone import Pinecone

        # Get settings from environment
        api_key = os.getenv('VECTOR_API_KEY')
        index_name = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')

        if not api_key:
            print("❌ VECTOR_API_KEY not found in .env file")
            return False

        print(f"🔄 Connecting to Pinecone...")
        print(f"   Index: {index_name}")

        # Initialize Pinecone
        pc = Pinecone(api_key=api_key)

        # Get index
        if index_name not in [idx.name for idx in pc.list_indexes()]:
            print(f"⚠️  Index '{index_name}' does not exist")
            return False

        index = pc.Index(index_name)

        # Get index stats before clearing
        stats = index.describe_index_stats()
        total_vectors = stats.get('total_vector_count', 0)

        if total_vectors == 0:
            print("✅ Index is already empty")
            return True

        print(f"📊 Found {total_vectors} vectors in index")

        # Confirm deletion
        response = input(f"⚠️  Are you sure you want to delete all {total_vectors} vectors? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Operation cancelled")
            return False

        print("🗑️  Deleting all vectors...")

        # Delete all vectors
        index.delete(delete_all=True)

        print("✅ Successfully cleared Pinecone index!")
        print("\n📋 Next steps:")
        print("  • Re-run ingestion: cd ingest && python main.py --folder-id YOUR_FOLDER_ID")

        return True

    except ImportError:
        print("❌ Pinecone package not installed. Run: pip install pinecone")
        return False
    except Exception as e:
        print(f"❌ Error clearing Pinecone: {e}")
        return False


def main():
    """Main CLI entry point"""
    print("🧹 Pinecone Vector Database Cleaner")
    print("=" * 40)

    success = clear_pinecone()

    if not success:
        sys.exit(1)

    print("\n🎉 Cleanup completed successfully!")


if __name__ == "__main__":
    main()
