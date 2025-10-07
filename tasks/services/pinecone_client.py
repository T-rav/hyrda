"""Standalone Pinecone client for tasks service."""

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class PineconeClient:
    """Standalone Pinecone client for metric sync."""

    def __init__(self):
        """Initialize Pinecone client."""
        self.api_key = os.getenv("VECTOR_API_KEY")
        if not self.api_key:
            raise ValueError("VECTOR_API_KEY not found in environment")

        self.index_name = os.getenv(
            "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
        )
        self.index = None

    async def initialize(self):
        """Initialize Pinecone connection."""
        try:
            from pinecone import Pinecone

            pc = Pinecone(api_key=self.api_key)
            self.index = pc.Index(self.index_name)
            logger.info(f"✅ Pinecone initialized with index: {self.index_name}")
        except ImportError as e:
            raise ImportError(
                "pinecone package not installed. Run: pip install pinecone"
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    async def upsert_with_namespace(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]],
        namespace: str = "metric",
    ):
        """Upsert vectors to Pinecone with namespace."""
        if not self.index:
            raise RuntimeError("Pinecone not initialized")

        vectors = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
            doc_metadata = metadata[i] if metadata else {}

            # Create stable ID based on actual record ID from metadata
            # This ensures upsert replaces existing records instead of creating duplicates
            record_id = (
                doc_metadata.get("employee_id")
                or doc_metadata.get("project_id")
                or doc_metadata.get("client_id")
                or doc_metadata.get("allocation_id")
                or f"unknown_{i}"
            )
            doc_id = f"{namespace}_{record_id}"

            doc_metadata["text"] = text

            vectors.append(
                {"id": doc_id, "values": embedding, "metadata": doc_metadata}
            )

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]

            def upsert_batch(b=batch):
                return self.index.upsert(vectors=b, namespace=namespace)

            await asyncio.get_event_loop().run_in_executor(None, upsert_batch)

        logger.info(
            f"✅ Added {len(texts)} documents to Pinecone namespace '{namespace}'"
        )

    async def close(self):
        """Close connection."""
        logger.debug("Pinecone connection closed")
