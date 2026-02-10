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
    """Load all agents from merged langgraph.json.

    All agents (system + custom) are defined in langgraph.json.
    The startup.sh script merges configs at runtime.

    Returns:
        Dict mapping agent names to CompiledStateGraph instances
    """
    global _agent_classes

    # Return cached if available and non-empty
    if _agent_classes:
        return _agent_classes

    # Load all agents from unified config
    try:
        from services.unified_agent_loader import get_unified_loader

        loader = get_unified_loader()
        all_agents = loader.discover_agents()

        # Only cache if we actually loaded agents
        if all_agents:
            _agent_classes = all_agents
            logger.info(f"Cached {len(all_agents)} agent classes")
        else:
            logger.warning("No agents loaded from unified loader, NOT caching")

        return all_agents

    except Exception as e:
        logger.error(f"❌ Error loading agents: {e}", exc_info=True)
        return {}


# Cache with TTL
_cached_agents: dict[str, dict[str, Any]] | None = None
_cache_timestamp: float = 0
_cache_ttl_seconds: int = 300  # 5 minutes - agents refresh automatically


def get_agent_registry(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Get agent registry from local langgraph.json (source of truth).

    Optionally fetches metadata from control plane for access management,
    but local agents are the source of truth for what can run.

    Args:
        force_refresh: Force refresh even if cache is valid

    Returns:
        Dict mapping agent names/aliases to agent metadata (includes agent_class)
    """
    global _cached_agents, _cache_timestamp  # noqa: PLW0603

    # Check if cache is still valid (and not empty!)
    if (
        not force_refresh
        and _cached_agents is not None
        and _cached_agents  # Don't return empty cache
        and (time.time() - _cache_timestamp) < _cache_ttl_seconds
    ):
        logger.debug(f"Returning cached registry with {len(_cached_agents)} agents")
        return _cached_agents

    # Load agent classes from langgraph.json (source of truth)
    agent_classes = _load_agent_classes()
    logger.info(f"Loaded {len(agent_classes)} agent classes from langgraph.json")

    # Don't proceed if no agents loaded
    if not agent_classes:
        logger.error("No agents loaded! Returning empty registry (will not cache)")
        return {}

    # Start with local agents as base
    registry = {}
    for agent_name, agent_class in agent_classes.items():
        logger.debug(f"Adding agent '{agent_name}' to registry")
        registry[agent_name.lower()] = {
            "name": agent_name.lower(),
            "display_name": agent_name.replace("_", " ").title(),
            "description": "",
            "aliases": [],
            "is_enabled": True,
            "requires_admin": False,
            "is_system": False,
            "is_primary": True,
            "agent_class": agent_class,
        }

    logger.info(f"Built registry with {len(registry)} agents")

    # Try to fetch metadata from control plane (for descriptions, aliases, etc.)
    try:
        import os

        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")

        # nosemgrep: python.requests.security.disabled-cert-validation.disabled-cert-validation
        response = requests.get(
            f"{control_plane_url}/api/agents",  # nosemgrep: python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http
            timeout=5,
            verify=False,  # nosec B501 - Internal Docker network with self-signed certs
        )
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Merge control plane metadata into local agents
            for agent in agents:
                name = agent["name"].lower()
                if name in registry:
                    # Update with control plane metadata
                    registry[name].update(
                        {
                            "display_name": agent.get(
                                "display_name", registry[name]["display_name"]
                            ),
                            "description": agent.get("description", ""),
                            "aliases": agent.get("aliases", []),
                            "is_enabled": agent.get("is_enabled", True),
                            "requires_admin": agent.get("requires_admin", False),
                            "is_system": agent.get("is_system", False),
                        }
                    )

                    # Register aliases
                    for alias in agent.get("aliases", []):
                        registry[alias.lower()] = {
                            **registry[name],
                            "is_primary": False,
                        }

            logger.info(f"Merged metadata from control plane for {len(agents)} agents")
        else:
            logger.warning(
                f"Control plane returned status {response.status_code}, using local agents only"
            )

    except Exception as e:
        logger.warning(f"Control plane unavailable: {e}, using local agents only")

    # Only cache if we have agents
    if registry:
        _cached_agents = registry
        _cache_timestamp = time.time()
        logger.info(f"Agent registry ready with {len(registry)} agents")
    else:
        logger.error("Registry is empty after loading, NOT caching")

    return registry


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
    for _name, info in registry.items():
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


def get_agent(agent_name: str):
    """Get agent instance by name or alias.

    Args:
        agent_name: Agent name or alias (case-insensitive)

    Returns:
        Agent instance ready for invocation

    Raises:
        ValueError: If agent not found or not available

    Example:
        agent = get_agent("profile")
        result = await agent.invoke("Research Acme Corp", {})
    """
    agent_info = get_agent_info(agent_name)

    if not agent_info:
        raise ValueError(
            f"Agent '{agent_name}' not found. "
            f"Check control-plane registry or external_agents/ directory."
        )

    # Get agent class/instance
    agent_class = agent_info.get("agent_class")

    if not agent_class:
        raise ValueError(
            f"Agent '{agent_name}' found in control-plane but no implementation available. "
            f"Ensure agent exists in external_agents/{agent_name}/agent.py"
        )

    # Check if agent is already an instance (e.g., LangGraph CompiledStateGraph)
    # If it's a LangGraph graph, it will have 'ainvoke' but not 'run' method
    if hasattr(agent_class, "ainvoke") and not hasattr(agent_class, "run"):
        # Already an instance (LangGraph graph) - return as-is
        logger.info(
            f"Agent '{agent_name}' is a LangGraph graph instance - returning as-is"
        )
        return agent_class
    elif callable(agent_class):
        # It's a class - instantiate it
        logger.info(f"Agent '{agent_name}' is a class - instantiating")
        return agent_class()
    else:
        # Already an instance of some other type - return as-is
        logger.info(f"Agent '{agent_name}' is an instance - returning as-is")
        return agent_class


def clear_cache():
    """Clear the cached agent registry (for testing or manual refresh)."""
    global _cached_agents, _cache_timestamp  # noqa: PLW0603
    _cached_agents = None
    _cache_timestamp = 0
