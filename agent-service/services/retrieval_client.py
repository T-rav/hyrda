"""
HTTP client for rag-service retrieval API.

This client provides agents with access to vector retrieval without
direct Qdrant dependencies. All retrieval goes through rag-service's
/api/v1/retrieve endpoint.
"""

import json
import logging
import os
import sys
from typing import Any

import httpx

# Add shared directory to path
sys.path.insert(0, "/app")
from shared.utils.request_signing import add_signature_headers

logger = logging.getLogger(__name__)


class RetrievalClient:
    """HTTP client for rag-service retrieval API."""

    def __init__(
        self,
        base_url: str | None = None,
        service_token: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize retrieval client.

        Args:
            base_url: rag-service URL (default: from RAG_SERVICE_URL env var)
            service_token: Service authentication token (default: from RAG_SERVICE_TOKEN)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv(
            "RAG_SERVICE_URL", "http://rag-service:8002"
        )
        self.service_token = service_token or os.getenv("RAG_SERVICE_TOKEN")
        self.timeout = timeout

        if not self.service_token:
            logger.warning(
                "RAG_SERVICE_TOKEN not set - retrieval requests may fail authentication"
            )

    async def retrieve(
        self,
        query: str,
        user_id: str | None = None,
        system_message: str | None = None,
        max_chunks: int = 10,
        similarity_threshold: float = 0.7,
        filters: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        enable_query_rewriting: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant chunks from vector database.

        Args:
            query: Search query
            user_id: User ID for tracing (default: "agent@system")
            system_message: Custom context for filtering (e.g., permissions, role)
            max_chunks: Maximum chunks to return (1-20)
            similarity_threshold: Minimum similarity score (0.0-1.0)
            filters: Metadata filters for Qdrant
            conversation_history: Conversation context for query rewriting
            enable_query_rewriting: Enable query rewriting for better retrieval

        Returns:
            List of chunks with content, metadata, and similarity scores

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/api/v1/retrieve"

        payload = {
            "query": query,
            "user_id": user_id or "agent@system",
            "max_chunks": max_chunks,
            "similarity_threshold": similarity_threshold,
            "enable_query_rewriting": enable_query_rewriting,
        }

        if system_message:
            payload["system_message"] = system_message

        if filters:
            payload["filters"] = filters

        if conversation_history:
            payload["conversation_history"] = conversation_history

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Service-Token": self.service_token,
            "X-User-Email": user_id or "agent@system",
        }

        # Convert payload to JSON string for signing
        payload_json = json.dumps(payload)

        # Add HMAC signature headers
        headers = add_signature_headers(headers, self.service_token, payload_json)

        logger.debug(
            f"Retrieving chunks: query='{query[:50]}...', max_chunks={max_chunks}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, content=payload_json, headers=headers)
            response.raise_for_status()

            data = response.json()
            chunks = data.get("chunks", [])
            metadata = data.get("metadata", {})

            logger.info(
                f"✅ Retrieved {len(chunks)} chunks from {metadata.get('unique_sources', 0)} sources "
                f"(avg similarity: {metadata.get('avg_similarity', 0):.3f})"
            )

            return chunks


# Singleton instance
_retrieval_client: RetrievalClient | None = None


def get_retrieval_client() -> RetrievalClient:
    """Get global retrieval client instance."""
    global _retrieval_client
    if _retrieval_client is None:
        _retrieval_client = RetrievalClient()
        logger.info("✅ Retrieval client initialized")
    return _retrieval_client
