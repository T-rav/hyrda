"""
Elasticsearch Index Migration System

Ensures required indices exist with proper mappings before RAG initialization.
"""
import logging
from typing import Dict, Any
try:
    from elasticsearch import AsyncElasticsearch
    from elasticsearch.exceptions import RequestError
except ImportError:
    raise ImportError(
        "elasticsearch package not installed. Run: pip install elasticsearch"
    )

logger = logging.getLogger(__name__)


class ElasticsearchMigrations:
    """Handles Elasticsearch index migrations and initialization"""

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    def get_dense_index_mapping(self, dims: int = 3072) -> Dict[str, Any]:
        """Get mapping for dense vector index"""
        return {
            "mappings": {
                "properties": {
                    "content": {"type": "text", "analyzer": "standard"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dims,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "metadata": {"type": "object", "enabled": True},
                    "timestamp": {"type": "date"},
                }
            },
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            },
        }

    def get_sparse_index_mapping(self) -> Dict[str, Any]:
        """Get mapping for sparse/BM25 index (no embeddings)"""
        return {
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "metadata": {"type": "object", "enabled": True},
                    "timestamp": {"type": "date"},
                }
            },
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            },
        }

    async def ensure_index_exists(self, index_name: str, mapping: Dict[str, Any]) -> bool:
        """Ensure index exists with proper mapping"""
        try:
            # Check if index exists
            exists = await self.client.indices.exists(index=index_name)

            if exists:
                logger.info(f"✅ Index '{index_name}' already exists")
                return True

            # Create index
            logger.info(f"🔨 Creating index '{index_name}'...")
            await self.client.indices.create(index=index_name, **mapping)
            logger.info(f"✅ Index '{index_name}' created successfully")
            return True

        except RequestError as e:
            logger.error(f"❌ Failed to create index '{index_name}': {e}")
            if hasattr(e, 'error'):
                logger.error(f"   Error: {e.error}")
            if hasattr(e, 'info'):
                logger.error(f"   Info: {e.info}")
            if hasattr(e, 'body'):
                logger.error(f"   Body: {e.body}")
            logger.error(f"   Status code: {e.status_code if hasattr(e, 'status_code') else 'unknown'}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error creating index '{index_name}': {type(e).__name__}: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False

    async def run_migrations(self, collection_name: str, embedding_dims: int = 3072) -> bool:
        """Run all required migrations for RAG system"""
        logger.info("🔄 Running Elasticsearch migrations...")

        # Test connection first
        try:
            ping_result = await self.client.ping()
            logger.info(f"✅ Elasticsearch connection verified: {ping_result}")

            # Get cluster info for debugging
            try:
                cluster_info = await self.client.info()
                logger.info(f"   Cluster: {cluster_info.get('cluster_name', 'unknown')}")
                logger.info(f"   Version: {cluster_info.get('version', {}).get('number', 'unknown')}")
            except Exception as info_e:
                logger.warning(f"   Could not get cluster info: {info_e}")

        except Exception as e:
            logger.error(f"❌ Elasticsearch connection failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False

        # Create indices (ensure valid Elasticsearch index names)
        # Elasticsearch index names must be lowercase and cannot contain certain characters
        dense_index = collection_name.lower().replace('_', '-')
        sparse_index = f"{dense_index}-sparse"

        logger.info(f"   Dense index name: {dense_index}")
        logger.info(f"   Sparse index name: {sparse_index}")

        results = []

        # Create dense index (for regular vector operations)
        dense_mapping = self.get_dense_index_mapping(embedding_dims)
        dense_ok = await self.ensure_index_exists(dense_index, dense_mapping)
        results.append(dense_ok)

        # Create sparse index (for BM25/hybrid operations)
        sparse_mapping = self.get_sparse_index_mapping()
        sparse_ok = await self.ensure_index_exists(sparse_index, sparse_mapping)
        results.append(sparse_ok)

        if all(results):
            logger.info("✅ All Elasticsearch migrations completed successfully")
            return True
        else:
            logger.error("❌ Some Elasticsearch migrations failed")
            return False


async def run_elasticsearch_migrations(
    elasticsearch_url: str,
    collection_name: str,
    embedding_dims: int = 3072
) -> bool:
    """Convenience function to run migrations"""
    client = AsyncElasticsearch(
        hosts=[elasticsearch_url],
        verify_certs=False,
        ssl_show_warn=False,
    )

    try:
        migrations = ElasticsearchMigrations(client)
        return await migrations.run_migrations(collection_name, embedding_dims)
    finally:
        await client.close()
