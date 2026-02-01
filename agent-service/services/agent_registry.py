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
    """Load agent classes from both system and external directories.

    System agents: LangGraph workflows baked into image (agents/system/)
    External agents: Client-customizable workflows from volume mounts

    Returns:
        Dict mapping agent names to agent classes/instances
    """
    global _agent_classes

    if _agent_classes:
        return _agent_classes

    all_agents = {}

    # Load system agents first (shipped with framework)
    try:
        from services.system_agent_loader import get_system_loader

        system_loader = get_system_loader()
        system_agents = system_loader.discover_agents()

        for name, agent_class in system_agents.items():
            all_agents[name.lower()] = agent_class

        if system_agents:
            logger.info(
                f"✅ Loaded {len(system_agents)} system agent(s) from agents/system/"
            )
    except Exception as e:
        logger.error(f"❌ Error loading system agents: {e}", exc_info=True)

    # Load external agents (client-provided, CANNOT override system agents)
    # Skip if EXTERNAL_AGENTS_IN_CLOUD=true (agents deployed to LangGraph Cloud)
    import os

    load_external = os.getenv("LOAD_EXTERNAL_AGENTS", "true").lower() == "true"

    if load_external:
        try:
            from services.external_agent_loader import get_external_loader

            external_loader = get_external_loader()
            external_agents = external_loader.discover_agents()

            # Prevent external agents from overriding system agents
            for name, agent_class in external_agents.items():
                name_lower = name.lower()
                if name_lower in all_agents:
                    logger.error(
                        f"❌ External agent '{name}' conflicts with system agent - IGNORING external version"
                    )
                    # Skip this external agent - system takes precedence
                else:
                    all_agents[name_lower] = agent_class

            if external_agents:
                logger.info(
                    f"✅ Loaded {len(external_agents)} external agent(s) from volume mount"
                )
            else:
                logger.warning(
                    "⚠️ No external agents loaded (EXTERNAL_AGENTS_PATH not set or empty)"
                )
        except Exception as e:
            logger.error(f"❌ Error loading external agents: {e}", exc_info=True)
    else:
        logger.info(
            "⏭️ Skipping external agents (LOAD_EXTERNAL_AGENTS=false - deployed to cloud)"
        )

    _agent_classes = all_agents
    logger.info(f"📦 Total agents available: {len(_agent_classes)} (system + external)")
    return _agent_classes


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
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control_plane:6001")

        response = requests.get(
            f"{control_plane_url}/api/agents",
            timeout=5,
            verify=False,  # nosec B501 - Internal Docker network with self-signed certs
        )
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Load agent classes from local registry
            agent_classes = _load_agent_classes()

            # Build registry dict mapping names/aliases to agent info
            # Only include enabled agents (is_enabled=true)
            registry = {}
            for agent in agents:
                # Skip disabled agents
                if not agent.get("is_enabled", False):
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
                    "is_enabled": agent.get("is_enabled", True),
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
