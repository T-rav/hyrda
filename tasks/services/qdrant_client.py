"""Standalone Qdrant client for tasks service."""

import asyncio
import hashlib
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class QdrantClient:
    """Standalone Qdrant client for metric sync."""

    def __init__(self):
        """Initialize Qdrant client."""
        self.host = os.getenv("QDRANT_HOST", "qdrant")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self.api_key = os.getenv(
            "QDRANT_API_KEY"
        )  # Set via docker-compose from VECTOR_API_KEY
        self.collection_name = os.getenv(
            "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
        )
        self.client = None

    async def initialize(self):
        """Initialize Qdrant connection."""
        try:
            from qdrant_client import QdrantClient as QdrantSDK
            from qdrant_client.models import Distance, VectorParams

            # Initialize Qdrant client with HTTPS support
            # Accept self-signed certificates in development environment
            environment = os.getenv("ENVIRONMENT", "development")

            if self.api_key:
                self.client = QdrantSDK(
                    url=f"https://{self.host}:{self.port}",
                    api_key=self.api_key,
                    timeout=60,
                    verify=environment != "development",  # Accept self-signed certs in dev
                )
            else:
                self.client = QdrantSDK(
                    host=self.host,
                    port=self.port,
                    timeout=60,
                    https=True,
                    verify=environment != "development",  # Accept self-signed certs in dev
                )

            # Create collection if it doesn't exist
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.client.get_collections
            )
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                # Create collection with OpenAI embedding dimensions (3072 for text-embedding-3-large)
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=3072, distance=Distance.COSINE
                        ),
                    ),
                )
                logger.info(f"✅ Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(
                    f"✅ Qdrant initialized with collection: {self.collection_name}"
                )

        except ImportError as e:
            raise ImportError(
                "qdrant-client package not installed. Run: pip install qdrant-client"
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            raise

    async def upsert_with_namespace(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]],
        namespace: str = "metric",
    ):
        """Upsert vectors to Qdrant with namespace as payload field."""
        if not self.client:
            raise RuntimeError("Qdrant not initialized")

        from qdrant_client.models import PointStruct

        points = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
            doc_metadata = metadata[i] if metadata else {}

            # Create stable UUID based on actual record ID from metadata
            # This ensures upsert replaces existing records instead of creating duplicates
            # Qdrant requires UUIDs or integers as point IDs
            record_id = (
                doc_metadata.get("employee_id")
                or doc_metadata.get("project_id")
                or doc_metadata.get("client_id")
                or doc_metadata.get("allocation_id")
                or doc_metadata.get(
                    "chunk_id"
                )  # For SEC filings and other chunked documents
                or f"unknown_{i}"
            )
            # Generate deterministic UUID from namespace + record_id
            id_string = f"{namespace}_{record_id}"
            id_hash = hashlib.md5(id_string.encode(), usedforsecurity=False).hexdigest()
            doc_id = str(uuid.UUID(id_hash))

            # Add text and namespace to metadata
            doc_metadata["text"] = text
            doc_metadata["namespace"] = namespace

            points.append(
                PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=doc_metadata,
                )
            )

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]

            def upsert_batch(b=batch):
                return self.client.upsert(
                    collection_name=self.collection_name,
                    points=b,
                )

            await asyncio.get_event_loop().run_in_executor(None, upsert_batch)

        logger.info(
            f"✅ Added {len(texts)} documents to Qdrant namespace '{namespace}'"
        )

    async def close(self):
        """Close connection."""
        if self.client:
            await asyncio.get_event_loop().run_in_executor(None, self.client.close)
        logger.debug("Qdrant connection closed")
