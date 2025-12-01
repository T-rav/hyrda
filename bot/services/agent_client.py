"""HTTP client for calling agent-service."""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AgentClient:
    """Client for calling agent-service HTTP API with retry logic."""

    def __init__(self, base_url: str = "http://agent_service:8000"):
        """Initialize agent client.

        Args:
            base_url: Base URL of agent-service (defaults to Docker service name)
        """
        self.base_url = base_url.rstrip("/")
        # Reduced timeout from 5min to 30s to fail fast
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        # Persistent HTTP client to reuse connections (fixes resource leak)
        self._client: httpx.AsyncClient | None = None
        self.max_retries = 3
        self.retry_delay = 1.0  # Start with 1 second

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

    async def invoke_agent(
        self, agent_name: str, query: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke an agent via HTTP.

        Args:
            agent_name: Name of agent to invoke
            query: User query
            context: Context dictionary for agent

        Returns:
            Agent execution result with response and metadata

        Raises:
            AgentClientError: If agent execution fails
        """
        url = f"{self.base_url}/api/agents/{agent_name}/invoke"
        logger.info(f"Calling agent-service: {url}")

        # Serialize context - remove non-serializable objects
        serializable_context = self._prepare_context(context)

        # Retry with exponential backoff for transient failures
        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.post(
                    url,
                    json={"query": query, "context": serializable_context},
                )

                if response.status_code == 404:
                    raise AgentClientError(f"Agent '{agent_name}' not found")

                if response.status_code != 200:
                    raise AgentClientError(
                        f"Agent execution failed: {response.status_code} - {response.text}"
                    )

                result = response.json()
                return {
                    "response": result.get("response", ""),
                    "metadata": result.get("metadata", {}),
                }

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.max_retries}: {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise AgentClientError("Agent execution timed out after retries") from e

            except httpx.ConnectError as e:
                logger.warning(
                    f"Connection error on attempt {attempt + 1}/{self.max_retries}: {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise AgentClientError(
                    "Unable to connect to agent service after retries"
                ) from e

            except Exception as e:
                logger.error(f"Error calling agent-service: {e}", exc_info=True)
                raise AgentClientError(f"Agent execution failed: {str(e)}") from e
        # NOTE: Agent invocation metrics are tracked in agent-service itself,
        # not here. This ensures ALL invocations (Slack, LibreChat, direct API)
        # are counted at the source.

    async def list_agents(self) -> list[dict[str, Any]]:
        """List available agents.

        Returns:
            List of agent metadata

        Raises:
            AgentClientError: If request fails
        """
        url = f"{self.base_url}/api/agents"

        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code != 200:
                raise AgentClientError(f"Failed to list agents: {response.status_code}")

            result = response.json()
            return result.get("agents", [])

        except Exception as e:
            logger.error(f"Error listing agents: {e}", exc_info=True)
            raise AgentClientError(f"Failed to list agents: {str(e)}") from e

    def _prepare_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Prepare context for serialization.

        Removes non-serializable objects like service instances.

        Args:
            context: Original context dictionary

        Returns:
            Serializable context dictionary
        """
        serializable = {}

        # Copy simple, serializable values
        for key, value in context.items():
            # Skip service instances and other non-serializable objects
            if key in [
                "slack_service",
                "llm_service",
                "conversation_cache",
            ]:
                continue

            # Keep simple types
            if isinstance(value, (str, int, float, bool, type(None), list, dict)):
                serializable[key] = value

        return serializable


class AgentClientError(Exception):
    """Exception raised when agent client operations fail."""

    pass


# Global client instance
_agent_client: AgentClient | None = None


def get_agent_client() -> AgentClient:
    """Get or create global agent client instance.

    Returns:
        AgentClient instance
    """
    global _agent_client  # noqa: PLW0603

    if _agent_client is None:
        import os

        base_url = os.getenv("AGENT_SERVICE_URL", "http://agent_service:8000")
        _agent_client = AgentClient(base_url=base_url)

    return _agent_client
