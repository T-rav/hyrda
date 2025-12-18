"""Generic agent client that works via HTTP API only.

Treats embedded (local) and cloud (LangGraph) agents identically.
All agent discovery happens via control-plane API.

Rule: If agent not registered in control plane → 404 Not Found

Security:
- Uses HTTP for internal Docker network (no TLS needed for trusted network)
- Uses HTTPS with proper verification for external services
- Never uses verify=False in production
"""

import logging
import os
import sys
from collections.abc import AsyncGenerator
from typing import Any

import httpx

# Add shared directory to path
sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from shared.utils.http_client import get_internal_service_url, get_secure_client

logger = logging.getLogger(__name__)


class AgentClient:
    """HTTP-only agent client. No direct agent imports.

    Architecture:
    1. Query control plane API to discover agent endpoint
    2. Invoke agent via HTTP (embedded or cloud - doesn't matter)
    3. If not in control plane → 404 (not registered = not invokable)
    """

    def __init__(self):
        # Use HTTP for internal Docker network (no TLS needed)
        self.control_plane_url = os.getenv(
            "CONTROL_PLANE_URL", get_internal_service_url("control_plane")
        )
        self.service_token = os.getenv("SERVICE_TOKEN", "dev-service-token-insecure")
        self.langgraph_api_key = os.getenv("LANGGRAPH_API_KEY")

        # Agent metadata cache (to avoid repeated control-plane queries)
        self._agent_cache: dict[str, dict] = {}

    async def discover_agent(self, agent_name: str) -> dict[str, Any]:
        """Discover agent from control-plane API.

        Args:
            agent_name: Name of agent to discover

        Returns:
            {
                "agent_name": "research",
                "display_name": "Research Agent",
                "endpoint_url": "http://agent-service:8000/api/agents/research/invoke",
                "langgraph_assistant_id": None,  # or "asst_xyz" for cloud
                "langgraph_url": None,           # or "https://api.langraph.com" for cloud
                "is_cloud": False
            }

        Raises:
            ValueError: If agent not found in control plane registry
        """
        # Check cache first
        if agent_name in self._agent_cache:
            return self._agent_cache[agent_name]

        # Query control-plane for all agents
        try:
            async with get_secure_client(timeout=5.0) as client:
                response = await client.get(
                    f"{self.control_plane_url}/api/agents",
                    headers={"X-Service-Token": self.service_token},
                )
                response.raise_for_status()
                data = response.json()
                agents = data.get("agents", [])
        except Exception as e:
            logger.error(f"Failed to query control plane for agents: {e}")
            raise ValueError(
                f"Failed to discover agent '{agent_name}': Control plane unreachable"
            )

        # Find agent by name or alias
        agent = None
        for a in agents:
            if a.get("name") == agent_name:
                agent = a
                break
            # Check aliases
            if agent_name in a.get("aliases", []):
                agent = a
                break

        if not agent:
            raise ValueError(
                f"Agent '{agent_name}' not found in control plane registry. "
                "Not registered = not invokable."
            )

        # Check if agent is enabled
        if not agent.get("is_public", True):
            raise ValueError(f"Agent '{agent_name}' is disabled")

        # Determine if cloud or embedded based on endpoint_url
        endpoint_url = agent.get("endpoint_url")
        if not endpoint_url:
            raise ValueError(
                f"Agent '{agent_name}' has no endpoint_url configured. "
                "Cannot invoke agent without endpoint."
            )

        # Determine agent type based on endpoint or langgraph fields
        is_cloud = bool(
            agent.get("langgraph_assistant_id") or "langraph" in endpoint_url.lower()
        )

        agent_info = {
            "agent_name": agent.get("name"),
            "display_name": agent.get("display_name", agent.get("name")),
            "endpoint_url": endpoint_url,
            "langgraph_assistant_id": agent.get("langgraph_assistant_id"),
            "langgraph_url": agent.get("langgraph_url"),
            "is_cloud": is_cloud,
        }

        # Cache and return
        self._agent_cache[agent_name] = agent_info
        logger.info(
            f"Discovered agent '{agent_name}' → "
            f"{'cloud' if is_cloud else 'embedded'} at {endpoint_url}"
        )

        return agent_info

    async def invoke(
        self, agent_name: str, query: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Invoke agent via HTTP API (embedded or cloud - same interface).

        Args:
            agent_name: Name of agent to invoke
            query: User query
            context: Optional context dict

        Returns:
            {"response": "...", "metadata": {...}}

        Raises:
            ValueError: If agent not registered in control plane
            httpx.HTTPError: If agent invocation fails
        """
        # Discover agent endpoint from control plane
        agent = await self.discover_agent(agent_name)

        if agent["is_cloud"]:
            return await self._invoke_cloud(agent, query, context or {})
        else:
            return await self._invoke_embedded(agent, query, context or {})

    async def stream(
        self, agent_name: str, query: str, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream agent execution (embedded or cloud - same interface).

        Args:
            agent_name: Name of agent to stream
            query: User query
            context: Optional context dict

        Yields:
            Status update strings

        Raises:
            ValueError: If agent not registered in control plane
        """
        agent = await self.discover_agent(agent_name)

        if agent["is_cloud"]:
            async for update in self._stream_cloud(agent, query, context or {}):
                yield update
        else:
            async for update in self._stream_embedded(agent, query, context or {}):
                yield update

    async def _invoke_embedded(
        self, agent: dict, query: str, context: dict
    ) -> dict[str, Any]:
        """Invoke embedded agent directly (not via HTTP to avoid recursion)."""
        agent_name = agent["agent_name"]

        logger.info(f"Invoking embedded agent '{agent_name}' directly")

        # Import agent registry to get agent instance
        from services.agent_registry import get_agent

        try:
            # Get agent instance and invoke it directly
            agent_instance = get_agent(agent_name)

            # Check if agent is a LangGraph CompiledStateGraph
            if hasattr(agent_instance, "ainvoke") and not hasattr(
                agent_instance, "run"
            ):
                # LangGraph graph - invoke with state dict
                result = await agent_instance.ainvoke({"query": query, **context})
            else:
                # Regular agent with invoke/run methods
                result = await agent_instance.invoke(query, context)

            return result
        except Exception as e:
            logger.error(f"Error invoking embedded agent '{agent_name}': {e}")
            raise

    async def _invoke_cloud(
        self, agent: dict, query: str, context: dict
    ) -> dict[str, Any]:
        """Invoke LangGraph Cloud agent via remote API."""
        if not self.langgraph_api_key:
            raise ValueError("LANGGRAPH_API_KEY not set for cloud agent invocation")

        endpoint = agent["endpoint_url"]

        # LangGraph Cloud API format
        payload = {"input": {"query": query, **context}}

        headers = {
            "Authorization": f"Bearer {self.langgraph_api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"Invoking cloud agent at {endpoint}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint, json=payload, headers=headers, timeout=120.0
            )
            response.raise_for_status()
            cloud_result = response.json()

            # Normalize cloud response to match embedded format
            return {
                "response": cloud_result.get("output", {}).get("response", ""),
                "metadata": cloud_result.get("metadata", {}),
            }

    async def _stream_embedded(
        self, agent: dict, query: str, context: dict
    ) -> AsyncGenerator[str, None]:
        """Stream embedded agent via SSE or websocket."""
        # Replace /invoke with /stream in endpoint
        endpoint = agent["endpoint_url"].replace("/invoke", "/stream")

        payload = {
            "query": query,
            "context": context,
            "user_id": context.get("user_id"),
        }

        logger.info(f"Streaming embedded agent at {endpoint}")

        async with (
            get_secure_client(timeout=120.0) as client,
            client.stream(
                "POST",
                endpoint,
                json=payload,
                headers={"X-Service-Token": self.service_token},
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    yield line

    async def _stream_cloud(
        self, agent: dict, query: str, context: dict
    ) -> AsyncGenerator[str, None]:
        """Stream LangGraph Cloud agent via SSE."""
        if not self.langgraph_api_key:
            raise ValueError("LANGGRAPH_API_KEY not set")

        # LangGraph Cloud streaming endpoint
        endpoint = agent["endpoint_url"].replace("/invoke", "/stream")

        payload = {"input": {"query": query, **context}, "stream_mode": "updates"}

        headers = {
            "Authorization": f"Bearer {self.langgraph_api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"Streaming cloud agent at {endpoint}")

        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST", endpoint, json=payload, headers=headers, timeout=120.0
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    # Parse SSE format: "data: {...}"
                    if line.startswith("data: "):
                        yield line[6:]  # Strip "data: " prefix

    def clear_cache(self):
        """Clear agent metadata cache (useful for testing)."""
        self._agent_cache.clear()
        logger.info("Cleared agent metadata cache")


# Global singleton
agent_client = AgentClient()
