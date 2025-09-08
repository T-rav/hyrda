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
                    # Sparse index: no embeddings
                    doc = {
                        "content": text,
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
        query_text: str = "",
    ) -> list[dict[str, Any]]:
        """Search Elasticsearch using traditional BM25 boosted by vector similarity"""
        try:
            if self.client is None:
                raise RuntimeError("Elasticsearch client not initialized")

            if query_text:
                # Start with pure BM25 search - no vector complications
                query = {
                    "query": {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["content", "metadata.file_name^2.0"],
                            "type": "most_fields",
                        }
                    },
                    "size": limit,
                    "_source": ["content", "metadata", "timestamp"],
                }
            else:
                # Fallback to pure vector search if no query text provided
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

            # Log the actual query being sent to Elasticsearch (without vector data)
            query_copy = query.copy()
            if (
                "query" in query_copy
                and "script_score" in query_copy["query"]
                and "script" in query_copy["query"]["script_score"]
                and "params" in query_copy["query"]["script_score"]["script"]
            ):
                query_copy["query"]["script_score"]["script"]["params"] = {
                    "query_vector": "[VECTOR_HIDDEN]",
                    "vector_boost": query["query"]["script_score"]["script"][
                        "params"
                    ].get("vector_boost", "N/A"),
                }
            logger.info(f"🔍 Elasticsearch query for '{query_text}': {query_copy}")

            # Get more results initially for diversification
            diverse_limit = 50  # Fixed higher limit to find diverse documents
            diverse_query = query.copy()
            diverse_query["size"] = diverse_limit

            response = await self.client.search(index=self.index_name, **diverse_query)

            # Process all hits first
            all_documents = []
            max_score = (
                response["hits"]["max_score"] or 1.0
            )  # Get max score for normalization

            for hit in response["hits"]["hits"]:
                # Use raw Elasticsearch score (combines BM25 + vector boost)
                raw_score = hit["_score"]

                if query_text:
                    # For BM25: normalize against max score to get relative relevance
                    # This gives us a 0.0-1.0 range where 1.0 is the best match in this result set
                    similarity = raw_score / max_score

                    # Apply stronger curve and scaling to match Pinecone's 0.7-0.95 range
                    # This creates more spread like cosine similarity scores
                    similarity = similarity**1.5  # Stronger power curve
                    similarity = 0.6 + (similarity * 0.35)  # Scale to 0.6-0.95 range
                else:
                    # For pure vector search, convert to similarity
                    similarity = raw_score - 1.0  # Convert back to cosine similarity
                    similarity = (similarity + 1) / 2  # Normalize to (0, 1)

                if similarity >= similarity_threshold:
                    all_documents.append(
                        {
                            "content": hit["_source"]["content"],
                            "similarity": similarity,
                            "metadata": hit["_source"].get("metadata", {}),
                            "id": hit["_id"],
                            "search_type": "bm25_vector_boost"
                            if query_text
                            else "pure_vector",
                            "raw_score": raw_score,  # Keep raw score for debugging
                        }
                    )

            # Apply diversification to ensure variety across documents
            documents = self._diversify_results(all_documents, limit)

            search_type = "BM25 + vector boost" if query_text else "pure vector"
            logger.debug(
                f"Found {len(documents)} documents using {search_type} (threshold: {similarity_threshold})"
            )

            # Log scores for debugging
            if documents:
                score_info = [
                    f"{d.get('metadata', {}).get('file_name', 'Unknown')}: raw={d.get('raw_score', 'N/A'):.2f}, rel={d['similarity']:.1%}"
                    for d in documents[:3]
                ]
                logger.debug(
                    f"Score details (max_score={max_score:.2f}): {'; '.join(score_info)}"
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

            # Default field boosts: file_name 4x, content 1x
            boosts = field_boosts or {"metadata.file_name": 4.0, "content": 1.0}

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

            # Get more results initially for diversification
            diverse_limit = 50  # Fixed higher limit to find diverse documents
            diverse_es_query = es_query.copy()
            diverse_es_query["size"] = diverse_limit

            response = await self.client.search(
                index=self.index_name, **diverse_es_query
            )

            all_documents = []
            max_score = (
                response["hits"]["max_score"] or 1.0
            )  # Get max score for normalization

            for hit in response["hits"]["hits"]:
                # Use same improved scoring as main search method
                raw_score = hit["_score"]
                similarity = raw_score / max_score
                similarity = similarity**1.5  # Stronger power curve to spread scores
                similarity = 0.6 + (similarity * 0.35)  # Scale to 0.6-0.95 range

                if similarity >= similarity_threshold:
                    all_documents.append(
                        {
                            "content": hit["_source"]["content"],
                            "similarity": similarity,
                            "metadata": hit["_source"].get("metadata", {}),
                            "id": hit["_id"],
                            "raw_score": raw_score,
                        }
                    )

            # Apply diversification
            documents = self._diversify_results(all_documents, limit)

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

    def _diversify_results(self, documents: list[dict], limit: int) -> list[dict]:
        """
        Diversify results to ensure variety across different documents.
        Uses a round-robin approach to select chunks from different files.
        """
        if not documents or limit <= 0:
            return []

        # Group documents by file_name
        file_groups = {}
        for doc in documents:
            file_name = doc.get("metadata", {}).get("file_name", "unknown")
            if file_name not in file_groups:
                file_groups[file_name] = []
            file_groups[file_name].append(doc)

        # Sort each group by similarity (highest first)
        for _file_name, docs in file_groups.items():
            docs.sort(key=lambda x: x["similarity"], reverse=True)

        # Use round-robin to select diverse results
        diversified = []
        file_names = list(file_groups.keys())
        file_indices = dict.fromkeys(
            file_names, 0
        )  # Track position in each file's chunks

        # Round-robin selection with max 2 chunks per file in top results
        rounds = 0
        max_per_file_per_round = 2  # Allow up to 2 chunks per file per round

        while (
            len(diversified) < limit and rounds < 5
        ):  # Max 5 rounds to prevent infinite loop
            added_this_round = False

            for file_name in file_names:
                if len(diversified) >= limit:
                    break

                file_docs = file_groups[file_name]
                start_idx = file_indices[file_name]

                # Add up to max_per_file_per_round chunks from this file
                for chunks_added, i in enumerate(range(start_idx, len(file_docs))):
                    if (
                        len(diversified) >= limit
                        or chunks_added >= max_per_file_per_round
                    ):
                        break

                    diversified.append(file_docs[i])
                    added_this_round = True
                    file_indices[file_name] = i + 1

            if not added_this_round:
                break  # No more documents to add

            rounds += 1

        logger.debug(
            f"Diversified {len(documents)} results to {len(diversified)} across {len(file_groups)} files"
        )
        return diversified

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
