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
        limit: int = 100,  # Higher default for hybrid retrieval
        similarity_threshold: float = 0.0,  # No threshold for intermediate results
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search Pinecone for similar documents"""
        try:
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")

            # Run query in executor to avoid blocking
            query_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.index.query(
                    vector=query_embedding,
                    top_k=limit,
                    include_metadata=True,
                    include_values=False,
                    filter=filter,
                ),
            )

            documents = []
            for match in query_result.matches:
                if match.score >= similarity_threshold:
                    documents.append(
                        {
                            "content": match.metadata.get("text", ""),
                            "similarity": match.score,
                            "metadata": match.metadata,
                            "id": match.id,
                        }
                    )

            logger.debug(
                f"Pinecone returned {len(documents)} documents above threshold {similarity_threshold}"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}")
            return []

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
