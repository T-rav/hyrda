"""Dynamic agent registry that fetches from control plane API.

Agents are now configured in the control plane database and discovered
dynamically without code changes. Uses TTL caching to refresh periodically.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Cache with TTL
_cached_agents: dict[str, dict[str, Any]] | None = None
_cache_timestamp: float = 0
_cache_ttl_seconds: int = 300  # 5 minutes - agents refresh automatically


def get_agent_registry(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Get agent registry from control plane API.

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
        import os

        import requests

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control_plane:6001")

        response = requests.get(f"{control_plane_url}/api/agents", timeout=5)
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Build registry dict mapping names/aliases to agent info
            registry = {}
            for agent in agents:
                name = agent["name"]
                aliases = agent.get("aliases", [])

                agent_info = {
                    "name": name.lower(),
                    "display_name": agent.get("display_name", name),
                    "description": agent.get("description", ""),
                    "aliases": aliases,
                    "is_public": agent.get("is_public", True),
                    "requires_admin": agent.get("requires_admin", False),
                    "is_system": agent.get("is_system", False),
                    "is_primary": True,
                }

                # Register primary name
                registry[name.lower()] = agent_info

                # Register aliases
                for alias in aliases:
                    registry[alias.lower()] = {
                        **agent_info,
                        "is_primary": False,
                    }

            _cached_agents = registry
            _cache_timestamp = time.time()
            logger.info(
                f"Loaded {len(agents)} agents from control plane (TTL: {_cache_ttl_seconds}s)"
            )
            return registry
        else:
            logger.error(
                f"Failed to fetch agents from control plane: HTTP {response.status_code}"
            )
            # Return cached data if available, even if stale
            return _cached_agents or {}

    except Exception as e:
        logger.error(f"Error fetching agents from control plane: {e}")
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


def list_agents() -> list[dict[str, Any]]:
    """List all registered agents (primary names only)."""
    registry = get_agent_registry()
    return [info for info in registry.values() if info.get("is_primary", False)]


def clear_cache():
    """Clear the cached agent registry (for testing or manual refresh)."""
    global _cached_agents, _cache_timestamp  # noqa: PLW0603
    _cached_agents = None
    _cache_timestamp = 0
