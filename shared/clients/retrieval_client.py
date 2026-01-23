"""
HTTP client for rag-service retrieval API.

This client provides agents with access to vector retrieval without
direct Qdrant dependencies. All retrieval goes through rag-service's
/api/v1/retrieve endpoint.
"""

import json
import logging
import sys
from typing import Any

import httpx

# Add shared directory to path
sys.path.insert(0, "/app")
from shared.utils.request_signing import add_signature_headers

from .config import RetrievalClientConfig
from .exceptions import (
    RetrievalAuthError,
    RetrievalConnectionError,
    RetrievalServiceError,
    RetrievalTimeoutError,
)
from .models import Chunk, RetrievalMetadata, RetrievalRequest, RetrievalResponse

logger = logging.getLogger(__name__)


class RetrievalClient:
    """HTTP client for rag-service retrieval API."""

    def __init__(self, config: RetrievalClientConfig | None = None):
        """
        Initialize retrieval client.

        Args:
            config: Client configuration (default: from environment variables)
        """
        self.config = config or RetrievalClientConfig.from_env()

        if not self.config.service_token:
            logger.warning(
                "RAG_SERVICE_TOKEN not set - retrieval requests may fail authentication"
            )

    async def retrieve(
        self,
        query: str,
        user_id: str | None = None,
        system_message: str | None = None,
        max_chunks: int | None = None,
        similarity_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        enable_query_rewriting: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant chunks from vector database.

        Args:
            query: Search query
            user_id: User ID for tracing (default: config.default_user_id)
            system_message: Custom context for filtering (e.g., permissions, role)
            max_chunks: Maximum chunks to return (default: config.default_max_chunks)
            similarity_threshold: Minimum similarity score (default: config.default_similarity_threshold)
            filters: Metadata filters for Qdrant
            conversation_history: Conversation context for query rewriting
            enable_query_rewriting: Enable query rewriting (default: config.default_enable_query_rewriting)

        Returns:
            List of chunks with content, metadata, and similarity scores

        Raises:
            RetrievalAuthError: Authentication failed
            RetrievalTimeoutError: Request timed out
            RetrievalConnectionError: Cannot connect to service
            RetrievalServiceError: Service returned error
        """
        # Build request with defaults from config
        request = RetrievalRequest(
            query=query,
            user_id=user_id or self.config.default_user_id,
            system_message=system_message,
            max_chunks=max_chunks or self.config.default_max_chunks,
            similarity_threshold=similarity_threshold
            or self.config.default_similarity_threshold,
            filters=filters,
            conversation_history=conversation_history,
            enable_query_rewriting=enable_query_rewriting
            if enable_query_rewriting is not None
            else self.config.default_enable_query_rewriting,
        )

        # Build request components
        payload = self._build_payload(request)
        headers = self._build_headers(request.user_id)
        signed_payload = self._sign_request(payload, headers)

        # Execute request
        logger.debug(
            f"Retrieving chunks: query='{query[:50]}...', max_chunks={request.max_chunks}"
        )

        try:
            response = await self._execute_request(
                signed_payload["payload"], signed_payload["headers"]
            )
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise RetrievalTimeoutError(self.config.request_timeout) from e
        except httpx.ConnectError as e:
            raise RetrievalConnectionError(self.config.base_url, e) from e

        # Parse response
        return self._parse_response(response)

    def _build_payload(self, request: RetrievalRequest) -> dict[str, Any]:
        """Build request payload from RetrievalRequest model."""
        return request.model_dump(exclude_none=True)

    def _build_headers(self, user_id: str) -> dict[str, str]:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "X-Service-Token": self.config.service_token,
            "X-User-Email": user_id,
        }

    def _sign_request(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Sign request with HMAC signature."""
        payload_json = json.dumps(payload)
        signed_headers = add_signature_headers(
            headers, self.config.service_token, payload_json
        )

        return {
            "payload": payload_json,
            "headers": signed_headers,
        }

    async def _execute_request(
        self, payload_json: str, headers: dict[str, str]
    ) -> httpx.Response:
        """Execute HTTP POST request to retrieval API."""
        url = f"{self.config.base_url}/api/v1/retrieve"

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            response = await client.post(url, content=payload_json, headers=headers)
            response.raise_for_status()
            return response

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Handle HTTP errors and raise appropriate custom exceptions."""
        status_code = error.response.status_code

        if status_code == 401:
            raise RetrievalAuthError("Invalid service token") from error
        elif status_code >= 500:
            detail = error.response.text
            raise RetrievalServiceError(status_code, detail) from error
        else:
            # Re-raise for other HTTP errors
            raise

    def _parse_response(self, response: httpx.Response) -> list[dict[str, Any]]:
        """Parse and log response data."""
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


def get_retrieval_client(config: RetrievalClientConfig | None = None) -> RetrievalClient:
    """Get global retrieval client instance.

    Args:
        config: Optional config for first initialization

    Returns:
        Singleton RetrievalClient instance
    """
    global _retrieval_client
    if _retrieval_client is None:
        _retrieval_client = RetrievalClient(config=config)
        logger.info("✅ Retrieval client initialized")
    return _retrieval_client
