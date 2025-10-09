"""
Minimal Qdrant Vector Store for Ingestion

Stripped-down version with only what's needed for document ingestion.
"""

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class QdrantVectorStore:
    """Minimal Qdrant vector store for document ingestion."""

    def __init__(self, host: str, port: int, collection_name: str, api_key: str | None = None):
        """
        Initialize Qdrant client.

        Args:
            host: Qdrant server host
            port: Qdrant server port
            collection_name: Name of the collection to use
            api_key: Optional API key for authentication
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.client = QdrantClient(host=host, port=port, api_key=api_key)

    async def initialize(self):
        """Initialize the vector store (create collection if needed)."""
        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)

        if not collection_exists:
            # Create collection with default embedding dimension (1536 for OpenAI)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

    async def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        texts: list[str],
    ) -> None:
        """
        Upsert vectors into the collection.

        Args:
            ids: List of unique IDs for the vectors
            embeddings: List of embedding vectors
            metadatas: List of metadata dictionaries
            texts: List of text chunks
        """
        points = [
            PointStruct(
                id=doc_id,
                vector=embedding,
                payload={"text": text, **metadata},
            )
            for doc_id, embedding, metadata, text in zip(ids, embeddings, metadatas, texts)
        ]

        self.client.upsert(collection_name=self.collection_name, points=points)

    async def delete(self, ids: list[str]) -> None:
        """
        Delete vectors by IDs.

        Args:
            ids: List of IDs to delete
        """
        self.client.delete(collection_name=self.collection_name, points_selector=ids)
