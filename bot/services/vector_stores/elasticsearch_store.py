"""
Elasticsearch Vector Store Implementation

Handles Elasticsearch-specific vector database operations including BM25 search.
"""

import hashlib
import logging
from typing import Any

from .base import VectorStore

logger = logging.getLogger(__name__)


class ElasticsearchVectorStore(VectorStore):
    """Elasticsearch vector store implementation using dense_vector fields"""

    def __init__(self, settings):
        super().__init__(settings)
        self.client = None
        self.index_name = self.collection_name

    async def initialize(self):
        """Initialize Elasticsearch client and index"""
        try:
            from elasticsearch import AsyncElasticsearch  # noqa: PLC0415

            # Parse URL for connection
            self.client = AsyncElasticsearch(
                hosts=[self.settings.url],
                verify_certs=False,  # For local development
                ssl_show_warn=False,
            )

            # Test connection
            await self.client.ping()

            # Create index with vector mapping if it doesn't exist
            index_exists = await self.client.indices.exists(index=self.index_name)
            if not index_exists:
                mapping = self._get_index_mapping()
                await self.client.indices.create(index=self.index_name, **mapping)

            logger.info(f"✅ Elasticsearch initialized with index: {self.index_name}")

        except ImportError:
            raise ImportError(
                "elasticsearch package not installed. Run: pip install elasticsearch"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch: {e}")
            raise

    def _get_index_mapping(self) -> dict:
        """Get Elasticsearch index mapping configuration"""
        return {
            "mappings": {
                "properties": {
                    "content": {"type": "text", "analyzer": "standard"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 3072,  # OpenAI text-embedding-3-large dimension
                        "index": True,
                        "similarity": "cosine",
                    },
                    "metadata": {"type": "object", "enabled": True},
                    "timestamp": {"type": "date"},
                }
            },
            "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        }

    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Add documents to Elasticsearch"""
        try:
            from datetime import datetime  # noqa: PLC0415

            # Prepare documents for bulk indexing
            documents = []
            is_sparse_index = "_sparse" in self.index_name

            for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
                text_hash = hashlib.md5(
                    text.encode(), usedforsecurity=False
                ).hexdigest()
                doc_id = f"doc_{text_hash}_{i}"

                doc_metadata = metadata[i] if metadata else {}

                if is_sparse_index:
                    # Sparse index: no embeddings, extract title from metadata
                    doc = {
                        "content": text,
                        "title": doc_metadata.get("title", ""),
                        "metadata": doc_metadata,
                        "timestamp": datetime.utcnow(),
                    }
                else:
                    # Dense index: include embeddings
                    doc = {
                        "content": text,
                        "embedding": embedding,
                        "metadata": doc_metadata,
                        "timestamp": datetime.utcnow(),
                    }

                # Bulk API format
                documents.extend(
                    [{"index": {"_index": self.index_name, "_id": doc_id}}, doc]
                )

            if self.client is None:
                raise RuntimeError("Elasticsearch client not initialized")

            # Bulk index documents
            response = await self.client.bulk(operations=documents)

            # Check for errors
            if response.get("errors"):
                errors = [
                    item
                    for item in response["items"]
                    if "error" in item.get("index", {})
                ]
                if errors:
                    logger.error(f"Bulk indexing errors: {errors}")
                    raise RuntimeError(f"Failed to index some documents: {errors}")

            logger.info(f"✅ Added {len(texts)} documents to Elasticsearch")

        except Exception as e:
            logger.error(f"Failed to add documents to Elasticsearch: {e}")
            raise

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search Elasticsearch for similar documents using vector similarity"""
        try:
            if self.client is None:
                raise RuntimeError("Elasticsearch client not initialized")

            # Use script_score query for vector similarity
            query = {
                "query": {
                    "script_score": {
                        "query": {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                            "params": {"query_vector": query_embedding},
                        },
                    }
                },
                "size": limit,
                "_source": ["content", "metadata", "timestamp"],
            }

            response = await self.client.search(index=self.index_name, **query)

            documents = []
            for hit in response["hits"]["hits"]:
                # Convert Elasticsearch score to similarity (0-1 range)
                raw_score = hit["_score"]
                similarity = raw_score - 1.0  # Convert back to cosine similarity
                similarity = (similarity + 1) / 2  # Normalize to (0, 1)

                if similarity >= similarity_threshold:
                    documents.append(
                        {
                            "content": hit["_source"]["content"],
                            "similarity": similarity,
                            "metadata": hit["_source"].get("metadata", {}),
                            "id": hit["_id"],
                        }
                    )

            logger.debug(
                f"Found {len(documents)} documents above similarity threshold {similarity_threshold}"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to search Elasticsearch: {e}")
            return []

    async def bm25_search(
        self,
        query: str,
        limit: int = 200,
        field_boosts: dict[str, float] | None = None,
        similarity_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """BM25 sparse retrieval for hybrid search"""
        try:
            if self.client is None:
                raise RuntimeError("Elasticsearch client not initialized")

            # Default field boosts: title 8x, content 1x
            boosts = field_boosts or {"title": 8.0, "content": 1.0}

            # Build boosted fields list
            boosted_fields = []
            for field, boost in boosts.items():
                boosted_fields.append(f"{field}^{boost}")

            # Multi-match query with field boosting
            es_query = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": boosted_fields,
                        "type": "most_fields",
                    }
                },
                "size": limit,
                "_source": ["content", "metadata", "timestamp"],
            }

            response = await self.client.search(index=self.index_name, **es_query)

            documents = []
            for hit in response["hits"]["hits"]:
                # Use Elasticsearch score as similarity
                similarity = hit["_score"] / 10.0  # Normalize ES score

                if similarity >= similarity_threshold:
                    documents.append(
                        {
                            "content": hit["_source"]["content"],
                            "similarity": similarity,
                            "metadata": hit["_source"].get("metadata", {}),
                            "id": hit["_id"],
                        }
                    )

            logger.debug(f"BM25 search returned {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    async def delete_documents(self, document_ids: list[str]):
        """Delete documents from Elasticsearch"""
        try:
            if self.client is None:
                raise RuntimeError("Elasticsearch client not initialized")

            # Prepare bulk delete operations
            delete_ops = []
            for doc_id in document_ids:
                delete_ops.append(
                    {"delete": {"_index": self.index_name, "_id": doc_id}}
                )

            response = await self.client.bulk(operations=delete_ops)

            # Check for errors
            if response.get("errors"):
                errors = [
                    item
                    for item in response["items"]
                    if "error" in item.get("delete", {})
                ]
                if errors:
                    logger.warning(f"Some documents could not be deleted: {errors}")

            logger.info(f"✅ Deleted {len(document_ids)} documents from Elasticsearch")

        except Exception as e:
            logger.error(f"Failed to delete documents from Elasticsearch: {e}")
            raise

    async def close(self):
        """Clean up Elasticsearch resources"""
        if self.client:
            await self.client.close()
            logger.debug("Elasticsearch connection closed")

    async def get_stats(self) -> dict[str, Any]:
        """Get Elasticsearch index statistics"""
        try:
            if self.client is None:
                return {"error": "Client not initialized"}

            stats = await self.client.indices.stats(index=self.index_name)
            index_stats = stats["indices"].get(self.index_name, {})

            return {
                "document_count": index_stats.get("total", {})
                .get("docs", {})
                .get("count", 0),
                "store_size": index_stats.get("total", {})
                .get("store", {})
                .get("size_in_bytes", 0),
                "index_name": self.index_name,
            }
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch stats: {e}")
            return {"error": str(e)}
