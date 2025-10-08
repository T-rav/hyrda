"""
Pinecone Vector Store Implementation

Handles Pinecone-specific vector database operations.
"""

import asyncio
import hashlib
import logging
from typing import Any

from .base import VectorStore

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

logger = logging.getLogger(__name__)


class PineconeVectorStore(VectorStore):
    """Pinecone vector store implementation for dense retrieval"""

    def __init__(self, settings):
        super().__init__(settings)
        self.index = None

    async def initialize(self):
        """Initialize Pinecone client and index"""
        try:
            if Pinecone is None:
                raise ImportError(
                    "pinecone package is required for Pinecone vector store"
                )

            if not self.settings.api_key:
                raise ValueError("Pinecone API key is required")

            # Initialize Pinecone client (v3.x API)
            pc = Pinecone(api_key=self.settings.api_key.get_secret_value())

            # Connect to existing index
            self.index = pc.Index(self.collection_name)

            logger.info(f"✅ Pinecone initialized with index: {self.collection_name}")

        except ImportError:
            raise ImportError(
                "pinecone package not installed. Run: pip install pinecone"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Add documents to Pinecone with enhanced metadata"""
        try:
            vectors = []
            for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
                text_hash = hashlib.md5(
                    text.encode(), usedforsecurity=False
                ).hexdigest()
                doc_id = f"doc_{text_hash}_{i}"

                doc_metadata = metadata[i] if metadata else {}

                # Store enhanced text with title injection
                doc_metadata["text"] = text

                vectors.append(
                    {"id": doc_id, "values": embedding, "metadata": doc_metadata}
                )

            # Upsert in batches
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")

            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                await asyncio.get_event_loop().run_in_executor(
                    None, self.index.upsert, batch
                )

            logger.info(f"✅ Added {len(texts)} documents to Pinecone")

        except Exception as e:
            logger.error(f"Failed to add documents to Pinecone: {e}")
            raise

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 100,  # Higher default for better retrieval
        similarity_threshold: float = 0.0,  # No threshold for intermediate results
        filter: dict[str, Any] | None = None,
        query_text: str = "",  # Ignored for Pinecone (compatibility with Elasticsearch)
    ) -> list[dict[str, Any]]:
        """Search Pinecone for similar documents across all namespaces"""
        try:
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")

            # Query BOTH default namespace and metric namespace
            namespaces = ["", "metric"]  # Default namespace and metric namespace
            all_documents = []

            for namespace in namespaces:
                # Run query in executor to avoid blocking
                query_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace: self.index.query(
                        vector=query_embedding,
                        top_k=limit,
                        include_metadata=True,
                        include_values=False,
                        filter=filter,
                        namespace=ns,
                    ),
                )

                for match in query_result.matches:
                    if match.score >= similarity_threshold:
                        all_documents.append(
                            {
                                "content": match.metadata.get("text", ""),
                                "similarity": match.score,
                                "metadata": match.metadata,
                                "id": match.id,
                                "namespace": namespace if namespace else "default",
                            }
                        )

            # Sort by similarity score (highest first)
            all_documents.sort(key=lambda x: x["similarity"], reverse=True)

            # Take top results after combining both namespaces
            combined_documents = all_documents[:limit]

            logger.debug(
                f"Pinecone returned {len(combined_documents)} documents from {len(namespaces)} namespaces "
                f"(above threshold {similarity_threshold})"
            )

            # Apply diversification to ensure variety across documents
            diversified_documents = self._diversify_results(combined_documents, limit)

            logger.debug(
                f"Pinecone diversified to {len(diversified_documents)} documents from "
                f"{len({d.get('metadata', {}).get('file_name', d.get('metadata', {}).get('name', 'Unknown')) for d in combined_documents})} unique sources"
            )

            return diversified_documents

        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}")
            return []

    def _diversify_results(
        self, documents: list[dict[str, Any]], limit: int
    ) -> list[dict[str, Any]]:
        """
        Diversify search results to ensure variety across different documents.

        Uses round-robin selection to get chunks from different documents first,
        then fills remaining slots with additional chunks from the same documents.

        Args:
            documents: List of document chunks sorted by similarity
            limit: Maximum number of results to return

        Returns:
            Diversified list of documents with variety across different files
        """
        if not documents or limit <= 0:
            return []

        # Group documents by file_name
        documents_by_file = {}
        for doc in documents:
            file_name = doc.get("metadata", {}).get("file_name", "Unknown")
            if file_name not in documents_by_file:
                documents_by_file[file_name] = []
            documents_by_file[file_name].append(doc)

        # Sort chunks within each document by similarity (highest first)
        for _file_name, chunks in documents_by_file.items():
            chunks.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        result = []
        file_names = list(documents_by_file.keys())

        # Round-robin through documents to get one chunk from each first
        round_num = 0
        while len(result) < limit and file_names:
            for file_name in file_names[
                :
            ]:  # Copy list to avoid modification during iteration
                if len(result) >= limit:
                    break

                # Check if this document has more chunks available
                if round_num < len(documents_by_file[file_name]):
                    result.append(documents_by_file[file_name][round_num])
                else:
                    # This document is exhausted, remove from rotation
                    file_names.remove(file_name)

            round_num += 1

        logger.debug(
            f"Diversification: Selected {len(result)} chunks from {len(documents_by_file)} unique documents"
        )

        return result

    async def delete_documents(self, document_ids: list[str]):
        """Delete documents from Pinecone"""
        try:
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")
            await asyncio.get_event_loop().run_in_executor(
                None, self.index.delete, document_ids
            )
            logger.info(f"✅ Deleted {len(document_ids)} documents from Pinecone")
        except Exception as e:
            logger.error(f"Failed to delete documents from Pinecone: {e}")
            raise

    async def close(self):
        """Clean up Pinecone resources"""
        # Pinecone doesn't require explicit cleanup
        logger.debug("Pinecone connection closed")
        pass

    async def get_stats(self) -> dict[str, Any]:
        """Get Pinecone index statistics"""
        try:
            if self.index is None:
                return {"error": "Index not initialized"}

            stats = await asyncio.get_event_loop().run_in_executor(
                None, self.index.describe_index_stats
            )
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
            }
        except Exception as e:
            logger.error(f"Failed to get Pinecone stats: {e}")
            return {"error": str(e)}
