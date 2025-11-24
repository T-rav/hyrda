"""Agent registry that fetches from agent-service API.

Replaces the local agent registry that required langgraph dependencies.
Now the bot just needs to know about agents for routing, not execute them.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_cached_agents: dict[str, dict[str, Any]] | None = None


def get_agent_registry() -> dict[str, dict[str, Any]]:
    """Get agent registry from agent-service API.

    Returns a dict mapping agent names/aliases to agent info.
    Caches the result to avoid repeated API calls.
    """
    global _cached_agents  # noqa: PLW0603

    if _cached_agents is not None:
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
            registry = {}
            for agent in agents:
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
            logger.info(f"Loaded {len(agents)} agents from agent-service")
            return registry
        else:
            logger.error(
                f"Failed to fetch agents from agent-service: HTTP {response.status_code}"
            )
            return {}

    except Exception as e:
        logger.error(f"Error fetching agents from agent-service: {e}")
        return {}


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
    """Clear the cached agent registry (for testing)."""
    global _cached_agents  # noqa: PLW0603
    _cached_agents = None


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
