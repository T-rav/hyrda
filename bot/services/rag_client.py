"""HTTP client for calling rag-service (chat completion proxy)."""

import json
import logging
import os
import sys
from typing import Any

import httpx

# Add shared directory to path for request signing utilities
sys.path.insert(0, "/app")
from shared.utils.request_signing import add_signature_headers

logger = logging.getLogger(__name__)


class RAGClient:
    """Client for calling rag-service HTTP API.

    This client calls the RAG service which handles:
    - Agent routing (decides when to use specialized agents)
    - RAG retrieval (vector search for context)
    - LLM generation (with tools like web search)
    - Response generation with citations
    """

    def __init__(self, base_url: str = "http://rag_service:8002"):
        """Initialize RAG client.

        Args:
            base_url: Base URL of rag-service (defaults to Docker service name)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._client: httpx.AsyncClient | None = None

        # Service authentication token
        self.service_token = os.getenv("BOT_SERVICE_TOKEN", "")
        if not self.service_token:
            logger.warning("BOT_SERVICE_TOKEN not set - rag-service calls will fail!")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate_response(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
        system_message: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        use_rag: bool = True,
        document_content: str | None = None,
        document_filename: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate response via rag-service.

        This calls the rag-service which handles all the intelligence:
        - Agent routing
        - RAG retrieval
        - LLM generation
        - Tool calling (web search, etc.)

        Args:
            query: User query
            conversation_history: Previous messages [{'role': 'user', 'content': '...'}, ...]
            system_message: Custom system prompt
            user_id: User ID for tracing
            conversation_id: Conversation ID (e.g., thread_ts)
            use_rag: Enable RAG retrieval
            document_content: Uploaded document content
            document_filename: Uploaded document filename
            session_id: Session ID for cache

        Returns:
            Response dict with 'response', 'citations', 'metadata'

        Raises:
            RAGClientError: If request fails
        """
        url = f"{self.base_url}/api/v1/chat/completions"

        request_body = {
            "query": query,
            "conversation_history": conversation_history,
            "system_message": system_message,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "use_rag": use_rag,
            "document_content": document_content,
            "document_filename": document_filename,
            "session_id": session_id,
        }

        # Remove None values
        request_body = {k: v for k, v in request_body.items() if v is not None}

        logger.info(
            f"Calling rag-service: query='{query[:50]}...', use_rag={use_rag}, "
            f"conversation_id={conversation_id}"
        )

        try:
            headers = {
                "X-Service-Token": self.service_token,
                "Content-Type": "application/json",
            }

            # Serialize request body once and use the exact same string for signing and sending
            request_body_str = json.dumps(request_body)

            # Add HMAC signature headers for authentication
            headers = add_signature_headers(
                headers, self.service_token, request_body_str
            )

            client = await self._get_client()
            response = await client.post(
                url,
                content=request_body_str,  # Send the exact string that was signed
                headers=headers,
            )

            if response.status_code == 401:
                raise RAGClientError("Authentication failed - check BOT_SERVICE_TOKEN")

            if response.status_code != 200:
                raise RAGClientError(
                    f"RAG service failed: {response.status_code} - {response.text}"
                )

            result = response.json()
            logger.info(
                f"RAG service response received: {len(result.get('response', ''))} chars, "
                f"citations={len(result.get('citations', []))}"
            )

            return result

        except httpx.TimeoutException as e:
            logger.error(f"RAG service timeout: {e}")
            raise RAGClientError("RAG service timeout") from e

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to RAG service: {e}")
            raise RAGClientError("Cannot connect to RAG service") from e

        except Exception as e:
            logger.error(f"Error calling RAG service: {e}", exc_info=True)
            raise RAGClientError(f"RAG service error: {str(e)}") from e


class RAGClientError(Exception):
    """Exception raised when RAG client operations fail."""

    pass


# Global client instance
_rag_client: RAGClient | None = None


def get_rag_client() -> RAGClient:
    """Get or create global RAG client instance.

    Returns:
        RAGClient instance
    """
    global _rag_client  # noqa: PLW0603

    if _rag_client is None:
        base_url = os.getenv("RAG_SERVICE_URL", "http://rag_service:8002")
        _rag_client = RAGClient(base_url=base_url)

    return _rag_client
