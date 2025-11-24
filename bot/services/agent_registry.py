"""Agent registry that fetches from agent-service API.

Replaces the local agent registry that required langgraph dependencies.
Now the bot just needs to know about agents for routing, not execute them.

Uses TTL caching - automatically refreshes every 5 minutes to pick up
agent changes without restart.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_cached_agents: dict[str, dict[str, Any]] | None = None
_cache_timestamp: float = 0
_cache_ttl_seconds: int = 300  # 5 minutes - agents refresh automatically


def get_agent_registry(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Get agent registry from agent-service API.

    Returns a dict mapping agent names/aliases to agent info.
    Caches the result with TTL - refreshes automatically every 5 minutes.

    Args:
        force_refresh: Force refresh even if cache is valid

    Returns:
        Dict mapping agent names/aliases to agent metadata
    """
    global _cached_agents, _cache_timestamp  # noqa: PLW0603

    # Check if cache is still valid
    if (
        not force_refresh
        and _cached_agents is not None
        and (time.time() - _cache_timestamp) < _cache_ttl_seconds
    ):
        return _cached_agents

    try:
        import requests

        from config.settings import get_settings

        settings = get_settings()
        agent_service_url = settings.agent_service_url or "http://agent_service:8000"

        response = requests.get(f"{agent_service_url}/api/agents", timeout=5)
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Build registry dict mapping names/aliases to agent info
            # Only include enabled agents (is_public=true)
            registry = {}
            for agent in agents:
                # Skip disabled agents
                if not agent.get("is_public", False):
                    continue
                name = agent["name"]
                aliases = agent.get("aliases", [])

                # Register primary name
                registry[name.lower()] = {
                    "name": name.lower(),
                    "description": agent.get("description", ""),
                    "aliases": aliases,
                    "is_primary": True,
                }

                # Register aliases
                for alias in aliases:
                    registry[alias.lower()] = {
                        "name": name.lower(),  # Points to primary name
                        "description": agent.get("description", ""),
                        "aliases": aliases,
                        "is_primary": False,
                    }

            _cached_agents = registry
            _cache_timestamp = time.time()
            logger.info(
                f"Loaded {len(agents)} agents from agent-service (TTL: {_cache_ttl_seconds}s)"
            )
            return registry
        else:
            logger.error(
                f"Failed to fetch agents from agent-service: HTTP {response.status_code}"
            )
            # Return cached data if available, even if stale
            return _cached_agents or {}

    except Exception as e:
        logger.error(f"Error fetching agents from agent-service: {e}")
        # Return cached data if available, even if stale
        return _cached_agents or {}


def get_agent_info(agent_name: str) -> dict[str, Any] | None:
    """Get agent info by name or alias."""
    registry = get_agent_registry()
    return registry.get(agent_name.lower())


def get_primary_name(agent_name: str) -> str:
    """Get primary agent name from name or alias."""
    agent_info = get_agent_info(agent_name)
    if agent_info:
        return agent_info["name"]
    return agent_name.lower()


def clear_cache():
    """Clear the cached agent registry (for testing or manual refresh)."""
    global _cached_agents, _cache_timestamp  # noqa: PLW0603
    _cached_agents = None
    _cache_timestamp = 0


def route_command(text: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """Parse command and route to appropriate agent.

    Parses messages like:
    - "-profile tell me about AllCampus AI"
    - "meddic analyze this deal"

    Args:
        text: Message text containing bot command

    Returns:
        Tuple of (agent_info, query, primary_name):
        - agent_info: Dict with agent metadata, or None if not found
        - query: Parsed query text
        - primary_name: Primary name of agent (resolves aliases)
    """
    import re

    # Match pattern: optional dash + command + rest of text
    match = re.match(r"^-?(\w+)\s*(.*)", text.strip(), re.IGNORECASE)

    if not match:
        return None, "", None

    command_name = match.group(1).lower()
    query = match.group(2).strip()

    # Check if this is a registered agent
    agent_info = get_agent_info(command_name)
    if not agent_info:
        return None, query, None

    primary_name = agent_info["name"]
    logger.info(f"Routing command '{command_name}' to agent '{primary_name}'")

    return agent_info, query, primary_name
