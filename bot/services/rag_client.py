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
        # Increased timeout for long-running agents (profile, research, etc.)
        self.timeout = httpx.Timeout(
            300.0, connect=10.0
        )  # 5 minutes for agent execution
        self._client: httpx.AsyncClient | None = None

        # Service authentication token
        self.service_token = os.getenv("BOT_SERVICE_TOKEN", "")
        if not self.service_token:
            logger.warning("BOT_SERVICE_TOKEN not set - rag-service calls will fail!")

        # Cache for agent patterns (refreshed periodically)
        self._agent_patterns: list[str] = []
        self._agent_pattern_map: dict[str, str] = {}  # pattern -> agent_name
        self._patterns_last_fetched: float = 0
        self._patterns_cache_ttl: float = 300.0  # 5 minutes

    async def fetch_agent_info(self) -> tuple[list[str], dict[str, str]]:
        """Fetch agent patterns and pattern-to-agent mapping.

        Returns:
            Tuple of (patterns, pattern_map) where pattern_map is {pattern: agent_name}

        """
        import time

        # Return cached if recent
        if (
            self._agent_patterns
            and time.time() - self._patterns_last_fetched < self._patterns_cache_ttl
        ):
            return self._agent_patterns, self._agent_pattern_map

        try:
            # Fetch agent list from agent service
            agent_service_url = os.getenv(
                "AGENT_SERVICE_URL", "http://agent_service:8000"
            )
            url = f"{agent_service_url}/api/agents"

            headers = {"X-Service-Token": self.service_token}
            client = await self._get_client()

            response = await client.get(url, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", [])

                # Generate patterns and mapping
                patterns = []
                pattern_map = {}

                for agent in agents:
                    name = agent.get("name", "")
                    aliases = agent.get("aliases", [])

                    if name:
                        # Add patterns for agent name
                        name_patterns = [
                            f"^/{name}",  # /profile
                            f"^{name}\\s",  # profile <query>
                        ]
                        for pattern in name_patterns:
                            patterns.append(pattern)
                            pattern_map[pattern] = name

                        # Add patterns for aliases
                        for alias in aliases:
                            alias_patterns = [
                                f"^/{alias}",
                                f"^{alias}\\s",
                            ]
                            for pattern in alias_patterns:
                                patterns.append(pattern)
                                pattern_map[pattern] = name

                self._agent_patterns = patterns
                self._agent_pattern_map = pattern_map
                self._patterns_last_fetched = time.time()

                logger.info(
                    f"Generated {len(patterns)} patterns from {len(agents)} agents"
                )
                return patterns, pattern_map
            else:
                logger.warning(f"Failed to fetch agents: {response.status_code}")
                return self._agent_patterns or [], self._agent_pattern_map or {}
        except Exception as e:
            logger.error(f"Error fetching agent info: {e}")
            return self._agent_patterns or [], self._agent_pattern_map or {}

    async def fetch_agent_patterns(self) -> list[str]:
        """Fetch agent invocation patterns from RAG service.

        Returns:
            List of regex patterns that trigger agent routing

        """
        import time

        # Return cached patterns if recent
        if (
            self._agent_patterns
            and time.time() - self._patterns_last_fetched < self._patterns_cache_ttl
        ):
            return self._agent_patterns

        try:
            # Fetch agent list from agent service and generate patterns
            agent_service_url = os.getenv(
                "AGENT_SERVICE_URL", "http://agent_service:8000"
            )
            url = f"{agent_service_url}/api/agents"

            headers = {"X-Service-Token": self.service_token}
            client = await self._get_client()

            response = await client.get(url, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", [])

                # Generate patterns from agent names and aliases
                patterns = []
                for agent in agents:
                    name = agent.get("name", "")
                    aliases = agent.get("aliases", [])

                    if name:
                        patterns.append(f"^/{name}")  # /profile
                        patterns.append(f"^{name}\\s")  # profile <query>

                    for alias in aliases:
                        patterns.append(f"^/{alias}")
                        patterns.append(f"^{alias}\\s")

                self._agent_patterns = patterns
                self._patterns_last_fetched = time.time()
                logger.info(
                    f"Generated {len(patterns)} patterns from {len(agents)} agents"
                )
                return patterns
            else:
                logger.warning(f"Failed to fetch agents: {response.status_code}")
                return self._agent_patterns or []
        except Exception as e:
            logger.error(f"Error fetching agent patterns: {e}")
            return self._agent_patterns or []

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

    async def generate_response_stream(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
        use_rag: bool = True,
        channel: str | None = None,
        thread_ts: str | None = None,
        document_content: str | None = None,
        document_filename: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        session_id: str | None = None,
    ):
        """Generate streaming response from RAG service (for agents).

        Yields:
            String chunks from the streaming response

        Raises:
            RAGClientError: If the request fails

        """
        url = f"{self.base_url}/api/v1/chat/completions"

        # Prepare request body
        request_body = {
            "query": query,
            "messages": conversation_history,
            "use_rag": use_rag,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "context": {
                "channel": channel,
                "thread_ts": thread_ts,
            },
        }

        if document_content:
            request_body["document_content"] = document_content
            request_body["document_filename"] = document_filename

        try:
            headers = {
                "X-Service-Token": self.service_token,
                "Content-Type": "application/json",
            }

            # Serialize request body once
            request_body_str = json.dumps(request_body)

            # Add HMAC signature headers
            headers = add_signature_headers(
                headers, self.service_token, request_body_str
            )

            client = await self._get_client()

            # Stream the response
            async with client.stream(
                "POST",
                url,
                content=request_body_str,
                headers=headers,
                timeout=300.0,
            ) as response:
                if response.status_code == 401:
                    raise RAGClientError(f"Authentication failed: {response.text}")

                if response.status_code != 200:
                    error_text = await response.aread()
                    raise RAGClientError(
                        f"RAG service failed: {response.status_code} - {error_text.decode()}"
                    )

                # Read SSE stream using aiter_bytes to avoid buffering
                logger.info("🚀 Bot starting to read SSE stream from RAG service")
                buffer = b""
                async for data in response.aiter_bytes():
                    buffer += data
                    # Process complete SSE messages (ending with \n\n)
                    while b"\n\n" in buffer:
                        message, buffer = buffer.split(b"\n\n", 1)
                        message_str = message.decode("utf-8")
                        logger.info(f"🚀 Bot received SSE message: {message_str[:100]}")

                        # Parse SSE format
                        if message_str.startswith("data: "):
                            chunk = message_str[6:]  # Remove "data: " prefix
                            if chunk and not chunk.startswith("ERROR"):
                                logger.info(f"🚀 Bot yielding chunk: {chunk[:50]}")
                                yield chunk
                logger.info("🚀 Bot finished reading SSE stream")

        except httpx.TimeoutException as e:
            logger.error(f"RAG service timeout: {e}")
            raise RAGClientError("RAG service timeout") from e
        except Exception as e:
            logger.error(f"Error streaming RAG service: {e}")
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
