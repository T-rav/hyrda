"""HTTP client for calling agent-service API."""

import json
import logging
import os
import sys
from collections.abc import AsyncGenerator
from typing import Any

import httpx

# Add shared directory to path for tracing utilities
sys.path.insert(0, "/app")
from shared.utils.tracing import add_trace_id_to_headers, get_trace_id

from services.langfuse_service import get_langfuse_service
from utils.trace_propagation import add_trace_headers_to_request

logger = logging.getLogger(__name__)


class AgentClient:
    """HTTP client for agent-service API.

    Calls agents via HTTP instead of local imports.
    """

    def __init__(self, base_url: str = None):
        """Initialize agent client.

        Args:
            base_url: Agent-service base URL (defaults to env var or localhost)
        """
        self.base_url = base_url or os.getenv(
            "AGENT_SERVICE_URL", "https://agent-service:8000"
        )
        self.service_token = os.getenv("BOT_SERVICE_TOKEN", "dev-bot-service-token")

        logger.info(f"AgentClient initialized with base_url: {self.base_url}")

    async def invoke(
        self, agent_name: str, query: str, context: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Invoke agent via HTTP API.

        Args:
            agent_name: Name of agent to invoke (e.g., "research", "profile")
            query: User query
            context: Context dict (must include thread_id for checkpointing)

        Returns:
            {"response": "...", "metadata": {...}}

        Raises:
            httpx.HTTPError: If agent invocation fails
        """
        context = context or {}

        trace_id = get_trace_id()
        logger.info(
            f"[{trace_id}] Invoking agent '{agent_name}' via HTTP with thread_id={context.get('thread_id')}"
        )

        payload = {"query": query, "context": context}

        headers = {
            "X-Service-Token": self.service_token,
            "Content-Type": "application/json",
        }

        # Add distributed trace ID for cross-service correlation
        headers = add_trace_id_to_headers(headers)

        # Add Langfuse trace context for LLM observability
        trace_context = context.get("trace_context")
        if not trace_context:
            langfuse_service = get_langfuse_service()
            if langfuse_service:
                trace_context = langfuse_service.get_current_trace_context()
        if trace_context:
            headers = add_trace_headers_to_request(headers, trace_context)

        # Use HTTPS with verify=False for internal services (they use self-signed certs)
        # Security: Internal service-to-service calls within Docker network
        async with httpx.AsyncClient(verify=False, timeout=300.0) as client:  # nosec B501
            try:
                response = await client.post(
                    f"{self.base_url}/api/agents/{agent_name}/invoke",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Agent '{agent_name}' returned response (length: {len(result.get('response', ''))})"
                )

                return result

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Agent invocation failed: {e.response.status_code} - {e.response.text}"
                )
                raise
            except Exception as e:
                logger.error(f"Error invoking agent '{agent_name}': {e}")
                raise

    async def stream(
        self, agent_name: str, query: str, context: dict[str, Any] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream agent execution with live status updates.

        Args:
            agent_name: Name of agent to stream
            query: User query
            context: Context dict (must include thread_id for checkpointing)

        Yields:
            Status dicts with {"phase": "...", "step": "...", "message": "..."}
            Final dict with {"response": "...", "metadata": {...}}

        Raises:
            httpx.HTTPError: If agent streaming fails
        """
        context = context or {}

        trace_id = get_trace_id()
        logger.info(
            f"[{trace_id}] Streaming agent '{agent_name}' via HTTP with thread_id={context.get('thread_id')}"
        )

        payload = {"query": query, "context": context}

        headers = {
            "X-Service-Token": self.service_token,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        # Add distributed trace ID for cross-service correlation
        headers = add_trace_id_to_headers(headers)

        # Add Langfuse trace context for LLM observability
        trace_context = context.get("trace_context")
        if not trace_context:
            langfuse_service = get_langfuse_service()
            if langfuse_service:
                trace_context = langfuse_service.get_current_trace_context()

        if trace_context:
            headers = add_trace_headers_to_request(headers, trace_context)
            logger.debug(f"[{trace_id}] Added Langfuse trace context")

        # Use 30 minute timeout for long-running agents
        timeout = httpx.Timeout(1800.0, connect=30.0)

        # Use HTTPS with verify=False for internal services (they use self-signed certs)
        # Security: Internal service-to-service calls within Docker network
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:  # nosec B501
            try:
                logger.info("🚀 Bot about to start HTTP stream request...")
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/agents/{agent_name}/stream",
                    json=payload,
                    headers=headers,
                ) as response:
                    logger.info(f"🚀 Bot got response status: {response.status_code}")
                    response.raise_for_status()
                    logger.info(
                        "🚀 Bot status check passed, starting to iterate over SSE lines..."
                    )
                    # Parse Server-Sent Events (SSE)
                    async for line in response.aiter_lines():
                        logger.info(f"🚀 Bot received SSE line: {line[:100]}")
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            try:
                                data = json.loads(data_str)
                                logger.info(f"✅ Bot parsed SSE data: {data}")
                                yield data
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE data: {data_str}")
                                continue
                    logger.info("🏁 Bot finished iterating SSE lines")

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Agent streaming failed: {e.response.status_code} - {e.response.text}"
                )
                raise
            except Exception as e:
                logger.error(f"Error streaming agent '{agent_name}': {e}")
                raise


class _AgentClientSingleton:
    """Singleton wrapper for AgentClient."""

    _instance: AgentClient | None = None

    @classmethod
    def get_instance(cls) -> AgentClient:
        """Get singleton agent client instance."""
        if cls._instance is None:
            cls._instance = AgentClient()
        return cls._instance


def get_agent_client() -> AgentClient:
    """Get singleton agent client instance."""
    return _AgentClientSingleton.get_instance()
