#!/usr/bin/env python3
"""
Vector Database Index Initialization

Initializes or recreates vector database indices with proper schemas.
Supports both Pinecone (dense vectors) and Elasticsearch (sparse search).
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "bot"))

# Load environment
from dotenv import load_dotenv
load_dotenv()


class IndexManager:
    """Manages vector database index initialization"""

    def __init__(self):
        self.api_key = os.getenv('VECTOR_API_KEY')
        self.index_name = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')
        self.environment = os.getenv('VECTOR_ENVIRONMENT', 'us-east-1')
        self.es_url = os.getenv('VECTOR_URL', 'http://localhost:9200')
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')

    def get_embedding_dimensions(self):
        """Get embedding dimensions based on model"""
        model_dims = {
            'text-embedding-3-small': 1536,
            'text-embedding-3-large': 3072,
            'text-embedding-ada-002': 1536,
        }
        return model_dims.get(self.embedding_model, 1536)

    async def init_pinecone(self, force_recreate=False):
        """Initialize Pinecone index"""
        try:
            from pinecone import Pinecone, ServerlessSpec

            if not self.api_key:
                print("❌ VECTOR_API_KEY not found in .env file")
                return False

            print("🔄 Initializing Pinecone index...")
            print(f"   Index: {self.index_name}")
            print(f"   Environment: {self.environment}")
            print(f"   Model: {self.embedding_model} ({self.get_embedding_dimensions()} dimensions)")

            pc = Pinecone(api_key=self.api_key)

            # Check if index exists
            existing_indexes = [idx.name for idx in pc.list_indexes()]
            index_exists = self.index_name in existing_indexes

            if index_exists:
                if force_recreate:
                    print(f"🗑️  Deleting existing index: {self.index_name}")
                    pc.delete_index(self.index_name)
                    index_exists = False
                else:
                    print(f"✅ Pinecone index '{self.index_name}' already exists")
                    return True

            if not index_exists:
                print(f"🔌 Creating Pinecone index: {self.index_name}")
                pc.create_index(
                    name=self.index_name,
                    dimension=self.get_embedding_dimensions(),
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.environment
                    )
                )

            print("✅ Pinecone index ready")
            return True

        except ImportError:
            print("❌ Pinecone package not installed. Run: pip install pinecone")
            return False
        except Exception as e:
            print(f"❌ Error initializing Pinecone: {e}")
            return False

    async def init_elasticsearch(self, force_recreate=False):
        """Initialize Elasticsearch indices"""
        try:
            from elasticsearch import AsyncElasticsearch

            print("🔄 Initializing Elasticsearch indices...")
            print(f"   URL: {self.es_url}")
            print(f"   Base name: {self.index_name}")

            client = AsyncElasticsearch(
                hosts=[self.es_url],
                verify_certs=False,
                ssl_show_warn=False
            )

            # Test connection
            if not await client.ping():
                print("❌ Cannot connect to Elasticsearch. Is it running?")
                print("   Start with: docker compose -f docker-compose.elasticsearch.yml up -d")
                return False

            # Define indices to create
            indices = {
                # Sparse index (BM25 text search) - this is what we actually use
                f"{self.index_name}_sparse": {
                    "mappings": {
                        "properties": {
                            "content": {"type": "text", "analyzer": "standard"},
                            "title": {"type": "text", "analyzer": "standard", "boost": 2.0},
                            "metadata": {"type": "object", "enabled": True},
                            "timestamp": {"type": "date"}
                        }
                    },
                    "settings": {
                        "index": {"number_of_shards": 1, "number_of_replicas": 0}
                    }
                }
            }

            for index_name, mapping in indices.items():
                exists = await client.indices.exists(index=index_name)

                if exists:
                    if force_recreate:
                        print(f"🗑️  Deleting existing index: {index_name}")
                        await client.indices.delete(index=index_name)
                        exists = False
                    else:
                        print(f"✅ Elasticsearch index '{index_name}' already exists")
                        continue

                if not exists:
                    index_type = "sparse (BM25)" if "_sparse" in index_name else "dense (vectors)"
                    print(f"🔌 Creating {index_type} index: {index_name}")
                    await client.indices.create(index=index_name, **mapping)

            await client.close()
            print("✅ Elasticsearch indices ready")
            return True

        except ImportError:
            print("❌ Elasticsearch package not installed. Run: pip install elasticsearch")
            return False
        except Exception as e:
            print(f"❌ Error initializing Elasticsearch: {e}")
            return False

    async def init_all(self, force_recreate=False):
        """Initialize all indices"""
        print("🚀 Vector Database Index Initialization")
        print("=" * 50)

        # Initialize Pinecone
        pinecone_success = await self.init_pinecone(force_recreate)

        print()  # Empty line

        # Initialize Elasticsearch
        elasticsearch_success = await self.init_elasticsearch(force_recreate)

        print()
        print("📋 Summary:")
        print(f"   Pinecone: {'✅ Ready' if pinecone_success else '❌ Failed'}")
        print(f"   Elasticsearch: {'✅ Ready' if elasticsearch_success else '❌ Failed'}")

        if pinecone_success and elasticsearch_success:
            print("\n🎉 All indices initialized successfully!")
            print("\n📋 Next steps:")
            print("  • Run ingestion: cd ingest && python main.py --folder-id YOUR_FOLDER_ID")
            print("  • Start bot: ./start_bot.sh")
            return True
        else:
            print("\n⚠️  Some indices failed to initialize")
            return False


async def main():
    """Main CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize vector database indices")
    parser.add_argument("--force", action="store_true",
                       help="Force recreate indices (deletes existing data)")
    parser.add_argument("--pinecone-only", action="store_true",
                       help="Initialize only Pinecone index")
    parser.add_argument("--elasticsearch-only", action="store_true",
                       help="Initialize only Elasticsearch indices")

    args = parser.parse_args()

    manager = IndexManager()

    if args.force:
        response = input("⚠️  This will delete all existing data. Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Operation cancelled")
            return

    try:
        if args.pinecone_only:
            success = await manager.init_pinecone(args.force)
        elif args.elasticsearch_only:
            success = await manager.init_elasticsearch(args.force)
        else:
            success = await manager.init_all(args.force)

        if not success:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
