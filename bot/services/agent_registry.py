"""Agent registry that fetches from agent-service API.

Replaces the local agent registry that required langgraph dependencies.
Now the bot just needs to know about agents for routing, not execute them.

Uses TTL caching - automatically refreshes every 5 minutes to pick up
agent changes without restart.
"""

import logging
import time

from bot_types import AgentInfo

logger = logging.getLogger(__name__)

# Agent registry configuration constants
CACHE_TTL_SECONDS = 300  # 5 minutes - agents refresh automatically
AGENT_SERVICE_TIMEOUT = 5  # Timeout for agent service API calls in seconds

_cached_agents: dict[str, AgentInfo] | None = None
_cache_timestamp: float = 0
_cache_ttl_seconds: int = CACHE_TTL_SECONDS


def get_agent_registry(force_refresh: bool = False) -> dict[str, AgentInfo]:
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

        from config.settings import Settings

        settings = Settings()
        control_plane_url = settings.control_plane_url

        response = requests.get(
            f"{control_plane_url}/api/agents", timeout=AGENT_SERVICE_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Build registry dict mapping names/aliases to agent info
            # Only include agents that are enabled AND visible in Slack
            registry = {}
            for agent in agents:
                # Skip disabled or non-Slack-visible agents
                # System agents are always enabled, so check is_enabled for non-system agents
                is_enabled = agent.get("is_enabled", False)
                is_slack_visible = agent.get("is_slack_visible", False)
                is_system = agent.get("is_system", False)

                # Agent must be enabled (or be a system agent) AND visible in Slack
                if not ((is_system or is_enabled) and is_slack_visible):
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


def get_agent_info(agent_name: str) -> AgentInfo | None:
    """Get agent info by name or alias."""
    registry = get_agent_registry()
    return registry.get(agent_name.lower())


def get_primary_name(agent_name: str) -> str:
    """Get primary agent name from name or alias."""
    agent_info = get_agent_info(agent_name)
    if agent_info:
        return agent_info["name"]
    return agent_name.lower()


def check_agent_availability(agent_name: str) -> dict[str, bool | str] | None:
    """Check if agent exists and its availability status.

    This queries ALL agents from control-plane (including disabled) to provide
    better error messages when users try to invoke disabled agents.

    Args:
        agent_name: Agent name or alias to check

    Returns:
        Dict with status info if agent exists:
        {
            "exists": True,
            "is_enabled": bool,
            "is_slack_visible": bool,
            "reason": str  # Human-readable reason if unavailable
        }
        None if agent doesn't exist at all
    """
    try:
        import requests

        from config.settings import Settings

        settings = Settings()

        # Query control-plane directly for all agents (including disabled)
        # Note: This bypasses the bot's filtered registry
        control_plane_url = settings.control_plane_url or "http://control_plane:6001"

        response = requests.get(
            f"{control_plane_url}/api/agents?include_deleted=false",
            timeout=AGENT_SERVICE_TIMEOUT,
        )

        if response.status_code != 200:
            logger.warning(
                f"Failed to fetch agents for availability check: HTTP {response.status_code}"
            )
            return None

        data = response.json()
        agents = data.get("agents", [])

        # Search for agent by name or alias
        for agent in agents:
            agent_name_lower = agent_name.lower()
            primary_name = agent["name"].lower()
            aliases = [a.lower() for a in agent.get("aliases", [])]

            if agent_name_lower == primary_name or agent_name_lower in aliases:
                is_enabled = agent.get("is_enabled", False)
                is_slack_visible = agent.get("is_slack_visible", False)
                is_system = agent.get("is_system", False)

                # Determine availability reason
                if not is_enabled:
                    reason = "This agent is currently disabled by an administrator."
                elif not is_slack_visible:
                    reason = "This agent is not available in Slack (backend/API only)."
                else:
                    reason = "Agent is available"

                return {
                    "exists": True,
                    "is_enabled": is_enabled
                    or is_system,  # System agents always enabled
                    "is_slack_visible": is_slack_visible,
                    "reason": reason,
                }

        # Agent not found
        return None

    except Exception as e:
        logger.error(f"Error checking agent availability: {e}")
        return None


def clear_cache():
    """Clear the cached agent registry (for testing or manual refresh)."""
    global _cached_agents, _cache_timestamp  # noqa: PLW0603
    _cached_agents = None
    _cache_timestamp = 0


def route_command(text: str) -> tuple[AgentInfo | None, str, str | None]:
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
