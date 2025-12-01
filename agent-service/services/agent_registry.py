"""Dynamic agent registry that fetches from control plane API.

Agents are now configured in the control plane database and discovered
dynamically without code changes. Uses TTL caching to refresh periodically.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Agent class mapping - maps agent names to their actual classes
_agent_classes: dict[str, type] = {}


def _load_agent_classes() -> dict[str, type]:
    """Load agent classes from the local registry.

    Returns:
        Dict mapping agent names to agent classes
    """
    global _agent_classes

    if _agent_classes:
        return _agent_classes

    try:
        # Import the local registry which has agent classes registered
        from agents.registry import agent_registry as local_registry

        # Build mapping from agent names to classes
        _agent_classes = {}
        for name, info in local_registry._agents.items():
            if "agent_class" in info:
                _agent_classes[info["name"]] = info["agent_class"]
                # Also map aliases
                for alias in info.get("aliases", []):
                    _agent_classes[alias.lower()] = info["agent_class"]

        logger.info(f"Loaded {len(_agent_classes)} agent class mappings")
        return _agent_classes
    except Exception as e:
        logger.error(f"Error loading agent classes: {e}", exc_info=True)
        return {}

# Cache with TTL
_cached_agents: dict[str, dict[str, Any]] | None = None
_cache_timestamp: float = 0
_cache_ttl_seconds: int = 300  # 5 minutes - agents refresh automatically


def get_agent_registry(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Get agent registry from control plane API.

    Returns a dict mapping agent names/aliases to agent info.
    Caches the result with TTL - refreshes automatically every 5 minutes.
    Merges control plane metadata with local agent classes.

    Args:
        force_refresh: Force refresh even if cache is valid

    Returns:
        Dict mapping agent names/aliases to agent metadata (includes agent_class)
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

            # Load agent classes from local registry
            agent_classes = _load_agent_classes()

            # Build registry dict mapping names/aliases to agent info
            # Only include enabled agents (is_public=true)
            registry = {}
            for agent in agents:
                # Skip disabled agents
                if not agent.get("is_public", False):
                    continue
                name = agent["name"]
                aliases = agent.get("aliases", [])

                # Get agent class if available
                agent_class = agent_classes.get(name.lower())

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

                # Add agent_class if available
                if agent_class:
                    agent_info["agent_class"] = agent_class

                # Register primary name
                registry[name.lower()] = agent_info

                # Register aliases
                for alias in aliases:
                    alias_info = {
                        **agent_info,
                        "is_primary": False,
                    }
                    # Also add agent_class to aliases
                    if agent_class:
                        alias_info["agent_class"] = agent_class
                    registry[alias.lower()] = alias_info

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


def get(agent_name: str) -> dict[str, Any] | None:
    """Get agent info by name or alias (alias for get_agent_info for API compatibility).

    Args:
        agent_name: Agent name or alias (case-insensitive)

    Returns:
        Agent info dict with 'agent_class' and metadata, or None if not found
    """
    return get_agent_info(agent_name)


def get_primary_name(agent_name: str) -> str | None:
    """Get primary agent name from name or alias.

    Args:
        agent_name: Agent name or alias

    Returns:
        Primary name if found, None otherwise
    """
    agent_info = get_agent_info(agent_name)
    if not agent_info:
        return None

    # If it's a primary agent, return its name
    if agent_info.get("is_primary", False):
        return agent_info["name"]

    # If it's an alias, find the primary agent with the same name
    registry = get_agent_registry()
    agent_base_name = agent_info.get("name")
    for name, info in registry.items():
        if info.get("is_primary", False) and info.get("name") == agent_base_name:
            return info["name"]

    # Fallback: return the name from the info
    return agent_info.get("name")


def list_agents() -> list[dict[str, Any]]:
    """List all registered agents (primary names only).

    Returns:
        List of agent info dicts with name, agent_class, and aliases
    """
    registry = get_agent_registry()
    return [info for info in registry.values() if info.get("is_primary", False)]


def clear_cache():
    """Clear the cached agent registry (for testing or manual refresh)."""
    global _cached_agents, _cache_timestamp  # noqa: PLW0603
    _cached_agents = None
    _cache_timestamp = 0
