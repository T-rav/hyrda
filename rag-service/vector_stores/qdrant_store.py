"""
Qdrant Vector Store Implementation

Handles Qdrant-specific vector database operations.
"""

import asyncio
import hashlib
import logging
import os
import ssl
import uuid
from typing import Any

from .base import VectorStore

try:
    from qdrant_client import QdrantClient  # type: ignore[reportMissingImports]
    from qdrant_client.models import (  # type: ignore[reportMissingImports]
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )
except ImportError:
    QdrantClient = None  # type: ignore[misc,assignment]
    Distance = None  # type: ignore[misc,assignment]
    VectorParams = None  # type: ignore[misc,assignment]
    PointStruct = None  # type: ignore[misc,assignment]
    Filter = None  # type: ignore[misc,assignment]
    FieldCondition = None  # type: ignore[misc,assignment]
    MatchValue = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# Qdrant configuration constants
DEFAULT_QDRANT_TIMEOUT = 60  # Client timeout in seconds
OPENAI_EMBEDDING_DIMENSION = 1536  # Dimension for text-embedding-3-small
DEFAULT_BATCH_SIZE = 100  # Default batch size for operations
DEFAULT_SEARCH_LIMIT = 100  # Default limit for search results


class QdrantVectorStore(VectorStore):
    """Qdrant vector store implementation for dense retrieval"""

    def __init__(self, settings):
        super().__init__(settings)
        self.client = None
        self.host = getattr(settings, "host", "localhost")
        self.port = getattr(settings, "port", 6333)
        self.api_key = getattr(settings, "api_key", None)

    async def initialize(self):
        """Initialize Qdrant client and collection"""
        try:
            if QdrantClient is None:
                raise ImportError("qdrant-client package is required for Qdrant vector store")

            # Initialize Qdrant client with HTTPS support
            # Check for certificate path (development) or use system CA store (production/Docker)
            cert_path = os.getenv("QDRANT_CERT_PATH", os.getenv("VECTOR_CERT_PATH"))

            # Try to find mkcert CA certificate for local development
            if not cert_path:
                # Look for mkcert CA in .ssl directory (local development)
                ca_cert_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    ".ssl",
                    "mkcert-ca.crt",
                )
                if os.path.exists(ca_cert_path):
                    cert_path = ca_cert_path

            # Determine SSL verification strategy
            if cert_path and os.path.exists(cert_path):
                # Use SSL context with CA certificate for proper validation
                verify = ssl.create_default_context(cafile=cert_path)
            else:
                # Fallback: disable SSL verification for local dev without cert
                # In production with proper certificates, this should be True
                verify = os.getenv("QDRANT_VERIFY_SSL", "false").lower() == "true"

            if self.api_key:
                self.client = QdrantClient(
                    url=f"https://{self.host}:{self.port}",
                    api_key=self.api_key,
                    timeout=DEFAULT_QDRANT_TIMEOUT,
                    verify=verify,
                )
            else:
                self.client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    timeout=DEFAULT_QDRANT_TIMEOUT,
                    https=True,
                    verify=verify,
                )

            # Create collection if it doesn't exist
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.client.get_collections
            )
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                # Create collection with OpenAI embedding dimensions (1536 for text-embedding-3-small)
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=OPENAI_EMBEDDING_DIMENSION, distance=Distance.COSINE
                        ),
                    ),
                )
                logger.info(f"✅ Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"✅ Qdrant initialized with collection: {self.collection_name}")

        except ImportError:
            raise ImportError(
                "qdrant-client package not installed. Run: pip install qdrant-client"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            raise

    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Add documents to Qdrant with enhanced metadata"""
        try:
            points = []
            for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
                # Generate a deterministic UUID from text content + index
                # This allows us to reupload the same content without duplicates
                text_hash = hashlib.md5(f"{text}_{i}".encode(), usedforsecurity=False).hexdigest()
                # Convert MD5 hash to UUID (Qdrant requires UUID or integer)
                doc_id = str(uuid.UUID(text_hash))

                doc_metadata = metadata[i] if metadata else {}

                # Store enhanced text with title injection
                doc_metadata["text"] = text

                points.append(
                    PointStruct(
                        id=doc_id,
                        vector=embedding,
                        payload=doc_metadata,
                    )
                )

            # Upsert in batches
            if self.client is None:
                raise RuntimeError("Qdrant client not initialized")

            batch_size = DEFAULT_BATCH_SIZE
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda b=batch: self.client.upsert(
                        collection_name=self.collection_name,
                        points=b,
                    ),
                )

            logger.info(f"✅ Added {len(texts)} documents to Qdrant")

        except Exception as e:
            logger.error(f"Failed to add documents to Qdrant: {e}")
            raise

    async def search(
        self,
        query_embedding: list[float],
        limit: int = DEFAULT_SEARCH_LIMIT,  # Higher default for better retrieval
        similarity_threshold: float = 0.0,  # No threshold for intermediate results
        filter: dict[str, Any] | None = None,
        query_text: str = "",  # Not used for pure vector search
    ) -> list[dict[str, Any]]:
        """Search Qdrant for similar documents across all namespaces"""
        try:
            if self.client is None:
                logger.error("Failed to search Qdrant: Qdrant client not initialized")
                return []

            # Query for documents with and without namespace filtering
            namespaces = ["metric"]  # Metric namespace
            all_documents = []

            # First, get documents from specific namespaces
            for namespace in namespaces:
                # Build filter for namespace
                query_filter = Filter(
                    must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
                )

                # Run query in executor to avoid blocking (using new query_points API)
                search_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace, f=query_filter: (
                        self.client.query_points(
                            collection_name=self.collection_name,
                            query=query_embedding,
                            limit=limit,
                            query_filter=f,
                            with_payload=True,
                            with_vectors=False,
                        ).points
                    ),
                )

                for match in search_result:
                    if match.score >= similarity_threshold:
                        all_documents.append(
                            {
                                "content": match.payload.get("text", ""),
                                "similarity": match.score,
                                "metadata": match.payload,
                                "id": match.id,
                                "namespace": namespace,
                            }
                        )

            # Also search documents without namespace (default namespace)
            # Build filter to exclude documents with namespace field
            default_filter = Filter(must_not=[FieldCondition(key="namespace", match=None)])

            default_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda f=default_filter: (
                    self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_embedding,
                        limit=limit,
                        query_filter=None,  # Get all documents for now
                        with_payload=True,
                        with_vectors=False,
                    ).points
                ),
            )

            for match in default_result:
                if (
                    match.score >= similarity_threshold
                    and match.payload
                    and "namespace" not in match.payload
                ):
                    all_documents.append(
                        {
                            "content": match.payload.get("text", ""),
                            "similarity": match.score,
                            "metadata": match.payload,
                            "id": match.id,
                            "namespace": "default",
                        }
                    )

            # Sort by similarity score (highest first)
            all_documents.sort(key=lambda x: x["similarity"], reverse=True)

            # Take top results after combining all namespaces
            combined_documents = all_documents[:limit]

            logger.debug(
                f"Qdrant returned {len(combined_documents)} documents "
                f"(above threshold {similarity_threshold})"
            )

            # Apply diversification to ensure variety across documents
            diversified_documents = self._diversify_results(combined_documents, limit)

            logger.debug(
                f"Qdrant diversified to {len(diversified_documents)} documents from "
                f"{len({d.get('metadata', {}).get('file_name', d.get('metadata', {}).get('name', 'Unknown')) for d in combined_documents})} unique sources"
            )

            return diversified_documents

        except Exception as e:
            logger.error(f"Failed to search Qdrant: {e}")
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
            for file_name in file_names[:]:  # Copy list to avoid modification during iteration
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
        """Delete documents from Qdrant"""
        try:
            if self.client is None:
                raise RuntimeError("Qdrant client not initialized")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=document_ids,
                ),
            )
            logger.info(f"✅ Deleted {len(document_ids)} documents from Qdrant")
        except Exception as e:
            logger.error(f"Failed to delete documents from Qdrant: {e}")
            raise

    async def close(self):
        """Clean up Qdrant resources"""
        if self.client:
            await asyncio.get_event_loop().run_in_executor(None, self.client.close)
        logger.debug("Qdrant connection closed")

    async def get_stats(self) -> dict[str, Any]:
        """Get Qdrant collection statistics"""
        try:
            if self.client is None:
                return {"error": "Client not initialized"}

            collection_info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.get_collection(collection_name=self.collection_name),
            )
            return {
                "total_vector_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "status": collection_info.status,
            }
        except Exception as e:
            logger.error(f"Failed to get Qdrant stats: {e}")
            return {"error": str(e)}
